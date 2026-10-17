import datetime
import json
import os
import tempfile
import unittest

from docpipe import installer


class Recorder:
    def __init__(self):
        self.scripts = []

    def __call__(self, script):
        self.scripts.append(script)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(os.path.join(self.src, "icon"))
        for rel in ("main.py", "db.py", "icon/app.ico"):
            with open(os.path.join(self.src, *rel.split("/")), "w") as f:
                f.write("x" * 100)
        self.root = os.path.join(self.tmp.name, "sandbox")
        self.program = installer.Program("ACME.Test", "ACME Test App", "0.2.0", "ACME Inc. (fictional)",
                                         ["main.py", "db.py", "icon/app.ico"], ["{dir}\\main.py"])
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def plan(self, **kw):
        return installer.plan(self.program, self.src, env={}, root=self.root, interpreter=r"C:\Py\python.exe",
                              today=datetime.date(2026, 10, 17), **kw)

    def test_plan_paths_and_registry(self):
        p = self.plan(desktop=True)
        self.assertEqual(p["install_dir"], os.path.join(self.root, "Programs", "ACME Inc", "ACME Test App"))
        self.assertEqual([os.path.basename(s["path"]) for s in p["shortcuts"]], ["ACME Test App.lnk"] * 2)
        reg = p["registry"]
        self.assertEqual(reg["DisplayVersion"], "0.2.0")
        self.assertEqual(reg["DisplayName"], "ACME Test App 0.2.0")
        self.assertEqual(reg["InstallDate"], "20261017")
        self.assertEqual((reg["NoModify"], reg["NoRepair"]), (1, 1))
        self.assertTrue(reg["DisplayIcon"].endswith(os.path.join("icon", "app.ico")))
        self.assertIn("--uninstall --root", reg["UninstallString"])
        self.assertTrue(reg["QuietUninstallString"].endswith("--quiet"))
        self.assertEqual(p["registry_key"], installer.UNINSTALL_KEY + "\\ACME.Test")
        self.assertEqual(p["shortcuts"][0]["args"], '"' + os.path.join(p["install_dir"], "main.py") + '"')

    def test_real_locations(self):
        env = {"LOCALAPPDATA": r"C:\L", "APPDATA": r"C:\R", "USERPROFILE": r"C:\U"}
        programs, start, desk, reg = installer.locations(env)
        self.assertEqual(programs, os.path.join(r"C:\L", "Programs", "ACME Inc"))
        self.assertEqual(start, os.path.join(r"C:\R", "Microsoft", "Windows", "Start Menu", "Programs", "ACME Inc"))
        self.assertIsNone(reg)

    def test_script_quotes_and_registry(self):
        p = installer.plan(self.program, self.src, env={"LOCALAPPDATA": r"C:\O'Brien"}, interpreter=r"C:\Py\python.exe")
        script = installer.ps_script(p)
        self.assertIn("'C:\\O''Brien\\Programs\\ACME Inc\\ACME Test App\\icon\\app.ico,0'", script)
        self.assertIn("-Name 'NoModify' -Value '1' -PropertyType DWord", script)
        self.assertIn("-Name 'DisplayVersion' -Value '0.2.0' -PropertyType String", script)
        self.assertIn("New-Item -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ACME.Test'", script)
        removal = installer.ps_script(p, remove=True)
        self.assertIn("Remove-Item -LiteralPath 'HKCU:", removal)
        self.assertNotIn("CreateShortcut", removal)

    def test_sandbox_script_never_touches_registry(self):
        self.assertNotIn("HKCU", installer.ps_script(self.plan()))
        self.assertNotIn("HKCU", installer.ps_script(self.plan(), remove=True))

    def test_round_trip(self):
        p, run = self.plan(), Recorder()
        db = os.path.join(self.root, "acme.db")
        os.makedirs(self.root, exist_ok=True)
        open(db, "w").close()
        installer.install(p, run)
        self.assertTrue(os.path.isfile(os.path.join(p["install_dir"], "icon", "app.ico")))
        marker = installer.read_marker(p["install_dir"])
        self.assertEqual(marker["files"], ["main.py", "db.py", "icon/app.ico"])
        with open(p["registry_file"]) as f:
            self.assertEqual(json.load(f)[p["registry_key"]]["DisplayVersion"], "0.2.0")
        installer.install(p, run)  # reinstall over itself
        os.chdir(p["install_dir"])
        self.assertTrue(installer.uninstall(p, run))
        self.assertFalse(os.path.exists(p["install_dir"]))
        self.assertTrue(os.path.exists(db))
        with open(p["registry_file"]) as f:
            self.assertEqual(json.load(f), {})
        self.assertEqual(len(run.scripts), 3)

    def test_guard_refuses_foreign_folder(self):
        p = self.plan()
        os.makedirs(p["install_dir"])
        with open(os.path.join(p["install_dir"], "keep.txt"), "w") as f:
            f.write("not ours")
        with self.assertRaises(RuntimeError):
            installer.uninstall(p, Recorder())
        with open(os.path.join(p["install_dir"], installer.MARKER), "w") as f:
            json.dump({"app_id": "ACME.Other"}, f)
        with self.assertRaises(RuntimeError):
            installer.install(p, Recorder())
        self.assertTrue(os.path.exists(os.path.join(p["install_dir"], "keep.txt")))

    def test_purge_only_the_data_folder(self):
        p, run = self.plan(), Recorder()
        data = os.path.join(self.root, "data", "ACME.Test")
        os.makedirs(data)
        installer.install(p, run)
        installer.uninstall(p, run, purge_dir=data)
        self.assertFalse(os.path.exists(data))
        self.assertTrue(os.path.exists(os.path.join(self.root, "data")))

    def test_program_files_skip_tests_and_caches(self):
        os.makedirs(os.path.join(self.src, "pkg", "__pycache__"))
        os.makedirs(os.path.join(self.src, "pkg", "tests"))
        for rel in ("pkg/a.py", "pkg/test_b.py", "pkg/__pycache__/a.pyc", "pkg/tests/t.py", "test_main.py"):
            open(os.path.join(self.src, *rel.split("/")), "w").close()
        self.assertEqual(installer.program_files(self.src, ["main.py", "pkg", "test_main.py", "missing.py"]),
                         ["main.py", "pkg/a.py"])

    @unittest.skipUnless(os.name == "nt", "Windows shortcuts")
    def test_real_shortcut_in_sandbox(self):
        p = self.plan()
        installer.install(p, installer.run_powershell)
        link = p["shortcuts"][0]["path"]
        self.assertTrue(os.path.isfile(link))
        installer.uninstall(p, installer.run_powershell)
        self.assertFalse(os.path.exists(link))
        self.assertFalse(os.path.exists(os.path.dirname(link)))


if __name__ == "__main__":
    unittest.main()
