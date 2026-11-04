# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_shape.py
# About: Tests for docpipe.enrich.shape: signatures, ranking, loaders, age() and the CLI.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for docpipe.enrich.shape: signatures, ranking, loaders, age() and the CLI.

Many tests feed deliberately broken files (NaN, infinity, wrong keys, wrong encodings) because one
bad number in a catalog or weights file would silently reorder every hint.
"""

import io
import json
import math
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from docpipe.enrich import shape
from docpipe.enrich.shape import (AGE_UNKNOWN, FALLBACK_WEIGHTS, Catalog,
                                  CatalogError, Exemplar, Signature, age,
                                  load_catalog, load_weights, nearest,
                                  profile, signature)

# Sample texts: TABLE and TABLE_LIKE are pipe-delimited rows with the same shape but different words;
# PROSE is one long line of ordinary sentence text. TABLE should rank TABLE_LIKE above PROSE.
TABLE = ["|ORDER|1042|SHIPPED|2026-03-01|",
         "|ORDER|1043|PENDING|2026-03-02|"]
TABLE_LIKE = ["|INVOICE|77|PAID|2026-02-11|",
              "|INVOICE|78|OPEN|2026-02-12|"]
PROSE = ["The quarterly summary describes how the team handled incoming "
         "requests and what changed in the second half of the year."]


class SignatureTest(unittest.TestCase):
    """signature() counts and profile() on edge input."""

    def test_counts_each_class(self):
        """The line "Hello World 42!" has 2 upper, 8 lower, 2 digits, 1 punctuation mark, 2 spaces and 3 tokens."""
        s =signature(["Hello World 42!"])
        self.assertEqual(s, Signature(lines=1, chars=15, upper=2, lower=8,
                                      digit=2, punct=1, space=2, tokens=3,
                                      mean_line=15.0))

    def test_caseless_letters_get_their_own_bucket(self):
        """Letters without case count as caseless, not as punctuation or as upper/lower."""
        # Japanese (2 letters) and Arabic (5 letters): neither has case.
        s = signature(["\u6587\u66f8 \u0645\u0631\u062d\u0628\u0627"])
        self.assertEqual(s.caseless, 7)
        self.assertEqual(s.punct, 0)
        self.assertEqual(s.upper + s.lower, 0)
        self.assertEqual(s.space, 1)

    def test_distinct_tokens_across_lines(self):
        """A token repeated on the same or another line counts once."""
        self.assertEqual(signature(["a b a", "b c"]).tokens, 3)

    def test_string_input_is_split_into_lines(self):
        """One string measures the same as its lines given as a list."""
        self.assertEqual(signature("one\ntwo 2\n"), signature(["one", "two 2"]))

    def test_line_endings_are_not_counted(self):
        """LF and CRLF endings on list items add no characters."""
        self.assertEqual(signature(["alpha beta\n", "gamma\r\n"]),
                         signature(["alpha beta", "gamma"]))

    def test_file_handle_matches_its_text(self):
        """An open file measures the same as its text read in one piece (15 characters, endings excluded)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("alpha beta\ngamma\n")
            with open(path, encoding="utf-8") as fh:
                from_handle = signature(fh)
            with open(path, encoding="utf-8") as fh:
                from_text = signature(fh.read())
        self.assertEqual(from_handle, from_text)
        self.assertEqual(from_handle.chars, 15)

    def test_empty_input(self):
        """No lines give an all-zero signature, and its profile divides by nothing (size is log10(10) = 1)."""
        s =signature([])
        self.assertEqual(s, Signature())
        p = profile(s)  # must not divide by zero
        self.assertTrue(all(v == 0 for k, v in p.items() if k != "size"))


