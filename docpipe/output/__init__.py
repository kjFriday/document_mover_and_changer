# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/output/__init__.py
# About: Stage 5: document files and their manifest.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Stage 5: document files and their manifest.

Stage 5 (storage and querying) of the five-stage design in idea.md. Its only module so far:

    documents   render() an order's invoice, receipt or packing slip as 64-column ASCII text, and
                build() every document of a run into a folder with a SHA-256 manifest

docpipe.pipeline calls build(); docpipe.store records the manifest in the shared database.
This file holds no code; it only marks the folder as a package.
"""

# ==== stamp v1 | author=kjFriday | hmac-sha256=c9a3b41f053b9d3600ddbde23c36587bfc209012ae9251ad3083a964e418c783 ====
