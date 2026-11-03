# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/__init__.py
# About: docpipe: a small, stdlib-only document pipeline.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
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

# ==== stamp v1 | author=kjFriday | hmac-sha256=1c2d015d6b9f5d5b1f89e78af8f4c347745eb72795376e38e3acf9d8a8eca52e ====
