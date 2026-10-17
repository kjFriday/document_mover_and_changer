import json
import os
import sqlite3
import tempfile
import unittest

from dbfixture import MOCK, mock_db
from docpipe import pipeline, source, store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_db_matches_the_mock_snapshot(self):
        conn = store.connect(mock_db(self.tmp), readonly=True)
        try:
            data = store.from_db(conn, 400)
        finally:
            conn.close()
        mock = source.from_mock(MOCK)
        key = lambda r: r["id"]  # noqa: E731
        for table in source.TABLES:
            self.assertEqual(sorted(data[table], key=key), sorted(mock[table], key=key), table)

    def test_missing_file_and_bad_schema(self):
        with self.assertRaises(FileNotFoundError):
            store.connect(os.path.join(self.tmp, "nope.db"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "nope.db")))  # never created
        bad = os.path.join(self.tmp, "bad.db")
        sqlite3.connect(bad).execute("CREATE TABLE orders (id INTEGER)").connection.close()
        conn = store.connect(bad)
        try:
            with self.assertRaises(store.SchemaError):
                store.check_schema(conn)
        finally:
            conn.close()

    def test_register_once_and_clean(self):
        db = mock_db(self.tmp, {"customers": [{"id": 1, "name": "A"}], "products": [{"id": 2, "name": "P"}],
                                "orders": [{"id": 7, "customer_id": 1, "product_id": 2, "ordered_at": "2026-04-05T10:11"}]})
        manifest = [{"document_id": None, "order_id": 7, "kind": "invoice‮", "path": "invoices/x.txt", "sha256": "0" * 64}]
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
        db = mock_db(self.tmp)
        before = os.path.getmtime(db)
        result = pipeline.run(os.path.join(self.tmp, "out"), db_path=db, orders=50)
        self.assertEqual((result["source"], result["orders"], result["event"]), ("db", 50, None))
        self.assertEqual(os.path.getmtime(db), before)


if __name__ == "__main__":
    unittest.main()
