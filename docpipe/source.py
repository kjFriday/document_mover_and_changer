"""Where the pipeline's rows come from: the bundled mock snapshot or the live CRUD hub API.

Both give the same shape: {"orders": [...], "documents": [...], "customers": [...], "products": [...]},
rows exactly as the hub serves them.
"""

import json
import os
import urllib.error
import urllib.request

TABLES = ("orders", "documents", "customers", "products")
PAGE = 500  # the hub's largest ?limit


def from_mock(folder):
    data = {}
    for table in TABLES:
        with open(os.path.join(folder, f"{table}.json"), encoding="utf-8") as f:
            data[table] = json.load(f)
    return data


class Hub:
    """A small client for the CRUD hub's REST API."""

    def __init__(self, base, timeout=10):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def call(self, method, path, body=None):
        """-> decoded JSON; raises OSError (unreachable) or urllib.error.HTTPError (4xx/5xx)."""
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read() or b"null")

    def rows(self, table, limit=None):
        """The newest `limit` rows of a table (all of them when None), paging with ?limit&offset."""
        out = []
        while limit is None or len(out) < limit:
            size = PAGE if limit is None else min(PAGE, limit - len(out))
            page = self.call("GET", f"/api/{table}?limit={size}&offset={len(out)}")
            out.extend(page)
            if len(page) < size:
                break
        return out


def from_hub(hub, orders=400):
    """The newest `orders` orders and every document, customer and product row they need."""
    data = {"orders": hub.rows("orders", orders)}
    ids = {o["id"] for o in data["orders"]}
    data["documents"] = [d for d in hub.rows("documents") if d["order_id"] in ids]
    data["customers"] = hub.rows("customers")
    data["products"] = hub.rows("products")
    return data
