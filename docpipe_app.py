# ==== Generic Company Inc. portfolio ====================================
# Project: document_mover_and_changer | File: docpipe_app.py
# About: Start Generic Company Doc Pipeline from a shortcut or Apps & features (same as `python -m...
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Start Generic Company Doc Pipeline from a shortcut or Apps & features (same as `python -m docpipe`, from any folder)."""

import sys

from docpipe.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

# ==== stamp v1 | author=kjFriday | hmac-sha256=455dd2bc90f0ce661f4db334357ba36712cef5ecf7ede7b158efd108c963152c ====
