"""A real SQLite database with the hub's exact schema (mock/schema.sql) for tests."""

import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "..", "mock")


def mock_db(folder, tables=None):
    """acme.db in folder, built from mock/schema.sql and filled with `tables` ({table: rows}),
    or with the whole mock snapshot when tables is None; -> its path."""
    path = os.path.join(folder, "acme.db")
    conn = sqlite3.connect(path)
    with open(os.path.join(MOCK, "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    if tables is None:
        tables = {}
        for name in ("customers", "products", "orders", "documents"):
            with open(os.path.join(MOCK, f"{name}.json"), encoding="utf-8") as f:
                tables[name] = json.load(f)
    for name, rows in tables.items():
        for row in rows:
            cols = list(row)
            conn.execute(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         [row[c] for c in cols])
    conn.commit()
    conn.close()
    return path
