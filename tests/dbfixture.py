# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/dbfixture.py
# About: A real SQLite database with the hub's exact schema (mock/schema.sql) for tests.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""A real SQLite database with the hub's exact schema (mock/schema.sql) for tests.

test_store.py and test_documents.py import it as a top-level module (`from dbfixture import ...`),
which works because `python -m unittest discover -s tests` puts tests/ on sys.path. Testing against a
real file with the real schema catches what a hand-written stand-in would miss: column names,
foreign keys, read-only opening.
"""

import json
import os
import sqlite3

# This folder, and the bundled snapshot beside it: the hub's schema.sql and its <table>.json rows.
HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "..", "mock")


def mock_db(folder, tables=None):
    """generic_company.db in folder, built from mock/schema.sql and filled with `tables` ({table: rows}),
    or with the whole mock snapshot when tables is None; -> its path."""
    path = os.path.join(folder, "generic_company.db")
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
            # table and column names cannot be bound parameters; they come from test data, never input
            cols = list(row)
            conn.execute(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         [row[c] for c in cols])
    conn.commit()
    conn.close()
    return path

# ==== stamp v1 | author=kjFriday | hmac-sha256=bc3ecdbbaa1b04dcb5bf7aa991a32885345f3912420ce71a4c815c67d3e3e944 ====
