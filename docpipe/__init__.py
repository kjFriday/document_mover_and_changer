# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/__init__.py
# About: docpipe: a small, stdlib-only document pipeline.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""docpipe: a small, stdlib-only document pipeline.

The package turns the newest orders of the shared Generic Company database (or the bundled mock
snapshot) into plain-text documents (invoice, receipt, packing slip) plus a hashed manifest. It follows
the five-stage design in idea.md; only stages 1, 4 and 5 have code so far.

Subpackages follow the pipeline stages:

    docpipe.ingest   Stage 1, ingestion (content hashing for dedupe/provenance)
    docpipe.enrich   Stage 4, normalisation and enrichment
    docpipe.output   Stage 5, document files and their manifest

docpipe.store reads and writes the shared database (by path), docpipe.source the bundled mock snapshot,
docpipe.pipeline runs it all, and docpipe.gui is the window that ``python -m docpipe`` opens.
docpipe.installer, docpipe.paths and docpipe.textsafe are copies of the CRUD hub's modules: programs
in the portfolio share no code at run time.

This module itself only holds the program's identity constants below. __main__, gui, the installer
plan and the tests all read them from here, so each value is written once.
"""

# The one Python-side version number. The Dev Console bumps it together with setup.json, and the
# smoke run in the portfolio's verify script expects this exact value.
__version__ = "0.2.0"

# Identity strings. APP_ID is the Windows AppUserModelID and the per-user data folder name; it must
# match paths.APP_ID and the id, appUserModelId and purge path in setup.json. NAME is the display
# name (window, Start menu, Apps & features), TITLE the window title in the portfolio's fixed
# "Generic Company Inc. — <name> <version>" form, PUBLISHER the Apps & features publisher, and
# CREDIT the icon licence credit that the About box must show (CC BY 2.5 requires attribution).
APP_ID = "GenericCompany.DocPipe"
NAME = "Generic Company Doc Pipeline"
TITLE = f"Generic Company Inc. — {NAME} {__version__}"
PUBLISHER = "Generic Company Inc. (fictional)"
CREDIT = ("Icon: Silk by Mark James (famfamfam.com/lab/icons/silk), CC BY 2.5 "
          "(creativecommons.org/licenses/by/2.5), enlarged by nearest-neighbour.")

# ==== stamp v1 | author=kjFriday | hmac-sha256=692efb9cb8b3da8ed6f1417b49537789b0b01dc772aa7fad72645ec121aa510d ====
