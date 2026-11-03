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
"""

import json
import os

TABLES = ("orders", "documents", "customers", "products")


def from_mock(folder):
    data = {}
    for table in TABLES:
        with open(os.path.join(folder, f"{table}.json"), encoding="utf-8") as f:
            data[table] = json.load(f)
    return data

# ==== stamp v1 | author=kjFriday | hmac-sha256=31f1d29f26cbdb5dca1b654aef621c2ad397840ea05ec6daa24177d087d434ae ====
