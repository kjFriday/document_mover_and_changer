# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/enrich/normalize.py
# About: Metadata normalisation for the enrich stage.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Metadata normalisation for the enrich stage.

``fold`` is for short metadata fields only: titles, authors, table cells.
It is lossy (accents are stripped and other non-ASCII characters dropped), so
never run it over body text.
"""

import unicodedata

LIMIT = 240

# Punctuation that NFKD leaves alone, mapped to ASCII look-alikes. Written as
# code points so this file stays pure ASCII.
_REPLACEMENTS = (
    (0x2019, "'"), (0x2018, "'"), (0x201C, '"'), (0x201D, '"'),
    (0x2013, "-"), (0x2014, "-"), (0x00D7, "x"), (0x00B0, " deg "),
)


def fold(value, limit=LIMIT):
    """Fold ``value`` to printable ASCII on a single line.

    ``None`` becomes "", booleans become "yes"/"no", and lists or tuples are
    joined with ", " (``None`` items skipped). Accented letters keep their
    base letter; anything else outside printable ASCII becomes a space, and
    runs of whitespace collapse to one space. Results longer than ``limit``
    are cut and end in "...".
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        value = ", ".join(fold(v, limit) for v in value if v is not None)
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    for code, plain in _REPLACEMENTS:
        s = s.replace(chr(code), plain)
    # Tabs and newlines would break one-line framing, not merely look odd.
    s = "".join(c if 32 <= ord(c) <= 126 else " " for c in s)
    s = " ".join(s.split())
    if len(s) > limit:
        if limit > 3:
            s = s[:limit - 3] + "..."
        else:
            s = s[:max(limit, 0)]
    return s

# ==== stamp v1 | author=kjFriday | hmac-sha256=c23ee738ea2ae8d1154f1c60d3da7a602efe7cf922f9637e336defffdbd24856 ====
