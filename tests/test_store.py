# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_store.py
# About: Tests for docpipe.store, and for pipeline.run() against a real SQLite database.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for docpipe.store, and for pipeline.run() against a real SQLite database.

Each test builds generic_company.db from the hub's schema with dbfixture, in a fresh temporary
folder, so nothing outside it is read or written.
"""

import json
import os
import sqlite3
import tempfile
import unittest

from dbfixture import MOCK, mock_db
from docpipe import pipeline, source, store


class StoreTest(unittest.TestCase):
    """connect, check_schema, from_db and register on throwaway databases."""

    def setUp(self):
        """Make the temporary folder for the database."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def test_db_matches_the_mock_snapshot(self):
        """A database filled from the snapshot reads back (400 orders) as exactly the snapshot, table by table."""
        conn =store.connect(mock_db(self.tmp), readonly=True)
        try:
            data = store.from_db(conn, 400)
        finally:
            conn.close()
        mock = source.from_mock(MOCK)
        key = lambda r: r["id"]  # noqa: E731
        for table in source.TABLES:
            self.assertEqual(sorted(data[table], key=key), sorted(mock[table], key=key), table)

    def test_missing_file_and_bad_schema(self):
        """A missing file raises and is not created; a database with an incomplete orders table fails check_schema."""
        with self.assertRaises(FileNotFoundError):
            store.connect(os.path.join(self.tmp, "nope.db"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "nope.db")))  # never created
        bad = os.path.join(self.tmp, "bad.db")
        # a database whose only table is an orders table with one column
        sqlite3.connect(bad).execute("CREATE TABLE orders (id INTEGER)").connection.close()
        conn = store.connect(bad)
        try:
            with self.assertRaises(store.SchemaError):
                store.check_schema(conn)
        finally:
            conn.close()

    def test_register_once_and_clean(self):
        """register adds one row and one event, strips a bidi control from the kind, and a second call
        reuses the row (0 new rows, the same id) while still adding its own event.

        The kind ends in U+202E (RIGHT-TO-LEFT OVERRIDE), written as an escape so it stays visible here.
        """
        db =mock_db(self.tmp, {"customers": [{"id": 1, "name": "A"}], "products": [{"id": 2, "name": "P"}],
                                "orders": [{"id": 7, "customer_id": 1, "product_id": 2, "ordered_at": "2026-04-05T10:11"}]})
        manifest = [{"document_id": None, "order_id": 7, "kind": "invoice\u202e", "path": "invoices/x.txt", "sha256": "0" * 64}]
        conn = store.connect(db)
        try:
            made, event = store.register(conn, manifest, pipeline.digest, "2026-10-17T09:00")
            self.assertEqual(made, 1)
            self.assertEqual(conn.execute("SELECT kind FROM documents").fetchone()[0], "invoice")  # bidi control removed
            again = [dict(manifest[0], document_id=None)]
            self.assertEqual(store.register(conn, again, pipeline.digest, "2026-10-17T09:05")[0], 0)
            self.assertEqual(again[0]["document_id"], manifest[0]["document_id"])
            events = conn.execute("SELECT kind, payload, status FROM events ORDER BY id").fetchall()
        finally:
            conn.close()
        self.assertEqual([e["kind"] for e in events], ["documents.generated"] * 2)
        self.assertEqual(json.loads(events[0]["payload"])["registered"], 1)
        self.assertEqual(events[0]["status"], "sent")
        self.assertNotEqual(event, None)

    def test_readonly_run_leaves_the_database_alone(self):
        """A run without register reads 50 orders, records no event, and leaves the file's mtime unchanged."""
        db =mock_db(self.tmp)
        before = os.path.getmtime(db)
        result = pipeline.run(os.path.join(self.tmp, "out"), db_path=db, orders=50)
        self.assertEqual((result["source"], result["orders"], result["event"]), ("db", 50, None))
        self.assertEqual(os.path.getmtime(db), before)


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=9ff6e95838b1984c0eec00b9506bf92a965461f210b428707c67344601fbd135 ====
