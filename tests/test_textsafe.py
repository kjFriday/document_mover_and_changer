# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_textsafe.py
# About: Tests for textsafe.clean.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for textsafe.clean.

Each class of refused character is checked one code point at a time, so a gap in a range shows
up with its hex value; ordinary text in several scripts must pass unchanged.
"""

import unittest

from docpipe.textsafe import LIMIT, clean

ESC = "\x1b"
CSI = "\x9b"  # the single-character form of ESC [


class CleanTest(unittest.TestCase):
    """What clean() removes, keeps and cuts."""

    def test_both_spellings_of_csi_are_removed(self):
        """ESC [ (two characters) and U+009B (one) both start a terminal command; only the starter is removed."""
        self.assertEqual(clean(ESC + "[2Jinvoice"), "[2Jinvoice")
        self.assertEqual(clean(CSI + "2Jinvoice"), "2Jinvoice")

    def test_del_and_whole_c1_block_are_removed(self):
        """U+007F (DEL) through U+009F, every one."""
        for c in range(0x7F, 0xA0):
            self.assertEqual(clean("a" + chr(c) + "b"), "ab", hex(c))

    def test_c0_controls_are_removed_except_tab_and_newline(self):
        """U+0000-U+001F are removed, except tab and newline (carriage return goes too)."""
        for c in range(0x20):
            want = "a" + chr(c) + "b" if chr(c) in "\t\n" else "ab"
            self.assertEqual(clean("a" + chr(c) + "b"), want, hex(c))

    def test_separators_and_bidi_controls_are_removed(self):
        """The line/paragraph separators and every bidi control, inside an otherwise plain string."""
        for c in [0x2028, 0x2029, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]:
            self.assertEqual(clean("order" + chr(c) + "42"), "order42", hex(c))

    def test_ordinary_text_is_untouched(self):
        """Accents, a multiplication sign, CJK, an emoji outside the BMP, tab and newline all pass."""
        plain = "Order 1042 for Zoë Müller: 3 × Widget, 東京 office \U0001F4E6\tnote\nline two"
        self.assertEqual(clean(plain), plain)

    def test_length_is_capped_after_removal(self):
        """The default cap is LIMIT, a given limit wins, removed characters do not count, None means no cap."""
        self.assertEqual(len(clean("x" * 500)), LIMIT)
        self.assertEqual(clean("abcdef", limit=3), "abc")
        self.assertEqual(clean(ESC * 300 + "ok"), "ok")
        self.assertEqual(len(clean("y" * 500, limit=None)), 500)

    def test_zero_or_negative_limit_gives_empty(self):
        """A negative limit gives "", not a slice counted from the end."""
        self.assertEqual(clean("hello", limit=0), "")
        self.assertEqual(clean("hello", limit=-1), "")
        self.assertEqual(clean("hello", limit=-2), "")

    def test_none_becomes_empty(self):
        """None is cleaned to "" rather than raising."""
        self.assertEqual(clean(None), "")


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=07a1f09c076a47dfabcbf7bf0b9a059189e9782110cb1c587c377cdfed6f07e0 ====
