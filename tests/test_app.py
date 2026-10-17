"""Doc Pipeline's identity: version, title, icon files and what an install copies."""

import hashlib
import os
import re
import struct
import unittest

import docpipe
from docpipe import __main__ as app
from docpipe import installer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ICON = os.path.join(ROOT, "icon")


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


class AppTest(unittest.TestCase):
    def test_one_version_everywhere(self):
        self.assertRegex(docpipe.__version__, r"^\d+\.\d+\.\d+$")
        self.assertTrue(docpipe.TITLE.endswith(" " + docpipe.__version__))
        p = installer.plan(app.program(), app.HERE, env={}, root=os.path.join(ROOT, "_never_written"))
        self.assertEqual(p["registry"]["DisplayVersion"], docpipe.__version__)
        self.assertEqual(p["app_id"], "ACME.DocPipe")
        self.assertTrue(p["shortcuts"][0]["args"].endswith('docpipe_app.py"'))

    def test_install_copies_runtime_only(self):
        files = app.program().files
        for needed in ("docpipe_app.py", "docpipe/gui.py", "docpipe/output/documents.py", "mock/orders.json", "icon/app.ico"):
            self.assertIn(needed, files)
        self.assertFalse([f for f in files if f.startswith("tests/") or "__pycache__" in f])

    def test_icon_files(self):
        self.assertEqual(png_size(os.path.join(ICON, "silk-folder_go.png")), (16, 16))
        for n in (32, 48, 256):
            self.assertEqual(png_size(os.path.join(ICON, f"app-{n}.png")), (n, n))
        with open(os.path.join(ICON, "app.ico"), "rb") as f:
            ico = f.read()
        self.assertEqual(struct.unpack("<HHH", ico[:6]), (0, 1, 4))
        with open(os.path.join(ICON, "README.md"), encoding="utf-8") as f:
            listed = dict(re.findall(r"\| `([^`]+)` \|[^|]*\| `([0-9a-f]{64})` \|", f.read()))
        self.assertEqual(len(listed), 6)
        for name, digest in listed.items():
            with open(os.path.join(ICON, name), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
