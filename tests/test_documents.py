# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_documents.py
# About: Tests for docpipe.output.documents and the --cli console run.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for docpipe.output.documents and the --cli console run.

RenderTest pins the text of one document, BuildTest the files and manifest of a run (gap filling,
determinism, the path-escape guard, the whole mock snapshot), and CliTest the console mode against
the snapshot and against a real SQLite database built by dbfixture.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from dbfixture import MOCK, mock_db
from docpipe import source
from docpipe.__main__ import main
from docpipe.output.documents import build, default_path, money, render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder, which holds docpipe/
# One order, its customer and its product. The accented name proves folding to ASCII; a total of
# 0.30 for 3 items gives a unit price of exactly 0.10, and 0.30 is a sum floats get wrong.
ORDER ={"id": 7, "customer_id": 1, "product_id": 2, "quantity": 3, "total": 0.30, "ordered_at": "2026-04-05T10:11"}
CUSTOMER = {"id": 1, "name": "Zoë Müller", "email": "zoe.muller@mail.example", "city": "Lyon"}
PRODUCT = {"id": 2, "name": "Rust Toolkit"}


class RenderTest(unittest.TestCase):
    """money(), render() and default_path() on the fixed order above."""

    def test_money_is_exact(self):
        """0.1 + 0.2 shows as 0.30, None as 0.00, and 2.675 (2.67499... in binary) rounds half up to 2.68."""
        self.assertEqual(money(0.1 + 0.2), "0.30")
        self.assertEqual(money(None), "0.00")
        self.assertEqual(money(2.675), "2.68")

    def test_invoice_layout(self):
        """An invoice has its heading, the folded customer name, the item, unit and total, and is pure ASCII.

        lines[9] is the item row and lines[11] the total, so this also pins render()'s line order.
        """
        text = render("invoice", ORDER, CUSTOMER, PRODUCT)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("Generic Company Inc.") and lines[0].endswith("INVOICE"))
        self.assertIn("Customer   Zoe Muller", text)  # folded to ASCII
        self.assertIn("Rust Toolkit", text)
        self.assertTrue(lines[11].endswith("0.30") and "0.10" in lines[9])
        self.assertTrue(text.isascii())

    def test_kinds_differ(self):
        """A receipt says it is paid, a packing slip shows no prices, and missing rows read as unknown."""
        self.assertIn("Paid in full", render("receipt", ORDER, CUSTOMER, PRODUCT))
        slip = render("packing_slip", ORDER, CUSTOMER, PRODUCT)
        self.assertNotIn("0.30", slip)
        self.assertIn("Unknown customer", render("invoice", ORDER, None, None))

    def test_default_path(self):
        """A new invoice's path follows the hub seed's layout: kind folder, year, month, zero-padded id."""
        self.assertEqual(default_path(ORDER), "invoices/2026/04/INV-000007.txt")


class BuildTest(unittest.TestCase):
    """build() writing into a fresh temporary folder per test."""

    def setUp(self):
        """Make the temporary output folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.out = self._tmp.name

    def tearDown(self):
        """Delete the output folder and everything written to it."""
        self._tmp.cleanup()

    def data(self, documents):
        """Run data for orders 7 and 8 with the given documents rows."""
        return {"orders": [ORDER, dict(ORDER, id=8)], "documents": documents, "customers": [CUSTOMER], "products": [PRODUCT]}

    def test_writes_rows_and_fills_gaps(self):
        """Order 7's stored receipt is written at its path, and order 8, with no row, gets a default invoice."""
        manifest, missing = build(self.data([{"id": 1, "order_id": 7, "kind": "receipt", "path": "receipts/a.txt"}]), self.out)
        self.assertEqual(missing, [8])
        self.assertEqual([m["path"] for m in manifest], ["invoices/2026/04/INV-000008.txt", "receipts/a.txt"])
        self.assertTrue(all(len(m["sha256"]) == 64 for m in manifest))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "receipts", "a.txt")))

    def test_same_input_same_hashes(self):
        """Two builds of the same data give identical manifests, hashes included."""
        a, _ = build(self.data([]), self.out)
        b, _ = build(self.data([]), self.out)
        self.assertEqual(a, b)

    def test_path_cannot_escape(self):
        """A stored path that climbs out of the output folder raises ValueError."""
        with self.assertRaises(ValueError):
            build(self.data([{"id": 1, "order_id": 7, "kind": "invoice", "path": "../../evil.txt"}]), self.out)

    def test_mock_snapshot(self):
        """The bundled snapshot builds one file per documents row, and every order there already has a row."""
        data = source.from_mock(MOCK)
        manifest, missing = build(data, self.out)
        self.assertEqual(len(manifest), len(data["documents"]))
        self.assertEqual(missing, [])


class CliTest(unittest.TestCase):
    """main(["--cli", ...]) in this process, plus one run in a fresh interpreter."""

    def setUp(self):
        """Make a temporary folder for the database and the output."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def test_mock_mode(self):
        """--mock reads the snapshot, says so, and writes manifest.jsonl."""
        out = os.path.join(self.tmp, "out")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(main(["--cli", "--mock", MOCK, "--out", out]), 0)
        self.assertIn("source: mock snapshot", buf.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(out, "manifest.jsonl")))

    def test_database_mode_registers(self):
        """--register on a database with one order and no documents adds one row, and its id reaches the manifest.

        The database is new, so the first documents row gets id 1.
        """
        db =mock_db(self.tmp, {"orders": [ORDER], "customers": [CUSTOMER], "products": [dict(PRODUCT, category="Tools", price=0.1)]})
        out = os.path.join(self.tmp, "out")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(main(["--cli", "--db", db, "--out", out, "--register"]), 0)
        self.assertIn("1 documents rows added", buf.getvalue())
        with open(os.path.join(out, "manifest.jsonl"), encoding="utf-8") as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["path"], "invoices/2026/04/INV-000007.txt")
        self.assertEqual(entry["document_id"], 1)  # the new row's id reaches the manifest

    def test_register_needs_a_database(self):
        """--register with a database path that does not exist exits 1 and explains why on stderr."""
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["--cli", "--db", os.path.join(self.tmp, "none.db"), "--out", self.tmp, "--register"]), 1)
        self.assertIn("needs the shared database", err.getvalue())

    def test_console_run_loads_no_window_code(self):
        """--cli imports neither tkinter nor docpipe.gui (checked in a fresh interpreter: this suite loads both)."""
        code = ("import contextlib, io, json, sys\n"
                "from docpipe.__main__ import main\n"
                "with contextlib.redirect_stdout(io.StringIO()):\n"
                "    status = main(sys.argv[1:])\n"
                "loaded = [name for name in ('tkinter', 'docpipe.gui') if name in sys.modules]\n"
                "print(json.dumps({'exit': status, 'loaded': loaded}))\n")
        proc = subprocess.run([sys.executable, "-c", code, "--cli", "--mock", MOCK, "--out", os.path.join(self.tmp, "out")],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"exit": 0, "loaded": []})


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=41b4b6499e2dfa131d908a2aec837257f3627f0b9ed30b393c2a5a1bbd65f307 ====