class NearestTest(unittest.TestCase):
    """nearest(): ranking, weights fallback and the n cap."""

    def test_missing_weights_fall_back_rather_than_zero(self):
        """None and {} as weights both score with the fallback, so different shapes are not at distance 0."""
        # Scoring on an empty weight map would put every exemplar at distance
        # 0 and make every one equally similar.
        a = signature(["|A|B|C|"])
        b = signature(["a much longer line of ordinary prose words"])
        exemplars = [Exemplar(id=1, title="b", label="prose", signature=b)]
        for weights in (None, {}):
            with self.subTest(weights=weights):
                hits = nearest(a, exemplars, 1, weights)
                self.assertEqual(len(hits), 1)
                self.assertNotEqual(hits[0].distance, 0)

    def test_ranks_by_shape_not_by_order(self):
        """The table-like exemplar ranks first even though prose is listed first."""
        # Prose comes first, so a matcher that does not rank returns it.
        exemplars = [
            Exemplar(id=1, title="annual summary", label="prose",
                     signature=signature(PROSE)),
            Exemplar(id=2, title="invoice export", label="table",
                     signature=signature(TABLE_LIKE)),
        ]
        hits = nearest(signature(TABLE), exemplars, 2)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].exemplar.label, "table")
        self.assertLess(hits[0].distance, hits[1].distance)

    def test_identical_shape_is_distance_zero(self):
        """A signature compared with itself is at distance exactly 0."""
        s = signature(TABLE)
        hits = nearest(s, [Exemplar(id=1, title="t", label="t", signature=s)])
        self.assertEqual(hits[0].distance, 0)

    def test_n_caps_the_result(self):
        """At most n hits come back; n = 0 or no exemplars give an empty list."""
        s =signature(TABLE)
        ex = [Exemplar(id=i, title=str(i), label="t", signature=s)
              for i in range(5)]
        self.assertEqual(len(nearest(s, ex, 3)), 3)
        self.assertEqual(nearest(s, ex, 0), [])
        self.assertEqual(nearest(s, [], 3), [])


