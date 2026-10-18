# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe_app.py
# About: Start ACME Doc Pipeline from a shortcut or Apps & features (same as `python -m docpipe`...
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Start ACME Doc Pipeline from a shortcut or Apps & features (same as `python -m docpipe`, from any folder)."""

import sys

from docpipe.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

# ==== stamp v1 | author=kjFriday | hmac-sha256=324bc53bc199870b14b506f614840a89a0574087b73ae961a833716392a1bdcb ====
