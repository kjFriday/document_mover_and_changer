# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe_app.py
# About: Start Generic Company Doc Pipeline from a shortcut or Apps & features.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Start Generic Company Doc Pipeline from a shortcut or Apps & features.

It does the same as `python -m docpipe`, from any folder. The Start-menu shortcut, the Apps & features uninstall entry and a Wizard Maker setup's run step all
start this file with pythonw.exe; it only calls docpipe.__main__.main() and exits with its code.

It must stay in the project folder beside docpipe/: Python puts a script's own folder first on
sys.path, and that is what lets `import docpipe` work from any current folder. setup.json, the
installer's shortcut arguments and tests/test_app.py all name this file.
"""

import sys

from docpipe.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

# ==== stamp v1 | author=kjFriday | hmac-sha256=950f12093f947a16d35167055dd817c591a461e3cb7414cae7411b358ac6bb6c ====