class WeightsTest(unittest.TestCase):
    """load_weights() on files written to a fresh temporary folder per test."""

    def setUp(self):
        """Make the temporary folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def _write(self, name, text, encoding="utf-8"):
        """Write text to a file called name in the given encoding; -> its path."""
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_none_returns_a_copy_of_the_fallback(self):
        """No file gives the fallback weights, as a copy: changing it leaves FALLBACK_WEIGHTS alone."""
        w =load_weights(None)
        self.assertEqual(w, FALLBACK_WEIGHTS)
        w["digit"] = 99.0
        self.assertEqual(FALLBACK_WEIGHTS["digit"], 1.4)

    def test_partial_file_keeps_fallback_for_missing_axes(self):
        """A file naming two axes changes those two (an integer reads as a float) and keeps the rest."""
        w =load_weights(self._write("w.json", '{"digit": 2, "size": 0.1}'))
        self.assertEqual(w["digit"], 2.0)
        self.assertEqual(w["size"], 0.1)
        self.assertEqual(w["caseless"], FALLBACK_WEIGHTS["caseless"])

    def test_bad_files_are_rejected(self):
        """Each case is refused with ValueError: not an object, unknown axis, a string, a boolean, broken
        JSON, NaN, infinity, a float or an integer too big to be finite, and a negative weight."""
        for name, text in (("list.json", "[1, 2]"),
                           ("axis.json", '{"digits": 1}'),
                           ("value.json", '{"digit": "high"}'),
                           ("bool.json", '{"digit": true}'),
                           ("broken.json", "{not json"),
                           ("nan.json", '{"digit": NaN}'),
                           ("inf.json", '{"digit": Infinity}'),
                           ("huge.json", '{"digit": 1e400}'),
                           ("bigint.json", '{"digit": %s}' % ("9" * 400)),
                           ("negative.json", '{"digit": -1}')):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    load_weights(self._write(name, text))

    def test_zero_weight_is_allowed(self):
        """A weight of 0 is valid: it switches that axis off."""
        self.assertEqual(load_weights(self._write("z.json",
                                                  '{"size": 0}'))["size"], 0)

    def test_byte_order_mark_is_accepted(self):
        """A UTF-8 file with a byte-order mark (as Windows tools write it) loads."""
        w = load_weights(self._write("bom.json", '{"digit": 2}', "utf-8-sig"))
        self.assertEqual(w["digit"], 2.0)

    def test_absent_file_raises(self):
        """A missing weights file raises FileNotFoundError, not the fallback."""
        with self.assertRaises(FileNotFoundError):
            load_weights(os.path.join(self.dir, "nope.json"))


class CatalogTest(unittest.TestCase):
    """load_catalog() on files written to a fresh temporary folder per test."""

    def setUp(self):
        """Make the temporary folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def _write(self, name, text, encoding="utf-8"):
        """Write text to a file called name in the given encoding; -> its path."""
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_absent_corrupt_and_empty_stay_distinct(self):
        """Missing is FileNotFoundError, broken JSON is CatalogError, and no exemplars is an empty Catalog."""
        with self.assertRaises(FileNotFoundError):
            load_catalog(os.path.join(self.dir, "nope.json"))

        with self.assertRaises(CatalogError) as ctx:
            load_catalog(self._write("bad.json", "{not json"))
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

        empty = load_catalog(self._write(
            "empty.json", '{"at": "2026-01-31T00:00:00+00:00"}'))
        self.assertEqual(empty, Catalog(at="2026-01-31T00:00:00+00:00"))

    def test_wrong_structure_is_corrupt(self):
        """Each case is JSON of the wrong shape or with a bad value, and must be CatalogError.

        Not an object, an exemplar that is not an object, a non-numeric count, overflowing and infinite
        counts, an infinite id, a NaN mean_line, a negative count, and "meanln" (the weights-file axis
        name) where the catalog needs the field name "mean_line".
        """
        for name, text in (("list.json", "[]"),
                           ("items.json", '{"exemplars": ["x"]}'),
                           ("count.json",
                            '{"exemplars": [{"signature": {"chars": "a"}}]}'),
                           ("huge.json",
                            '{"exemplars": [{"signature": {"lines": 1e400}}]}'),
                           ("inf.json", '{"exemplars": [{"signature": '
                                        '{"lines": Infinity}}]}'),
                           ("id.json", '{"exemplars": [{"id": Infinity}]}'),
                           ("nan.json", '{"exemplars": [{"signature": '
                                        '{"mean_line": NaN}}]}'),
                           ("negative.json", '{"exemplars": [{"signature": '
                                             '{"chars": -1}}]}'),
                           ("field.json", '{"exemplars": [{"signature": '
                                          '{"meanln": 30.0}}]}')):
            with self.subTest(name=name):
                with self.assertRaises(CatalogError):
                    load_catalog(self._write(name, text))

    def test_poisoned_exemplar_is_rejected_not_ranked(self):
        """One NaN among good exemplars rejects the whole catalog."""
        # A NaN between a far and a near exemplar would leave the exact match
        # ranked last, so the whole catalog is refused instead.
        near = asdict(signature(TABLE))
        doc = {"exemplars": [
            {"id": 1, "label": "prose", "signature": asdict(signature(PROSE))},
            {"id": 2, "label": "bad", "signature": dict(near,
                                                        mean_line=math.nan)},
            {"id": 3, "label": "table", "signature": near}]}
        with self.assertRaises(CatalogError):
            load_catalog(self._write("poisoned.json", json.dumps(doc)))

    def test_encodings(self):
        """UTF-8 with a byte-order mark loads; the same text in Latin-1 or UTF-16 is CatalogError."""
        # A non-ASCII character, so Latin-1 and UTF-16 bytes are not UTF-8.
        e_acute = chr(0xE9)
        text = '{"at": "%s", "exemplars": []}' % e_acute
        self.assertEqual(
            load_catalog(self._write("bom.json", text, "utf-8-sig")).at,
            e_acute)
        for encoding in ("latin-1", "utf-16"):
            with self.subTest(encoding=encoding):
                with self.assertRaises(CatalogError):
                    load_catalog(self._write(encoding + ".json", text,
                                             encoding))

    def test_round_trip(self):
        """A signature saved with asdict() loads back as an equal Exemplar, every field kept."""
        sig =signature(TABLE)
        doc = {"at": "2026-01-31T00:00:00Z",
               "exemplars": [{"id": 7, "title": "orders", "label": "table",
                              "path": "samples/orders.txt",
                              "signature": asdict(sig)}]}
        cat = load_catalog(self._write("cat.json", json.dumps(doc)))
        self.assertEqual(cat.exemplars, (
            Exemplar(id=7, title="orders", label="table", signature=sig,
                     path="samples/orders.txt"),))


