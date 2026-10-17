"""Run the document pipeline: orders in, document files and a manifest out.

    python -m docpipe [--mock mock] [--out out] [--hub URL [--orders N] [--register]]

Standalone it reads the bundled mock/ snapshot. With --hub it reads the newest orders from the CRUD
hub; --register then writes back: a `documents` row for each order that had none, and one
`documents.generated` event summarising the run (which the notification hub can pick up).
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error

from docpipe import source
from docpipe.output.documents import build


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m docpipe", description=__doc__.split("\n\n")[0])
    ap.add_argument("--mock", default="mock", help="snapshot folder (default: mock)")
    ap.add_argument("--out", default="out", help="output folder (default: out)")
    ap.add_argument("--hub", default=os.environ.get("ACME_HUB", ""), help="CRUD hub base URL; empty = use --mock")
    ap.add_argument("--orders", type=int, default=400, help="with --hub: how many of the newest orders")
    ap.add_argument("--register", action="store_true", help="with --hub: write documents rows and a summary event")
    args = ap.parse_args(argv)

    hub = source.Hub(args.hub) if args.hub else None
    try:
        data = source.from_hub(hub, args.orders) if hub else source.from_mock(args.mock)
    except (OSError, urllib.error.URLError) as e:
        print(f"hub unreachable at {args.hub} ({e}); run without --hub to use the mock snapshot", file=sys.stderr)
        return 1

    manifest, missing = build(data, args.out)
    lines = "".join(json.dumps(m, sort_keys=True) + "\n" for m in manifest)
    with open(os.path.join(args.out, "manifest.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        f.write(lines)
    kinds = {}
    for m in manifest:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    print(f"source: {'live hub ' + args.hub if hub else 'mock snapshot ' + args.mock}")
    print(f"orders: {len(data['orders'])}; documents written: {len(manifest)} {kinds}")
    print(f"orders with no documents row: {len(missing)}")
    print(f"manifest: {os.path.join(args.out, 'manifest.jsonl')}  sha256 {hashlib.sha256(lines.encode()).hexdigest()[:16]}")

    if hub and args.register:
        made = 0
        for m in manifest:
            if m["document_id"] is None:
                m["document_id"] = hub.call("POST", "/api/documents", {"order_id": m["order_id"], "kind": m["kind"], "path": m["path"]})["id"]
                made += 1
        payload = {"documents": len(manifest), "registered": made, "manifest_sha256": hashlib.sha256(lines.encode()).hexdigest()}
        event = hub.call("POST", "/api/events", {"kind": "documents.generated", "payload": json.dumps(payload), "status": "sent"})
        print(f"hub: POST /api/documents x{made}; POST /api/events -> event {event['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
