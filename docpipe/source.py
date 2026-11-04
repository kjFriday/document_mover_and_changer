# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/source.py
# About: The bundled mock snapshot: the same shape store.from_db() gives from the shared database.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""The bundled mock snapshot: the same shape store.from_db() gives from the shared database.

{"orders": [...], "documents": [...], "customers": [...], "products": [...]}, rows exactly as the CRUD
hub's database holds them.

docpipe.pipeline.run() reads it when there is no usable database. The JSON files in mock/ are written
by the CRUD hub's mock export, so they track the hub's schema; this module only reads them.
"""

import json
import os

# The tables a run needs, one <table>.json file each. tests/test_store.py compares exactly these
# tables between the snapshot and a database built from it.
TABLES = ("orders", "documents", "customers", "products")


def from_mock(folder):
    """Read <table>.json for each of TABLES from folder; -> {table: list of row dicts}.

    The snapshot is returned whole (it holds 400 orders). Raises OSError for a missing or unreadable
    file and json.JSONDecodeError (a ValueError) for a broken one.
    """
    data = {}
    for table in TABLES:
        with open(os.path.join(folder, f"{table}.json"), encoding="utf-8") as f:
            data[table] = json.load(f)
    return data

# ==== stamp v1 | author=kjFriday | hmac-sha256=d32932df9c420e8a436b9e9a31c4f087b948f59359197903b4303e9eba9ca634 ====
