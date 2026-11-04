# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/enrich/__init__.py
# About: Stage 4: validation, normalisation and enrichment.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Stage 4: validation, normalisation and enrichment.

Stage 4 of the five-stage design in idea.md. Its modules:

    normalize   fold(): short metadata fields to one line of printable ASCII (used by
                docpipe.output.documents when it renders names)
    shape       text-shape signatures and nearest-exemplar document-type hints, with its own
                command line (python -m docpipe.enrich.shape); the app does not call it yet

This file holds no code; it only marks the folder as a package, and the submodules are imported
by name.
"""

# ==== stamp v1 | author=kjFriday | hmac-sha256=5a157e96dbe8752cec6a443f887d2c5cd364f723277d7290c0272f39e8c32bd5 ====
