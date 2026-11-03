# ==== Generic Company Inc. portfolio ====================================
# Project: document_mover_and_changer | File: docpipe/__init__.py
# About: docpipe: a small, stdlib-only document pipeline.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""docpipe: a small, stdlib-only document pipeline.

Subpackages follow the pipeline stages:

    docpipe.ingest   Stage 1, ingestion (content hashing for dedupe/provenance)
    docpipe.enrich   Stage 4, normalisation and enrichment
    docpipe.output   Stage 5, document files and their manifest

docpipe.store reads and writes the shared database (by path), docpipe.source the bundled mock snapshot,
docpipe.pipeline runs it all, and docpipe.gui is the window that ``python -m docpipe`` opens.
"""

__version__ = "0.2.0"

APP_ID = "GenericCompany.DocPipe"
NAME = "Generic Company Doc Pipeline"
TITLE = f"Generic Company Inc. — {NAME} {__version__}"
PUBLISHER = "Generic Company Inc. (fictional)"
CREDIT = ("Icon: Silk by Mark James (famfamfam.com/lab/icons/silk), CC BY 2.5 "
          "(creativecommons.org/licenses/by/2.5), enlarged by nearest-neighbour.")

# ==== stamp v1 | author=kjFriday | hmac-sha256=3bbaf2eb475a291a34c6e413d04897e789a9efd8fe5132e51a0429e2a6f225e8 ====
