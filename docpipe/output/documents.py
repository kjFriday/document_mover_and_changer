# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/output/documents.py
# About: Stage 5 output: render each order's documents (invoice, receipt, packing slip) as...
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Stage 5 output: render each order's documents (invoice, receipt, packing slip) as plain-text files.

Each `documents` row names its order, its kind and its relative path; `build` writes the file there
and returns a manifest line with the file's SHA-256, so a rerun can tell what changed.
"""

import os
from decimal import ROUND_HALF_UP, Decimal

from docpipe.enrich.normalize import fold
from docpipe.ingest.hashing import sha256_of

WIDTH = 64
TITLES = {"invoice": "INVOICE", "receipt": "RECEIPT", "packing_slip": "PACKING SLIP"}


def money(value):
    """Exact two-place amount (no float drift): 12.5 -> "12.50"."""
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def default_path(order, kind="invoice"):
    """The path the hub's seed uses, for orders that have no documents row yet."""
    when = (order.get("ordered_at") or "0000-00")[:7].replace("-", "/")
    return f"{kind}s/{when}/{kind[:3].upper()}-{order['id']:06d}.txt"


def render(kind, order, customer, product):
    """The document text. Names are folded to one line of ASCII so the layout never breaks."""
    title = TITLES.get(kind, fold(kind).upper() or "DOCUMENT")
    qty = int(order.get("quantity") or 0)
    total = Decimal(money(order.get("total")))
    unit = (total / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty else Decimal("0.00")
    name = fold((product or {}).get("name") or "Unknown product", 36)
    lines = [
        "ACME Inc.".ljust(WIDTH - len(title)) + title,
        "=" * WIDTH,
        f"Order      #{order['id']:06d}",
        f"Date       {fold(order.get('ordered_at'), 16)}",
        f"Customer   {fold((customer or {}).get('name') or 'Unknown customer', 50)}",
        f"Email      {fold((customer or {}).get('email'), 50)}",
        f"City       {fold((customer or {}).get('city'), 50)}",
        "-" * WIDTH,
        f"{'Item':<36}{'Qty':>6}{'Unit':>10}{'Amount':>12}",
    ]
    if kind == "packing_slip":
        lines += [f"{name:<36}{qty:>6}", "-" * WIDTH, "Prices are on the invoice."]
    else:
        lines += [f"{name:<36}{qty:>6}{money(unit):>10}{money(total):>12}", "-" * WIDTH, f"{'Total':<52}{money(total):>12}"]
        if kind == "receipt":
            lines.append("Paid in full. Thank you.")
    lines += ["", "ACME Inc. is a fictional company; this document is mock data."]
    return "\n".join(lines) + "\n"


def build(data, out_dir):
    """Write every document for data["orders"]; -> (manifest rows, orders that had no documents row)."""
    customers = {c["id"]: c for c in data["customers"]}
    products = {p["id"]: p for p in data["products"]}
    orders = {o["id"]: o for o in data["orders"]}
    docs = [d for d in data["documents"] if d["order_id"] in orders]
    covered = {d["order_id"] for d in docs}
    missing = sorted(oid for oid in orders if oid not in covered)
    jobs = [(d["kind"], d["path"], d.get("id")) for d in docs] + [("invoice", default_path(orders[oid]), None) for oid in missing]
    manifest = []
    root = os.path.abspath(out_dir)
    for (kind, rel, doc_id), order in zip(jobs, [orders[d["order_id"]] for d in docs] + [orders[o] for o in missing]):
        path = os.path.abspath(os.path.join(root, rel))
        if os.path.commonpath([root, path]) != root:  # a stored path must never climb out of out_dir
            raise ValueError(f"document path escapes the output folder: {rel!r}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = render(kind, order, customers.get(order.get("customer_id")), products.get(order.get("product_id")))
        with open(path, "w", encoding="ascii", newline="\n") as f:
            f.write(text)
        manifest.append({"document_id": doc_id, "order_id": order["id"], "kind": kind,
                         "path": rel.replace(os.sep, "/"), "sha256": sha256_of(path)})
    manifest.sort(key=lambda m: m["path"])
    return manifest, missing

# ==== stamp v1 | author=kjFriday | hmac-sha256=563fe12906138084305bbef51422b1cd70bdcef5e5b2cfb606228066a14f9137 ====
