import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from dbfixture import mock_db
from docpipe import source
from docpipe.__main__ import main
from docpipe.output.documents import build, default_path, money, render

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "..", "mock")

ORDER = {"id": 7, "customer_id": 1, "product_id": 2, "quantity": 3, "total": 0.30, "ordered_at": "2026-04-05T10:11"}
CUSTOMER = {"id": 1, "name": "Zoë Müller", "email": "zoe.muller@mail.example", "city": "Lyon"}
PRODUCT = {"id": 2, "name": "Rust Toolkit"}


class RenderTest(unittest.TestCase):
    def test_money_is_exact(self):
        self.assertEqual(money(0.1 + 0.2), "0.30")
        self.assertEqual(money(None), "0.00")
        self.assertEqual(money(2.675), "2.68")

    def test_invoice_layout(self):
        text = render("invoice", ORDER, CUSTOMER, PRODUCT)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("ACME Inc.") and lines[0].endswith("INVOICE"))
        self.assertIn("Customer   Zoe Muller", text)  # folded to ASCII
        self.assertIn("Rust Toolkit", text)
        self.assertTrue(lines[11].endswith("0.30") and "0.10" in lines[9])
        self.assertTrue(text.isascii())

    def test_kinds_differ(self):
        self.assertIn("Paid in full", render("receipt", ORDER, CUSTOMER, PRODUCT))
        slip = render("packing_slip", ORDER, CUSTOMER, PRODUCT)
        self.assertNotIn("0.30", slip)
        self.assertIn("Unknown customer", render("invoice", ORDER, None, None))

    def test_default_path(self):
        self.assertEqual(default_path(ORDER), "invoices/2026/04/INV-000007.txt")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def data(self, documents):
        return {"orders": [ORDER, dict(ORDER, id=8)], "documents": documents, "customers": [CUSTOMER], "products": [PRODUCT]}

    def test_writes_rows_and_fills_gaps(self):
        manifest, missing = build(self.data([{"id": 1, "order_id": 7, "kind": "receipt", "path": "receipts/a.txt"}]), self.out)
        self.assertEqual(missing, [8])
        self.assertEqual([m["path"] for m in manifest], ["invoices/2026/04/INV-000008.txt", "receipts/a.txt"])
        self.assertTrue(all(len(m["sha256"]) == 64 for m in manifest))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "receipts", "a.txt")))

    def test_same_input_same_hashes(self):
        a, _ = build(self.data([]), self.out)
        b, _ = build(self.data([]), self.out)
        self.assertEqual(a, b)

    def test_path_cannot_escape(self):
        with self.assertRaises(ValueError):
            build(self.data([{"id": 1, "order_id": 7, "kind": "invoice", "path": "../../evil.txt"}]), self.out)

    def test_mock_snapshot(self):
        data = source.from_mock(MOCK)
        manifest, missing = build(data, self.out)
        self.assertEqual(len(manifest), len(data["documents"]))
        self.assertEqual(missing, [])



class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_mock_mode(self):
        out = os.path.join(self.tmp, "out")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(main(["--cli", "--mock", MOCK, "--out", out]), 0)
        self.assertIn("source: mock snapshot", buf.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(out, "manifest.jsonl")))

    def test_database_mode_registers(self):
        db = mock_db(self.tmp, {"orders": [ORDER], "customers": [CUSTOMER], "products": [dict(PRODUCT, category="Tools", price=0.1)]})
        out = os.path.join(self.tmp, "out")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(main(["--cli", "--db", db, "--out", out, "--register"]), 0)
        self.assertIn("1 documents rows added", buf.getvalue())
        with open(os.path.join(out, "manifest.jsonl"), encoding="utf-8") as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["path"], "invoices/2026/04/INV-000007.txt")
        self.assertEqual(entry["document_id"], 1)  # the new row's id reaches the manifest

    def test_register_needs_a_database(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["--cli", "--db", os.path.join(self.tmp, "none.db"), "--out", self.tmp, "--register"]), 1)
        self.assertIn("needs the shared database", err.getvalue())


if __name__ == "__main__":
    unittest.main()