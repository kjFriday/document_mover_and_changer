# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/store.py
# About: The shared database, opened by path: the pipeline's only link to the other programs.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""The shared database, opened by path: the pipeline's only link to the other programs.

The database is the Generic Company one that the CRUD hub creates and every program shares.

from_db() gives the same shape as source.from_mock() (the newest orders, their documents rows, all
customers and products). register() writes back what the run produced: a `documents` row for each
order that had none and one `documents.generated` event, in one transaction. The CRUD hub owns the
schema; this module only reads and inserts rows, and cleans every string with textsafe first.

docpipe.pipeline is the only caller. The flow of a run:

1. connect() opens the file by path, read-only unless the run registers; it never creates a file.
2. check_schema() confirms the tables and columns in NEEDS, so a different schema fails early and the
   caller can fall back to the mock snapshot.
3. from_db() reads the rows as plain dicts.
4. register(), only when asked, inserts the new rows and the event in one transaction.
"""

import json
import os
import sqlite3

from docpipe import textsafe

# The part of the hub's schema this program relies on: table -> the columns it reads or writes.
# Other tables and extra columns are ignored, so the hub can grow its schema freely.
NEEDS = {
    "orders": {"id", "customer_id", "product_id", "quantity", "total", "ordered_at"},
    "documents": {"id", "order_id", "kind", "path"},
    "customers": {"id", "name", "email", "city"},
    "products": {"id", "name", "category", "price"},
    "events": {"id", "kind", "payload", "status", "created_at"},
}
UNCAPPED = {"payload", "path"}  # machine data (JSON, file paths): cleaned, never cut short
ORDERS = 400  # newest orders a run reads by default: as many as the mock snapshot holds (tools/verify.ps1 expects 400)


class SchemaError(Exception):
    """The database lacks a table or column listed in NEEDS; the message names what is missing."""

    pass


def connect(path, readonly=False):
    """An open connection with busy_timeout and foreign keys; a missing file is an error, never created.

    Rows come back as sqlite3.Row, so columns can be read by name. Raises FileNotFoundError for a
    missing file and sqlite3.Error when SQLite cannot open it.

    Known limitation: the path goes into the URI without percent-encoding, so a path holding "#", "?"
    or "%" followed by two hex digits is misread.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    # a "file:" URI lets SQLite take a mode: ro refuses every write, and rw (unlike the default rwc)
    # refuses to create the file, so a mistyped path never leaves an empty database behind
    uri = "file:" + os.path.abspath(path).replace("\\", "/") + ("?mode=ro" if readonly else "?mode=rw")
    # timeout=5 and busy_timeout=5000 both mean: wait up to 5 s for another program's lock to clear
    # before failing with "database is locked"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    # SQLite checks FOREIGN KEY constraints only when this is on, per connection: a documents row
    # must name an order that exists
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def check_schema(conn):
    """Raise SchemaError unless every table and column the pipeline uses is there."""
    for table, cols in NEEDS.items():
        # PRAGMA table_info lists a table's columns, one row each with a "name", and returns no rows
        # at all for a table that does not exist. Pragmas take no bound parameters, so the name is
        # put in the text; that is safe only because it comes from NEEDS, never from input.
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:
            raise SchemaError(f"no {table} table")
        if cols - have:
            raise SchemaError(f"{table} lacks {', '.join(sorted(cols - have))}")


def _rows(conn, sql, args=()):
    """Run a query with bound args; -> its rows as plain dicts (column name -> value)."""
    return [dict(r) for r in conn.execute(sql, args)]


def from_db(conn, orders=ORDERS):
    """The newest `orders` orders (by id) and every document, customer and product row they need.

    -> {"orders", "documents", "customers", "products"}, each a list of row dicts, the same shape as
    source.from_mock(). The documents are those of the orders read; customers and products are read
    whole (both are small), not only the rows these orders name. Raises SchemaError first when NEEDS
    is not met.
    """
    check_schema(conn)
    data = {"orders": _rows(conn, "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (orders,))}
    ids = [o["id"] for o in data["orders"]]
    data["documents"] = []
    # one "?" per id; SQLite builds before 3.32 allow at most 999 bound parameters per statement
    for i in range(0, len(ids), 500):  # stay under SQLite's bound-parameter limit
        chunk = ids[i:i + 500]
        data["documents"] += _rows(conn, f"SELECT * FROM documents WHERE order_id IN ({','.join('?' * len(chunk))}) "
                                         "ORDER BY id DESC", chunk)
    data["customers"] = _rows(conn, "SELECT * FROM customers ORDER BY id DESC")
    data["products"] = _rows(conn, "SELECT * FROM products ORDER BY id DESC")
    return data


def _clean(column, value):
    """value ready to store in column: a string loses invisible control characters (textsafe.clean)
    and is cut to textsafe.LIMIT, unless the column is in UNCAPPED; anything else passes unchanged."""
    if isinstance(value, str):
        return textsafe.clean(value, None if column in UNCAPPED else textsafe.LIMIT)
    return value


def register(conn, manifest, digest, when):
    """Insert a documents row for each manifest entry without one (filling in its document_id) and one
    documents.generated event carrying digest(manifest) of the filled-in manifest; -> (rows made, event id).
    Running it again makes no new documents rows.

    manifest is build()'s list, changed in place; digest is pipeline.digest, passed in so this module
    need not import pipeline; when is the event's created_at text. The connection must be read-write.

    Steps:
    1. Open a transaction (`with conn` commits at the end, or rolls everything back on an error).
    2. For each entry without a document_id, reuse a row with the same order and path if there is one
       (that is what makes a rerun add nothing), else insert one, and write the id into the entry.
    3. Insert one documents.generated event whose payload counts the documents and new rows and
       carries the hash of the now filled-in manifest.
    """
    made = 0
    with conn:
        for m in manifest:
            if m["document_id"] is None:
                # compared with the cleaned path, since that is what an earlier run stored
                existing = conn.execute("SELECT id FROM documents WHERE order_id = ? AND path = ?",
                                        (m["order_id"], _clean("path", m["path"]))).fetchone()
                if existing:
                    m["document_id"] = existing["id"]
                    continue
                cur = conn.execute("INSERT INTO documents (order_id, kind, path) VALUES (?, ?, ?)",
                                   (m["order_id"], _clean("kind", m["kind"]), _clean("path", m["path"])))
                m["document_id"] = cur.lastrowid
                made += 1
        # status "sent" (the schema's default is "pending"): the notification hub's dispatcher only
        # takes "pending" events, so this one stays a record of the run and is never sent on
        payload = json.dumps({"documents": len(manifest), "registered": made, "manifest_sha256": digest(manifest)})
        cur = conn.execute("INSERT INTO events (kind, payload, status, created_at) VALUES (?, ?, ?, ?)",
                           ("documents.generated", _clean("payload", payload), "sent", _clean("created_at", when)))
    return made, cur.lastrowid  # cur is the event insert's cursor here, so this is the event id

# ==== stamp v1 | author=kjFriday | hmac-sha256=049f3779798cbd34233065b703041aa38fae64d0a6877ecd9efa2de1f5ac8570 ====
