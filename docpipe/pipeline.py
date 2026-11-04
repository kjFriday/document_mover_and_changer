# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/pipeline.py
# About: One pipeline run for window and console: rows in, document files and manifest out.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""One pipeline run for window and console: rows in, document files and manifest out.

docpipe.__main__ (--cli) and docpipe.gui both call describe_source() to pick the source and run() to
do the work. run() calls docpipe.store or docpipe.source for the rows, docpipe.output.documents.build()
for the files, and store.register() when asked to record the run.

The manifest file is JSON Lines: one JSON object per line, keys sorted, "\\n" endings. digest() is the
SHA-256 of exactly those bytes, so the hash in the summary, the event and the file always agree.
Start reading at run().
"""

import hashlib
import json
import os
from datetime import datetime

from docpipe import source, store
from docpipe.output.documents import build

# The project folder, which holds docpipe/ and mock/.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK =os.path.join(HERE, "mock")  # the bundled snapshot, beside the package (also in an installed copy)
ORDERS = store.ORDERS  # the default order count; store holds the value because it cannot import this module


def describe_source(db_path, force_mock=False):
    """("db", path) when the shared database is usable, else ("mock", why).

    Usable means the file exists, opens read-only and has every table and column store.NEEDS lists.
    force_mock (--mock) skips the check. It never raises: any failure becomes the reason text, which
    the window's badge and the console summary show.
    """
    if force_mock:
        return "mock", "mock snapshot (--mock)"
    if not os.path.isfile(db_path):
        return "mock", f"mock snapshot — no database at {db_path}"
    try:
        conn = store.connect(db_path, readonly=True)
        try:
            store.check_schema(conn)
        finally:
            conn.close()
    except Exception as e:  # missing tables, locked, not a database
        return "mock", f"mock snapshot — {db_path}: {e}"
    return "db", db_path


def manifest_lines(manifest):
    """The manifest as JSON Lines text: one object per entry, keys sorted, each line ending in "\\n".

    Sorted keys make the text depend only on the values, so equal manifests give equal bytes.
    """
    return "".join(json.dumps(m, sort_keys=True) + "\n" for m in manifest)


def digest(manifest):
    """Hex SHA-256 of manifest_lines(manifest) as UTF-8: the hash of the manifest.jsonl file's bytes.

    store.register() gets this function as an argument, so store never has to import this module.
    """
    return hashlib.sha256(manifest_lines(manifest).encode()).hexdigest()


def run(out, db_path=None, mock=MOCK, orders=ORDERS, register=False, now=None):
    """Read the shared database at db_path (or the mock snapshot when db_path is None), write the
    documents and manifest.jsonl under out, and with register=True record them in the database.
    -> a summary dict (the manifest included).

    mock is the snapshot folder, orders how many of the newest orders to read (database only; the
    snapshot is used whole), and now the time stamped on the event (default: the local time, to the
    minute), which tests fix to get a known value.

    Steps:
    1. Load the rows. The database is opened read-only unless register is set, so a plain run never
       changes it.
    2. build() writes the documents and returns the manifest and the orders that had no row.
    3. With register, store.register() adds the missing documents rows and one documents.generated
       event in one transaction, filling the new row ids into the manifest entries in place.
    4. Write manifest.jsonl, after step 3 so the new ids are in it.

    The summary keys: source ("db" or "mock"), db, out, orders (rows read), manifest, kinds ({kind:
    count}), missing (how many orders had no row), sha256 (digest of the manifest), registered (rows
    added) and event (the event id, or None).

    Raises FileNotFoundError, store.SchemaError or sqlite3.Error for a bad database, ValueError for a
    stored path that escapes out, and OSError for file trouble.
    """
    if db_path:
        conn = store.connect(db_path, readonly=not register)
        try:
            data = store.from_db(conn, orders)
            manifest, missing = build(data, out)
            made, event = (store.register(conn, manifest, digest, (now or datetime.now()).isoformat(timespec="minutes"))
                           if register else (0, None))
        finally:
            conn.close()
    else:
        data = source.from_mock(mock)
        manifest, missing = build(data, out)
        made, event = 0, None
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "manifest.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest_lines(manifest))  # after registering, so new document ids are in the file
    kinds = {}
    for m in manifest:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    return {
        "source": "db" if db_path else "mock", "db": db_path, "out": out, "orders": len(data["orders"]),
        "manifest": manifest, "kinds": kinds, "missing": len(missing), "sha256": digest(manifest),
        "registered": made, "event": event,
    }

# ==== stamp v1 | author=kjFriday | hmac-sha256=baff290124d103941c464c09d3dcfc40a731d64c52359d7f430c89647f81bd16 ====
