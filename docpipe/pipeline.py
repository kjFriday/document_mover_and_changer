# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/pipeline.py
# About: One pipeline run, shared by the window and the command line: rows in, document files and...
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""One pipeline run, shared by the window and the command line: rows in, document files and manifest out."""

import hashlib
import json
import os
from datetime import datetime

from docpipe import source, store
from docpipe.output.documents import build

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = os.path.join(HERE, "mock")  # the bundled snapshot, beside the package (also in an installed copy)


def manifest_lines(manifest):
    return "".join(json.dumps(m, sort_keys=True) + "\n" for m in manifest)


def digest(manifest):
    return hashlib.sha256(manifest_lines(manifest).encode()).hexdigest()


def run(out, db_path=None, mock=MOCK, orders=400, register=False, now=None):
    """Read the shared database at db_path (or the mock snapshot when db_path is None), write the
    documents and manifest.jsonl under out, and with register=True record them in the database.
    -> a summary dict (the manifest included)."""
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

# ==== stamp v1 | author=kjFriday | hmac-sha256=aca119b119e2cf9adfd8e308edf0e0031d5b95492c85a8aefe202065b18bbdf1 ====
