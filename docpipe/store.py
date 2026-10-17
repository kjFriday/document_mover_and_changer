"""The shared ACME database, opened by path: the pipeline's only link to the other programs.

from_db() gives the same shape as source.from_mock() (the newest orders, their documents rows, all
customers and products). register() writes back what the run produced: a `documents` row for each
order that had none and one `documents.generated` event, in one transaction. The CRUD hub owns the
schema; this module only reads and inserts rows, and cleans every string with textsafe first.
"""

import json
import os
import sqlite3

from docpipe import textsafe

NEEDS = {
    "orders": {"id", "customer_id", "product_id", "quantity", "total", "ordered_at"},
    "documents": {"id", "order_id", "kind", "path"},
    "customers": {"id", "name", "email", "city"},
    "products": {"id", "name", "category", "price"},
    "events": {"id", "kind", "payload", "status", "created_at"},
}
UNCAPPED = {"payload", "path"}  # machine data (JSON, file paths): cleaned, never cut short


class SchemaError(Exception):
    pass


def connect(path, readonly=False):
    """An open connection with busy_timeout and foreign keys; a missing file is an error, never created."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    uri = "file:" + os.path.abspath(path).replace("\\", "/") + ("?mode=ro" if readonly else "?mode=rw")
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def check_schema(conn):
    """Raise SchemaError unless every table and column the pipeline uses is there."""
    for table, cols in NEEDS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:
            raise SchemaError(f"no {table} table")
        if cols - have:
            raise SchemaError(f"{table} lacks {', '.join(sorted(cols - have))}")


def _rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args)]


def from_db(conn, orders=400):
    """The newest `orders` orders (by id) and every document, customer and product row they need."""
    check_schema(conn)
    data = {"orders": _rows(conn, "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (orders,))}
    ids = [o["id"] for o in data["orders"]]
    data["documents"] = []
    for i in range(0, len(ids), 500):  # stay under SQLite's bound-parameter limit
        chunk = ids[i:i + 500]
        data["documents"] += _rows(conn, f"SELECT * FROM documents WHERE order_id IN ({','.join('?' * len(chunk))}) "
                                         "ORDER BY id DESC", chunk)
    data["customers"] = _rows(conn, "SELECT * FROM customers ORDER BY id DESC")
    data["products"] = _rows(conn, "SELECT * FROM products ORDER BY id DESC")
    return data


def _clean(column, value):
    if isinstance(value, str):
        return textsafe.clean(value, None if column in UNCAPPED else textsafe.LIMIT)
    return value


def register(conn, manifest, digest, when):
    """Insert a documents row for each manifest entry without one (filling in its document_id) and one
    documents.generated event carrying digest(manifest) of the filled-in manifest; -> (rows made, event id).
    Running it again makes no new documents rows."""
    made = 0
    with conn:
        for m in manifest:
            if m["document_id"] is None:
                existing = conn.execute("SELECT id FROM documents WHERE order_id = ? AND path = ?",
                                        (m["order_id"], _clean("path", m["path"]))).fetchone()
                if existing:
                    m["document_id"] = existing["id"]
                    continue
                cur = conn.execute("INSERT INTO documents (order_id, kind, path) VALUES (?, ?, ?)",
                                   (m["order_id"], _clean("kind", m["kind"]), _clean("path", m["path"])))
                m["document_id"] = cur.lastrowid
                made += 1
        payload = json.dumps({"documents": len(manifest), "registered": made, "manifest_sha256": digest(manifest)})
        cur = conn.execute("INSERT INTO events (kind, payload, status, created_at) VALUES (?, ?, ?, ?)",
                           ("documents.generated", _clean("payload", payload), "sent", _clean("created_at", when)))
    return made, cur.lastrowid
