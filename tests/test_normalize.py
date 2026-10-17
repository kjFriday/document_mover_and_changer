import unittest

from docpipe.enrich.normalize import LIMIT, fold


class FoldTest(unittest.TestCase):
    def test_scalars(self):
        self.assertEqual(fold(None), "")
        self.assertEqual(fold(True), "yes")
        self.assertEqual(fold(False), "no")
        self.assertEqual(fold(42), "42")
        self.assertEqual(fold(2.5), "2.5")

    def test_accents_keep_their_base_letter(self):
        self.assertEqual(fold("Caf\u00e9 Cr\u00e8me Br\u00fbl\u00e9e"),
                         "Cafe Creme Brulee")

    def test_typographic_punctuation(self):
        self.assertEqual(
            fold("\u201cQuoted\u201d \u2014 it\u2019s \u2018fine\u2019"),
            "\"Quoted\" - it's 'fine'")
        self.assertEqual(fold("3\u00d74 at 20\u00b0C"), "3x4 at 20 deg C")
        self.assertEqual(fold("2019\u20132020"), "2019-2020")

    def test_one_line_and_collapsed_whitespace(self):
        self.assertEqual(fold("  a\tb\n\nc   d\r\n"), "a b c d")

    def test_lists_and_tuples(self):
        self.assertEqual(fold(["Ann Lee", None, "Bo Park"]), "Ann Lee, Bo Park")
        self.assertEqual(fold(("x", True)), "x, yes")
        self.assertEqual(fold([]), "")

    def test_lossy_for_non_latin_text(self):
        # Why fold is for metadata only: letters with no ASCII form vanish.
        self.assertEqual(fold("\u6587\u66f8 report"), "report")

    def test_default_limit(self):
        out = fold("x" * 500)
        self.assertEqual(LIMIT, 240)
        self.assertEqual(len(out), 240)
        self.assertTrue(out.endswith("..."))

    def test_custom_limit(self):
        self.assertEqual(fold("abcdef", limit=5), "ab...")
        self.assertEqual(fold("abcdef", limit=6), "abcdef")
        self.assertEqual(fold("abcdef", limit=2), "ab")
        self.assertEqual(fold("abcdef", limit=0), "")


if __name__ == "__main__":
    unittest.main()
