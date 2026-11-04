# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/ingest/__init__.py
# About: Stage 1: ingestion and routing.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Stage 1: ingestion and routing.

Stage 1 of the five-stage design in idea.md. Its only module so far:

    hashing   sha256_of(): a chunked SHA-256 of a file, for duplicate detection and provenance
              (docpipe.output.documents hashes every file it writes with it)

Routing is not written yet; docpipe.enrich.shape's document-type hints are meant to feed it.
This file holds no code; it only marks the folder as a package.
"""

# ==== stamp v1 | author=kjFriday | hmac-sha256=2f588f4613df24722870bd373fd5fb204dc5c3110ae9ea71eef536b65f8be054 ====