class AgeTest(unittest.TestCase):
    """age() against a fixed "now", so the results never depend on the clock."""

    # the catalog time, and the same instant as an aware datetime to add deltas to
    AT = "2026-01-31T00:00:00+00:00"
    T0 = datetime(2026, 1, 31, tzinfo=timezone.utc)

    def test_buckets(self):
        """Seconds read "just now"; minutes, hours and days are whole units rounded down (3 h 59 min is 3 hours)."""
        for delta, want in ((timedelta(seconds=30), "written just now"),
                            (timedelta(minutes=5), "written 5 minute(s) ago"),
                            (timedelta(hours=3, minutes=59),
                             "written 3 hour(s) ago"),
                            (timedelta(days=2, hours=5),
                             "written 2 day(s) ago")):
            with self.subTest(delta=delta):
                self.assertEqual(age(self.AT, now=self.T0 + delta), want)

    def test_z_suffix(self):
        """A trailing "Z" is read as UTC."""
        self.assertEqual(age("2026-01-31T00:00:00Z",
                             now=self.T0 + timedelta(minutes=2)),
                         "written 2 minute(s) ago")

    def test_unreadable(self):
        """Empty, free text, a time with no offset and None all give AGE_UNKNOWN."""
        for at in ("", "yesterday", "2026-01-31T00:00:00", None):
            with self.subTest(at=at):
                self.assertEqual(age(at, now=self.T0), AGE_UNKNOWN)


class CommandLineTest(unittest.TestCase):
    """shape.main() called in this process with its output captured."""

    def setUp(self):
        """Make the temporary folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def _write(self, name, text):
        """Write text as UTF-8 to a file called name; -> its path."""
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _run(self, *argv):
        """Run shape.main(argv); -> (exit code, stdout text, stderr text)."""
        out, err =io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = shape.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_signature_and_hints(self):
        """Output lines in order: the signature JSON, the catalog's age and size, the weights note, then the
        hints nearest first (table before prose)."""
        doc =self._write("orders.txt", "\n".join(TABLE) + "\n")
        cat = self._write("cat.json", json.dumps({
            "at": "2026-01-31T00:00:00+00:00",
            "exemplars": [
                {"id": 1, "title": "annual summary", "label": "prose",
                 "signature": asdict(signature(PROSE))},
                {"id": 2, "title": "invoice export", "label": "table",
                 "signature": asdict(signature(TABLE_LIKE))},
            ]}))
        code, out, _ = self._run(doc, "--catalog", cat)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(json.loads(lines[0]), asdict(signature(TABLE)))
        self.assertIn("2 exemplar(s)", lines[1])
        self.assertIn("weights: built-in fallback", lines[2])
        self.assertIn("table", lines[3])
        self.assertIn("prose", lines[4])

    def test_absent_catalog_is_reported(self):
        """A missing catalog exits 1 with "not found" on stderr."""
        doc =self._write("a.txt", "x\n")
        code, _, err = self._run(doc, "--catalog",
                                 os.path.join(self.dir, "nope.json"))
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

    def test_absent_input_is_reported(self):
        """A missing input file exits 1, prints nothing on stdout and says "not found" on stderr."""
        code, out, err =self._run(os.path.join(self.dir, "nope.txt"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("not found", err)


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=9caa0635fb285974a25ef7335780866b3b6b642596d2346c71b1829a74eee56c ====
