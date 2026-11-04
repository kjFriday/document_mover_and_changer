# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_paths.py
# About: Tests for paths: where the shared database and each program's settings live.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for paths: where the shared database and each program's settings live.

Every test passes its own env dict with LOCALAPPDATA in a temporary folder, so the real user
profile is never read or written.
"""

import json
import os
import tempfile
import unittest

from docpipe import paths


class PathsTest(unittest.TestCase):
    """Path choice, precedence and settings files, under a temporary LOCALAPPDATA."""

    def setUp(self):
        """A temporary folder and an environment whose LOCALAPPDATA is that folder."""
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"LOCALAPPDATA": self.tmp.name}

    def tearDown(self):
        """Remove the temporary folder."""
        self.tmp.cleanup()

    def test_default_is_shared(self):
        """With nothing set, every program gets the same database under the company folder."""
        self.assertEqual(paths.resolve_db(env=self.env), os.path.join(self.tmp.name, "Generic Company Inc", "generic_company.db"))
        self.assertEqual(paths.data_dir("GenericCompany.Dash", self.env), os.path.join(self.tmp.name, "Generic Company Inc", "GenericCompany.Dash"))

    def test_precedence(self):
        """The saved setting, then the environment variable over it, then --db over both; a blank variable is skipped."""
        paths.save_settings({"db": os.path.join(self.tmp.name, "saved.db")}, env=self.env)
        self.assertTrue(paths.resolve_db(env=self.env).endswith("saved.db"))
        self.env["GENERIC_COMPANY_DB"] = os.path.join(self.tmp.name, "env.db")
        self.assertTrue(paths.resolve_db(env=self.env).endswith("env.db"))
        self.assertTrue(paths.resolve_db(os.path.join(self.tmp.name, "flag.db"), env=self.env).endswith("flag.db"))
        self.env["GENERIC_COMPANY_DB"] = "  "
        self.assertTrue(paths.resolve_db(env=self.env).endswith("saved.db"))

    def test_settings_per_app(self):
        """One program's saved setting is invisible to another."""
        paths.save_settings({"db": "a.db"}, "GenericCompany.Hub", self.env)
        self.assertEqual(paths.load_settings("GenericCompany.CMS", self.env), {})
        self.assertEqual(paths.load_settings("GenericCompany.Hub", self.env)["db"], "a.db")

    def test_bad_or_foreign_settings(self):
        """A settings file that is not JSON, or is JSON but not an object, reads as no settings."""
        path = paths.settings_path(env=self.env)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(paths.load_settings(env=self.env), {})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(["a list"], f)
        self.assertEqual(paths.load_settings(env=self.env), {})

    def test_save_keeps_unknown_keys_and_leaves_no_temp(self):
        """A save keeps keys it does not change, adds the version, and leaves no settings.json.tmp behind."""
        paths.save_settings({"db": "a.db", "theme": "dark"}, env=self.env)
        data = paths.save_settings({"db": "b.db"}, env=self.env)
        self.assertEqual(data, {"db": "b.db", "theme": "dark", "version": 1})
        folder = paths.data_dir(env=self.env)
        self.assertEqual(os.listdir(folder), ["settings.json"])


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=e1ee83147293b10181c70f455610445b70e45def9d7fce0585e94fa6a4f98763 ====
