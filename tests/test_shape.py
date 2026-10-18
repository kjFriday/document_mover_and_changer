# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: tests/test_shape.py
# About: Tests for shape.py.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

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

TABLE = ["|ORDER|1042|SHIPPED|2026-03-01|",
         "|ORDER|1043|PENDING|2026-03-02|"]
TABLE_LIKE = ["|INVOICE|77|PAID|2026-02-11|",
              "|INVOICE|78|OPEN|2026-02-12|"]
PROSE = ["The quarterly summary describes how the team handled incoming "
         "requests and what changed in the second half of the year."]


class SignatureTest(unittest.TestCase):
    def test_counts_each_class(self):
        s = signature(["Hello World 42!"])
        self.assertEqual(s, Signature(lines=1, chars=15, upper=2, lower=8,
                                      digit=2, punct=1, space=2, tokens=3,
                                      mean_line=15.0))

    def test_caseless_letters_get_their_own_bucket(self):
        # Japanese (2 letters) and Arabic (5 letters): neither has case.
        s = signature(["\u6587\u66f8 \u0645\u0631\u062d\u0628\u0627"])
        self.assertEqual(s.caseless, 7)
        self.assertEqual(s.punct, 0)
        self.assertEqual(s.upper + s.lower, 0)
        self.assertEqual(s.space, 1)

    def test_distinct_tokens_across_lines(self):
        self.assertEqual(signature(["a b a", "b c"]).tokens, 3)

    def test_string_input_is_split_into_lines(self):
        self.assertEqual(signature("one\ntwo 2\n"), signature(["one", "two 2"]))

    def test_line_endings_are_not_counted(self):
        self.assertEqual(signature(["alpha beta\n", "gamma\r\n"]),
                         signature(["alpha beta", "gamma"]))

    def test_file_handle_matches_its_text(self):
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
        s = signature([])
        self.assertEqual(s, Signature())
        p = profile(s)  # must not divide by zero
        self.assertTrue(all(v == 0 for k, v in p.items() if k != "size"))


class NearestTest(unittest.TestCase):
    def test_missing_weights_fall_back_rather_than_zero(self):
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
        s = signature(TABLE)
        hits = nearest(s, [Exemplar(id=1, title="t", label="t", signature=s)])
        self.assertEqual(hits[0].distance, 0)

    def test_n_caps_the_result(self):
        s = signature(TABLE)
        ex = [Exemplar(id=i, title=str(i), label="t", signature=s)
              for i in range(5)]
        self.assertEqual(len(nearest(s, ex, 3)), 3)
        self.assertEqual(nearest(s, ex, 0), [])
        self.assertEqual(nearest(s, [], 3), [])


class WeightsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text, encoding="utf-8"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_none_returns_a_copy_of_the_fallback(self):
        w = load_weights(None)
        self.assertEqual(w, FALLBACK_WEIGHTS)
        w["digit"] = 99.0
        self.assertEqual(FALLBACK_WEIGHTS["digit"], 1.4)

    def test_partial_file_keeps_fallback_for_missing_axes(self):
        w = load_weights(self._write("w.json", '{"digit": 2, "size": 0.1}'))
        self.assertEqual(w["digit"], 2.0)
        self.assertEqual(w["size"], 0.1)
        self.assertEqual(w["caseless"], FALLBACK_WEIGHTS["caseless"])

    def test_bad_files_are_rejected(self):
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
        self.assertEqual(load_weights(self._write("z.json",
                                                  '{"size": 0}'))["size"], 0)

    def test_byte_order_mark_is_accepted(self):
        w = load_weights(self._write("bom.json", '{"digit": 2}', "utf-8-sig"))
        self.assertEqual(w["digit"], 2.0)

    def test_absent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_weights(os.path.join(self.dir, "nope.json"))


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text, encoding="utf-8"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_absent_corrupt_and_empty_stay_distinct(self):
        with self.assertRaises(FileNotFoundError):
            load_catalog(os.path.join(self.dir, "nope.json"))

        with self.assertRaises(CatalogError) as ctx:
            load_catalog(self._write("bad.json", "{not json"))
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

        empty = load_catalog(self._write(
            "empty.json", '{"at": "2026-01-31T00:00:00+00:00"}'))
        self.assertEqual(empty, Catalog(at="2026-01-31T00:00:00+00:00"))

    def test_wrong_structure_is_corrupt(self):
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
        sig = signature(TABLE)
        doc = {"at": "2026-01-31T00:00:00Z",
               "exemplars": [{"id": 7, "title": "orders", "label": "table",
                              "path": "samples/orders.txt",
                              "signature": asdict(sig)}]}
        cat = load_catalog(self._write("cat.json", json.dumps(doc)))
        self.assertEqual(cat.exemplars, (
            Exemplar(id=7, title="orders", label="table", signature=sig,
                     path="samples/orders.txt"),))


class AgeTest(unittest.TestCase):
    AT = "2026-01-31T00:00:00+00:00"
    T0 = datetime(2026, 1, 31, tzinfo=timezone.utc)

    def test_buckets(self):
        for delta, want in ((timedelta(seconds=30), "written just now"),
                            (timedelta(minutes=5), "written 5 minute(s) ago"),
                            (timedelta(hours=3, minutes=59),
                             "written 3 hour(s) ago"),
                            (timedelta(days=2, hours=5),
                             "written 2 day(s) ago")):
            with self.subTest(delta=delta):
                self.assertEqual(age(self.AT, now=self.T0 + delta), want)

    def test_z_suffix(self):
        self.assertEqual(age("2026-01-31T00:00:00Z",
                             now=self.T0 + timedelta(minutes=2)),
                         "written 2 minute(s) ago")

    def test_unreadable(self):
        for at in ("", "yesterday", "2026-01-31T00:00:00", None):
            with self.subTest(at=at):
                self.assertEqual(age(at, now=self.T0), AGE_UNKNOWN)


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = shape.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_signature_and_hints(self):
        doc = self._write("orders.txt", "\n".join(TABLE) + "\n")
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
        doc = self._write("a.txt", "x\n")
        code, _, err = self._run(doc, "--catalog",
                                 os.path.join(self.dir, "nope.json"))
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

    def test_absent_input_is_reported(self):
        code, out, err = self._run(os.path.join(self.dir, "nope.txt"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("not found", err)


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=c31864937fcdd1063c798a5a8a381a1618da0ae037cc6c9faf9bd5fed2bb0a14 ====
