# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_normalize.py
# About: Tests for docpipe.enrich.normalize.fold.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for docpipe.enrich.normalize.fold.

Inputs are written as \\u escapes so the file stays ASCII and every character is visible. They cover
the value types fold accepts, accent stripping, the punctuation table, whitespace, how lossy it is for
scripts with no ASCII form, and the length cap.
"""

import unittest

from docpipe.enrich.normalize import LIMIT, fold


class FoldTest(unittest.TestCase):
    """fold() on one kind of input per test."""

    def test_scalars(self):
        """None is empty, booleans read yes/no, and numbers print as str() does."""
        self.assertEqual(fold(None), "")
        self.assertEqual(fold(True), "yes")
        self.assertEqual(fold(False), "no")
        self.assertEqual(fold(42), "42")
        self.assertEqual(fold(2.5), "2.5")

    def test_accents_keep_their_base_letter(self):
        """e-acute, e-grave and u-circumflex lose their accents and keep their letters."""
        self.assertEqual(fold("Caf\u00e9 Cr\u00e8me Br\u00fbl\u00e9e"),
                         "Cafe Creme Brulee")

    def test_typographic_punctuation(self):
        """Curly quotes, en and em dashes, the multiplication sign and the degree sign map to ASCII."""
        self.assertEqual(
            fold("\u201cQuoted\u201d \u2014 it\u2019s \u2018fine\u2019"),
            "\"Quoted\" - it's 'fine'")
        self.assertEqual(fold("3\u00d74 at 20\u00b0C"), "3x4 at 20 deg C")
        self.assertEqual(fold("2019\u20132020"), "2019-2020")

    def test_one_line_and_collapsed_whitespace(self):
        """Tabs, newlines and CRLF become single spaces, and the ends are trimmed."""
        self.assertEqual(fold("  a\tb\n\nc   d\r\n"), "a b c d")

    def test_lists_and_tuples(self):
        """Items are folded and joined with ", ", None items skipped; an empty list is empty."""
        self.assertEqual(fold(["Ann Lee", None, "Bo Park"]), "Ann Lee, Bo Park")
        self.assertEqual(fold(("x", True)), "x, yes")
        self.assertEqual(fold([]), "")

    def test_lossy_for_non_latin_text(self):
        """Two Japanese characters vanish entirely, leaving only the ASCII word."""
        # Why fold is for metadata only: letters with no ASCII form vanish.
        self.assertEqual(fold("\u6587\u66f8 report"), "report")

    def test_default_limit(self):
        """The default cap is 240, and a longer value is cut to exactly 240 ending in "..."."""
        out = fold("x" * 500)
        self.assertEqual(LIMIT, 240)
        self.assertEqual(len(out), 240)
        self.assertTrue(out.endswith("..."))

    def test_custom_limit(self):
        """Over the limit gets "..." when it fits (5), exactly at it is kept (6), and 2 and 0 are plain cuts."""
        self.assertEqual(fold("abcdef", limit=5), "ab...")
        self.assertEqual(fold("abcdef", limit=6), "abcdef")
        self.assertEqual(fold("abcdef", limit=2), "ab")
        self.assertEqual(fold("abcdef", limit=0), "")


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=0ad68e5c87148d7e049edeeee37653d8d17f6ad18d497ac534e8aa2c99456d95 ====
