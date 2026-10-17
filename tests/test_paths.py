import json
import os
import tempfile
import unittest

from docpipe import paths


class PathsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"LOCALAPPDATA": self.tmp.name}

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_is_shared(self):
        self.assertEqual(paths.resolve_db(env=self.env), os.path.join(self.tmp.name, "ACME Inc", "acme.db"))
        self.assertEqual(paths.data_dir("ACME.Dash", self.env), os.path.join(self.tmp.name, "ACME Inc", "ACME.Dash"))

    def test_precedence(self):
        paths.save_settings({"db": os.path.join(self.tmp.name, "saved.db")}, env=self.env)
        self.assertTrue(paths.resolve_db(env=self.env).endswith("saved.db"))
        self.env["ACME_DB"] = os.path.join(self.tmp.name, "env.db")
        self.assertTrue(paths.resolve_db(env=self.env).endswith("env.db"))
        self.assertTrue(paths.resolve_db(os.path.join(self.tmp.name, "flag.db"), env=self.env).endswith("flag.db"))
        self.env["ACME_DB"] = "  "
        self.assertTrue(paths.resolve_db(env=self.env).endswith("saved.db"))

    def test_settings_per_app(self):
        paths.save_settings({"db": "a.db"}, "ACME.Hub", self.env)
        self.assertEqual(paths.load_settings("ACME.CMS", self.env), {})
        self.assertEqual(paths.load_settings("ACME.Hub", self.env)["db"], "a.db")

    def test_bad_or_foreign_settings(self):
        path = paths.settings_path(env=self.env)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(paths.load_settings(env=self.env), {})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(["a list"], f)
        self.assertEqual(paths.load_settings(env=self.env), {})

    def test_save_keeps_unknown_keys_and_leaves_no_temp(self):
        paths.save_settings({"db": "a.db", "theme": "dark"}, env=self.env)
        data = paths.save_settings({"db": "b.db"}, env=self.env)
        self.assertEqual(data, {"db": "b.db", "theme": "dark", "version": 1})
        folder = paths.data_dir(env=self.env)
        self.assertEqual(os.listdir(folder), ["settings.json"])


if __name__ == "__main__":
    unittest.main()
