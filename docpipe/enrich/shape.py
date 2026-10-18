# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/enrich/shape.py
# About: Text-shape signatures and nearest-neighbour document-type hints.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Text-shape signatures and nearest-neighbour document-type hints.

A signature counts what a block of text is made of (lines, characters by
class, distinct tokens) without keeping any of its words. Signatures are
compared as scale-free profiles, so a five-line memo and a five-thousand-line
export of the same kind still land close together.

``nearest`` ranks a catalog of labelled exemplars by weighted L1 distance and
returns the closest few. The result is a hint for a person or a router, not a
classification.

Catalog file (JSON)::

    {"at": "2026-01-31T12:00:00+00:00",
     "exemplars": [{"id": 1, "title": "Q3 invoice", "label": "invoice",
                    "path": "samples/q3.csv",
                    "signature": {"lines": 40, "chars": 2200, ...}}]}

Signature keys are Signature field names, and their values must be finite
and non-negative.

Weights file (JSON), optional; axes left out keep their fallback weight.
Each weight must be finite and non-negative::

    {"digit": 2.0, "size": 0.1}

Both files are read as UTF-8, with or without a byte-order mark.

Command line::

    python -m docpipe.enrich.shape FILE [--catalog PATH] [--weights PATH] [-n N]
"""

import argparse
import json
import math
import sys
import unicodedata
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import NamedTuple

# How many hints the command line shows by default.
SHOWN = 3

AXIS_UPPER = "upper"
AXIS_LOWER = "lower"
AXIS_CASELESS = "caseless"
AXIS_DIGIT = "digit"
AXIS_PUNCT = "punct"
AXIS_SPACE = "space"
AXIS_MEAN_LINE = "meanln"
AXIS_TOKENS = "tokens"
AXIS_SIZE = "size"

# Character-class axes. Each name is also a Signature field.
_CLASS_AXES = (AXIS_UPPER, AXIS_LOWER, AXIS_CASELESS, AXIS_DIGIT, AXIS_PUNCT,
               AXIS_SPACE)

# Used when no weights are configured, and for any axis a weights file leaves
# out. Digits and punctuation weigh most; size weighs least, so length alone
# never decides a match.
FALLBACK_WEIGHTS = {
    AXIS_UPPER: 1.0, AXIS_LOWER: 1.0, AXIS_CASELESS: 1.0, AXIS_DIGIT: 1.4,
    AXIS_PUNCT: 1.3, AXIS_SPACE: 0.8, AXIS_MEAN_LINE: 0.9, AXIS_TOKENS: 0.7,
    AXIS_SIZE: 0.25,
}

AGE_UNKNOWN = "age unknown"


@dataclass(frozen=True)
class Signature:
    """Character-class counts for a block of text."""

    lines: int = 0
    chars: int = 0
    upper: int = 0
    lower: int = 0
    caseless: int = 0   # letters with no upper/lower form: CJK, Arabic, ...
    digit: int = 0
    punct: int = 0      # everything else: punctuation, symbols, marks
    space: int = 0
    tokens: int = 0     # distinct whitespace-separated tokens
    mean_line: float = 0.0


def _char_class(ch):
    if ch.isspace():
        return AXIS_SPACE
    cat = unicodedata.category(ch)
    if cat == "Lu":
        return AXIS_UPPER
    if cat == "Ll":
        return AXIS_LOWER
    if cat[0] == "L":
        return AXIS_CASELESS
    if cat == "Nd":
        return AXIS_DIGIT
    return AXIS_PUNCT


def signature(lines):
    """Measure ``lines``: one string to split, or an iterable of lines.

    Line endings are not counted, so an open text file can be passed as is
    and measures the same as its text read in one piece.
    """
    if isinstance(lines, str):
        lines = lines.splitlines()
    counts = dict.fromkeys(_CLASS_AXES, 0)
    n_lines = chars = 0
    seen = set()
    for line in lines:
        line = line.rstrip("\r\n")
        n_lines += 1
        for ch in line:
            chars += 1
            counts[_char_class(ch)] += 1
        seen.update(line.split())
    mean = chars / n_lines if n_lines else 0.0
    return Signature(lines=n_lines, chars=chars, tokens=len(seen),
                     mean_line=mean, **counts)


def profile(sig):
    """Turn a signature into the scale-free vector that distances run on.

    Each class axis is a share of all characters. Mean line length and tokens
    per line are capped and scaled to 0..1. Size enters once, as log10 of the
    character count.
    """
    n = max(sig.chars, 1)
    lines = max(sig.lines, 1)
    p = {axis: getattr(sig, axis) / n for axis in _CLASS_AXES}
    p[AXIS_MEAN_LINE] = min(sig.mean_line, 200) / 200
    p[AXIS_TOKENS] = min(sig.tokens / lines, 40) / 40
    p[AXIS_SIZE] = math.log10(max(10, n))
    return p


def distance(a, b, weights):
    """Weighted L1 distance between two profiles.

    ``weights`` must name every axis. The size term is capped at four orders
    of magnitude and scaled to 0..1.
    """
    d = 0.0
    for axis in _CLASS_AXES + (AXIS_MEAN_LINE, AXIS_TOKENS):
        d += weights[axis] * abs(a[axis] - b[axis])
    d += weights[AXIS_SIZE] * min(abs(a[AXIS_SIZE] - b[AXIS_SIZE]), 4) / 4
    return d


def load_weights(path=None):
    """Return axis weights, read from a JSON object file at ``path``.

    ``None`` means no weights are configured and a copy of FALLBACK_WEIGHTS
    is returned. Axes the file leaves out keep their fallback weight, so an
    older file never scores a newer axis at zero. Raises OSError if the file
    cannot be read and ValueError if it is not an object of finite,
    non-negative numbers keyed by known axis names. A NaN or negative weight
    would rank the farthest exemplar first instead of the nearest.
    """
    weights = dict(FALLBACK_WEIGHTS)
    if path is None:
        return weights
    with open(path, encoding="utf-8-sig") as fh:
        # Integers are read as floats, so an oversized one becomes inf and is
        # rejected below instead of overflowing later.
        raw = json.load(fh, parse_int=float)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: weights must be a JSON object")
    for axis, value in raw.items():
        if axis not in FALLBACK_WEIGHTS:
            raise ValueError(f"{path}: unknown axis {axis!r}")
        if (not isinstance(value, float) or not math.isfinite(value)
                or value < 0):
            raise ValueError(f"{path}: weight for {axis!r} is not a finite, "
                             f"non-negative number")
        weights[axis] = value
    return weights


@dataclass(frozen=True)
class Exemplar:
    """A known document: its type label and its signature."""

    id: int
    title: str
    label: str
    signature: Signature
    path: str = ""


@dataclass(frozen=True)
class Catalog:
    """Labelled exemplars, and when the catalog was written (RFC 3339)."""

    at: str = ""
    exemplars: tuple = ()


class CatalogError(ValueError):
    """The catalog file exists but cannot be used."""


_SIG_FIELDS = {f.name for f in fields(Signature)}


def _exemplar(raw):
    sig = {}
    for name, value in raw.get("signature", {}).items():
        # An unknown key would otherwise leave its axis at zero unnoticed.
        if name not in _SIG_FIELDS:
            raise ValueError(f"unknown signature field {name!r}")
        num = float(value) if name == "mean_line" else int(value)
        # One NaN in the catalog would scramble the whole ranking.
        if num < 0 or not math.isfinite(num):
            raise ValueError(f"signature field {name!r} is not a finite, "
                             f"non-negative number")
        sig[name] = num
    return Exemplar(id=int(raw.get("id", 0)), title=str(raw.get("title", "")),
                    label=str(raw.get("label", "")),
                    signature=Signature(**sig), path=str(raw.get("path", "")))


def load_catalog(path):
    """Read a catalog file.

    Three outcomes stay distinct: an absent file raises FileNotFoundError, a
    corrupt one raises CatalogError, and a valid file with no exemplars
    returns an empty Catalog. Text that is not UTF-8 counts as corrupt.
    """
    # open() stays outside the try so a missing file is never called corrupt.
    with open(path, encoding="utf-8-sig") as fh:
        try:
            raw = json.load(fh)
            return Catalog(
                at=str(raw.get("at", "")),
                exemplars=tuple(_exemplar(e)
                                for e in raw.get("exemplars", [])),
            )
        except (ValueError, TypeError, AttributeError, KeyError,
                OverflowError) as e:
            raise CatalogError(f"{path}: unreadable catalog: {e}") from e


class Hit(NamedTuple):
    exemplar: Exemplar
    distance: float


def nearest(sig, exemplars, n=SHOWN, weights=None):
    """Return up to ``n`` exemplars closest in shape to ``sig``, nearest first.

    Missing or empty ``weights`` mean FALLBACK_WEIGHTS, and a partial map is
    filled in from it. Scoring on an empty map would put every exemplar at
    distance 0: a matcher that reports success while doing nothing.
    """
    w = {**FALLBACK_WEIGHTS, **(weights or {})}
    me = profile(sig)
    hits = [Hit(e, distance(me, profile(e.signature), w)) for e in exemplars]
    hits.sort(key=lambda h: h.distance)
    return hits[:max(n, 0)]


def age(at, now=None):
    """Describe how old an RFC 3339 timestamp is, e.g. "written 3 hour(s) ago".

    Show this before any result drawn from a catalog, so an old answer is
    never mistaken for a fresh one. ``now`` must be timezone-aware; it
    defaults to the current UTC time. Timestamps without an offset are
    reported as AGE_UNKNOWN.
    """
    try:
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return AGE_UNKNOWN
    if t.tzinfo is None:
        return AGE_UNKNOWN
    secs = ((now or datetime.now(timezone.utc)) - t).total_seconds()
    if secs < 60:
        return "written just now"
    if secs < 3600:
        return f"written {int(secs // 60)} minute(s) ago"
    if secs < 86400:
        return f"written {int(secs // 3600)} hour(s) ago"
    return f"written {int(secs // 86400)} day(s) ago"


def main(argv=None):
    """Print a file's signature and, given a catalog, its nearest exemplars."""
    ap = argparse.ArgumentParser(
        prog="python -m docpipe.enrich.shape",
        description="Measure a text file's shape and suggest similar "
                    "documents from a catalog.")
    ap.add_argument("file", help="UTF-8 text file to measure")
    ap.add_argument("--catalog", help="catalog JSON file of exemplars")
    ap.add_argument("--weights", help="JSON object of axis weights "
                                      "(default: built-in fallback)")
    ap.add_argument("-n", type=int, default=SHOWN, help="hints to show")
    args = ap.parse_args(argv)

    try:
        with open(args.file, encoding="utf-8-sig", errors="replace") as fh:
            sig = signature(fh.read())
    except FileNotFoundError as e:
        print(f"not found: {e.filename}", file=sys.stderr)
        return 1
    except OSError as e:
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(asdict(sig)))
    if not args.catalog:
        return 0

    try:
        weights = load_weights(args.weights)
        catalog = load_catalog(args.catalog)
    except FileNotFoundError as e:
        print(f"not found: {e.filename}; no hints given", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    print(f"catalog {age(catalog.at)}, "
          f"{len(catalog.exemplars)} exemplar(s)")
    if args.weights is None:
        print("weights: built-in fallback")
    if not catalog.exemplars:
        print("the catalog lists no exemplars; nothing to compare against")
        return 0
    for hit in nearest(sig, catalog.exemplars, args.n, weights):
        e = hit.exemplar
        print(f"{hit.distance:6.3f}  {e.label or '-':<12} {e.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ==== stamp v1 | author=kjFriday | hmac-sha256=b3d7862497e5ba3ce8cc9b19f462f1b0783ca90f7e1872d5957fe6f05f2d7442 ====
