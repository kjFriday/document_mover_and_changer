# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/enrich/normalize.py
# About: Metadata normalisation for the enrich stage.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Metadata normalisation for the enrich stage.

``fold`` is for short metadata fields only: titles, authors, table cells.
It is lossy (accents are stripped and other non-ASCII characters become
spaces, which then collapse), so never run it over body text.

docpipe.output.documents calls it on customer and product names, dates and
kinds, so a fixed-width ASCII document never breaks on an odd character.

How the folding works, for a reader new to Unicode normalisation:

1. NFKD ("compatibility decomposition", Unicode Standard Annex #15) splits
   an accented letter into its base letter plus a combining mark, so
   U+00E9 (e with acute) becomes "e" + U+0301. It also maps compatibility
   forms such as ligatures and full-width letters to plain ones.
2. Dropping every combining mark then leaves the bare base letters.
3. A short table maps the typographic punctuation NFKD leaves alone (curly
   quotes, dashes, the multiplication and degree signs) to ASCII.
4. Whatever is still outside printable ASCII becomes a space, whitespace
   runs collapse to one space, and the result is capped at ``limit``.
"""

import unicodedata

# Default cap, in characters. The same number as textsafe.LIMIT, but set
# separately: this module is a ported library and imports nothing from the app.
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
    are cut and end in "..."; with a ``limit`` of 3 or less there is no room
    for the dots, so the text is simply cut.

    Each list item is folded with the same ``limit``, and the joined string is
    capped again, so the whole result never exceeds ``limit``.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        value = ", ".join(fold(v, limit) for v in value if v is not None)
    # split accented letters into base letter + combining mark, then drop the marks
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
            s = s[:max(limit, 0)]  # max(): a negative slice end would count from the end
    return s

# ==== stamp v1 | author=kjFriday | hmac-sha256=0734bd30aced233ae5e7d1d30f650f6559a4dc7ea585b55c5883fe33bc53a834 ====
