# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_app.py
# About: Doc Pipeline's identity: version, title, icon files and what an install copies.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Doc Pipeline's identity: version, title, icon files and what an install copies.

These tests pin the facts other tools depend on: one version number everywhere, the app id, the
files --install copies against setup.json, the hand-off to a Wizard Maker uninstaller, the icon files
and the hash table in icon/README.md, and that the window module still imports. Nothing here touches
the real Start menu or registry: install plans are made with env={} and a sandbox root.
"""

import hashlib
import io
import json
import os
import re
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

import docpipe
from docpipe import __main__ as app
from docpipe import installer

# The project folder and its icon folder.
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ICON = os.path.join(ROOT, "icon")


def png_size(path):
    """Return a PNG file's (width, height) in pixels, read from its header without decoding it.

    A PNG starts with an 8-byte signature, then the IHDR chunk: 4 bytes of length and 4 of type,
    then width and height as big-endian 32-bit integers, so they sit at bytes 16..24.
    """
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


class AppTest(unittest.TestCase):
    """Identity, install contents and icon checks for the whole program."""

    def test_one_version_everywhere(self):
        """The version is x.y.z and the title and Apps & features entry show it; the app id and shortcut target are fixed."""
        self.assertRegex(docpipe.__version__, r"^\d+\.\d+\.\d+$")
        self.assertTrue(docpipe.TITLE.endswith(" " + docpipe.__version__))
        p = installer.plan(app.program(), app.HERE, env={}, root=os.path.join(ROOT, "_never_written"))
        self.assertEqual(p["registry"]["DisplayVersion"], docpipe.__version__)
        self.assertEqual(p["app_id"], "GenericCompany.DocPipe")
        self.assertTrue(p["shortcuts"][0]["args"].endswith('docpipe_app.py"'))

    def test_install_copies_runtime_only(self):
        """An install includes the launcher, the package, the snapshot and the icon, and no tests or caches."""
        files = app.program().files
        for needed in ("docpipe_app.py", "docpipe/gui.py", "docpipe/output/documents.py", "mock/orders.json", "icon/app.ico"):
            self.assertIn(needed, files)
        self.assertFalse([f for f in files if f.startswith("tests/") or "__pycache__" in f])

    def test_runtime_matches_setup_json_files(self):
        """--install copies RUNTIME and a Wizard Maker setup copies setup.json "files": same entries, same places."""
        with open(os.path.join(ROOT, "setup.json"), encoding="utf-8") as f:
            rules = json.load(f)["files"]
        self.assertEqual([r["from"] for r in rules], app.RUNTIME)
        # Wizard Maker copies a file, or a folder's contents, into "to" (default: the install folder itself),
        # so a folder needs "to" set to its own name and a top-level file none, to land where --install puts it
        for r in rules:
            folder = os.path.isdir(os.path.join(ROOT, r["from"]))
            self.assertEqual(r.get("to", ""), r["from"] if folder else "", r["from"])

    def test_uninstall_hands_a_wizard_made_install_to_its_uninstaller(self):
        """--uninstall passes --quiet, --purge and --root on to uninstall.exe and returns its exit code."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plan = installer.plan(app.program(), app.HERE, env={}, root=tmp.name)
        os.makedirs(plan["install_dir"])
        with open(os.path.join(plan["install_dir"], installer.MARKER), "w") as f:
            json.dump({"app_id": docpipe.APP_ID, "name": docpipe.NAME, "version": docpipe.__version__, "files": [],
                       "shortcuts": [], "installer": "Generic Company Wizard Maker 0.1.0"}, f)
        calls = []

        # stands in for installer.run_uninstaller: records the call and fails as a busy uninstaller does
        # (exit code 4), so main() must pass that code on and keep the install marker
        def refused(p, args):
            calls.append((p["install_dir"], args))
            raise installer.UninstallerFailed(4, f"Setup or uninstall of {docpipe.NAME} is already running.")

        # the module attribute is swapped for the rest of this test; the cleanup puts the real one back
        self.addCleanup(setattr, installer, "run_uninstaller", installer.run_uninstaller)
        installer.run_uninstaller = refused
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(app.main(["--uninstall", "--quiet", "--purge", "--root", tmp.name]), 4)
        self.assertEqual(calls, [(plan["install_dir"], ["-quiet", "-purge", "-root", os.path.abspath(tmp.name)])])
        self.assertIn("already running", out.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(plan["install_dir"], installer.MARKER)))
        installer.run_uninstaller = lambda p, args: f"Removed {docpipe.NAME} {docpipe.__version__}."
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(app.main(["--uninstall", "--quiet", "--root", tmp.name]), 0)
        self.assertIn("Removed", out.getvalue())

    def test_icon_files(self):
        """The icon files have their sizes, the .ico holds 4 images, and icon/README.md lists each file's true SHA-256."""
        self.assertEqual(png_size(os.path.join(ICON, "silk-folder_go.png")), (16, 16))
        for n in (32, 48, 256):
            self.assertEqual(png_size(os.path.join(ICON, f"app-{n}.png")), (n, n))
        with open(os.path.join(ICON, "app.ico"), "rb") as f:
            ico = f.read()
        # ICONDIR header, three little-endian 16-bit fields: reserved (0), type (1 = icon), image count
        self.assertEqual(struct.unpack("<HHH", ico[:6]), (0, 1, 4))
        # rows of the README table look like | `name` | ... | `<64 hex digits>` |; six files are listed
        with open(os.path.join(ICON, "README.md"), encoding="utf-8") as f:
            listed = dict(re.findall(r"\| `([^`]+)` \|[^|]*\| `([0-9a-f]{64})` \|", f.read()))
        self.assertEqual(len(listed), 6)
        for name, digest in listed.items():
            with open(os.path.join(ICON, name), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest, name)

    def test_window_module_imports(self):
        """gui.py imports and uses the pipeline's source check; the order counts keep their values (400, 15000)."""
        # the only test that loads gui.py: --cli no longer imports it
        try:
            import tkinter  # noqa: F401
        except ImportError:
            self.skipTest("this Python has no tkinter")
        from docpipe import gui, pipeline, store
        self.assertIs(gui.describe_source, pipeline.describe_source)
        self.assertEqual((store.ORDERS, pipeline.ORDERS, gui.MAX_ORDERS), (400, 400, 15000))


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=873366f1ad9082bcaa68ed3dcd3527c627276ca2a9cc59d5c275ca7923325967 ====
