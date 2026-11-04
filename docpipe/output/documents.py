# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/output/documents.py
# About: Stage 5 output: each order's invoice, receipt or packing slip as a plain-text file.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Stage 5 output: each order's invoice, receipt or packing slip as a plain-text file.

`render` lays out one document as 64-column ASCII text; `build` writes all of a run's documents.

Each `documents` row names its order, its kind and its relative path; `build` writes the file there
and returns a manifest line with the file's SHA-256, so a rerun can tell what changed.

docpipe.pipeline.run() calls build() with the rows from docpipe.store (database) or docpipe.source
(mock snapshot). build() in turn:

1. indexes customers, products and orders by id;
2. keeps the documents rows of the orders in the run, and notes the orders with none;
3. renders each document with render() (names folded by enrich.normalize.fold) and writes it as ASCII
   at its stored path, or at default_path() as an invoice for an order with no row;
4. hashes each file with ingest.hashing.sha256_of and returns the manifest sorted by path.

A manifest entry is a dict {document_id, order_id, kind, path, sha256}; document_id is None for an
order that had no row, until docpipe.store.register() fills it in. The same input always gives the
same files, so the same hashes.
"""

import os
from decimal import ROUND_HALF_UP, Decimal

from docpipe.enrich.normalize import fold
from docpipe.ingest.hashing import sha256_of

# Page width in columns. The item row's columns (36 + 6 + 10 + 12) and the "Total" label (52 + 12)
# add up to it by hand, so changing it means changing those numbers in render() too.
WIDTH = 64
# Heading for each document kind the hub knows; any other kind is shown as its folded, upper-cased name.
TITLES = {"invoice": "INVOICE", "receipt": "RECEIPT", "packing_slip": "PACKING SLIP"}


def money(value):
    """Exact two-place amount (no float drift): 12.5 -> "12.50".

    str() first gives the float's shortest repr ("2.675"), so Decimal works on the digits a person
    sees, not the binary value (2.67499...). Halves round up, as on a till: 2.675 -> "2.68".
    None and 0 give "0.00".
    """
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def default_path(order, kind="invoice"):
    """The path the hub's seed uses, for orders that have no documents row yet.

    The form is {kind}s/YYYY/MM/{KIN}-{id:06d}.txt, e.g. invoices/2026/04/INV-000007.txt, with the year and
    month from ordered_at ("0000/00" when it is missing). It copies the CRUD hub seed's layout, so
    documents made here sit beside the seeded ones; a change there must be made here as well.
    """
    when = (order.get("ordered_at") or "0000-00")[:7].replace("-", "/")
    return f"{kind}s/{when}/{kind[:3].upper()}-{order['id']:06d}.txt"


def render(kind, order, customer, product):
    """The document text. Names are folded to one line of ASCII so the layout never breaks.

    kind is "invoice", "receipt", "packing_slip" or any other name; order is an orders row; customer
    and product are their rows or None (shown as "Unknown ..."). The result is WIDTH-column text with
    "\\n" line endings and a final newline, and it is pure ASCII, which build() relies on.

    Layout: a heading line, order and customer details, then the item table. Invoices and receipts
    show the unit price, the amount and a total; a receipt adds "Paid in full"; a packing slip shows
    only the quantity. Every document ends with the note that the data is fictional.
    """
    title = TITLES.get(kind, fold(kind).upper() or "DOCUMENT")
    qty = int(order.get("quantity") or 0)
    total = Decimal(money(order.get("total")))
    # orders store only the total, so the unit price is derived from it (0.00 for no quantity)
    unit = (total / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty else Decimal("0.00")
    # fold limits match the column each value sits in: 36 for the item column, 50 for the details
    # after their 11-character label, 16 for a date-time such as "2026-04-05T10:11"
    name = fold((product or {}).get("name") or "Unknown product", 36)
    lines = [
        "Generic Company Inc.".ljust(WIDTH - len(title)) + title,
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
    lines += ["", "Generic Company Inc. is a fictional company; this document is mock data."]
    return "\n".join(lines) + "\n"


def build(data, out_dir):
    """Write every document for data["orders"]; -> (manifest rows, orders that had no documents row).

    data has the lists "orders", "documents", "customers" and "products" (store.from_db() or
    source.from_mock()). Files go under out_dir, created as needed and overwritten on a rerun. The
    manifest is sorted by path and the missing order ids are sorted too, so output is deterministic.

    Raises ValueError, before writing that file, when a stored path would land outside out_dir
    ("../..", or an absolute path), and OSError when a file cannot be written.
    """
    customers = {c["id"]: c for c in data["customers"]}
    products = {p["id"]: p for p in data["products"]}
    orders = {o["id"]: o for o in data["orders"]}
    docs = [d for d in data["documents"] if d["order_id"] in orders]
    covered = {d["order_id"] for d in docs}
    missing = sorted(oid for oid in orders if oid not in covered)
    # one job per file: the existing rows first, then a new invoice for each order without a row.
    # The order list zipped with jobs below is built in the same two parts, in the same order.
    jobs = [(d["kind"], d["path"], d.get("id")) for d in docs] + [("invoice", default_path(orders[oid]), None) for oid in missing]
    manifest = []
    root = os.path.abspath(out_dir)
    for (kind, rel, doc_id), order in zip(jobs, [orders[d["order_id"]] for d in docs] + [orders[o] for o in missing]):
        # abspath resolves any ".." and join() takes an absolute rel as is, so the check below sees the
        # real target; commonpath raises ValueError itself for a path on another drive
        path = os.path.abspath(os.path.join(root, rel))
        if os.path.commonpath([root, path]) != root:  # a stored path must never climb out of out_dir
            raise ValueError(f"document path escapes the output folder: {rel!r}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = render(kind, order, customers.get(order.get("customer_id")), products.get(order.get("product_id")))
        # newline="\n": the same bytes, so the same hash, on every system
        with open(path, "w", encoding="ascii", newline="\n") as f:
            f.write(text)
        manifest.append({"document_id": doc_id, "order_id": order["id"], "kind": kind,
                         "path": rel.replace(os.sep, "/"), "sha256": sha256_of(path)})
    manifest.sort(key=lambda m: m["path"])  # a fixed order, so the manifest's own hash is reproducible
    return manifest, missing

# ==== stamp v1 | author=kjFriday | hmac-sha256=522709f098423fad1c31e2b796cdf74b9ebcc77b53b3f6a351cb8349541f0e54 ====
