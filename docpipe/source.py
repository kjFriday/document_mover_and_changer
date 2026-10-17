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
