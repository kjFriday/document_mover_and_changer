# ==== Generic Company Inc. portfolio ====================================
# Project: document_mover_and_changer | File: docpipe/source.py
# About: The bundled mock snapshot: the same shape store.from_db() gives from the shared database.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
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

# ==== stamp v1 | author=kjFriday | hmac-sha256=b2933e571b7f8371982d98299125a5036581c6487f4f64c198387e41a535c62b ====
