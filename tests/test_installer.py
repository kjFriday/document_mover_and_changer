# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_installer.py
# About: Tests for installer: the plan, the PowerShell text, and install/uninstall in a sandbox.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for installer: the plan, the PowerShell text, and install/uninstall in a sandbox.

Almost every test uses root= (a sandbox under a temporary folder, registry in registry.json) and a
Recorder instead of PowerShell, so nothing reaches the real Start menu or registry. The few tests
marked skipUnless(os.name == "nt") run real PowerShell or cmd.exe, still inside the sandbox or on a
registry key that does not exist.
"""

import datetime
import json
import os
import tempfile
import unittest

from docpipe import installer


class Recorder:
    """A stand-in PowerShell runner that keeps each script it is given in .scripts."""

    def __init__(self):
        """Start with no scripts."""
        self.scripts = []

    def __call__(self, script):
        """Record script instead of running it."""
        self.scripts.append(script)


class InstallerTest(unittest.TestCase):
    """installer.py end to end, on a tiny three-file program in a temporary folder."""

    def setUp(self):
        """A source folder with main.py, db.py and icon/app.ico (100 bytes each), a sandbox root and a Program."""
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(os.path.join(self.src, "icon"))
        for rel in ("main.py", "db.py", "icon/app.ico"):
            with open(os.path.join(self.src, *rel.split("/")), "w") as f:
                f.write("x" * 100)
        self.root = os.path.join(self.tmp.name, "sandbox")
        self.program = installer.Program("GenericCompany.Test", "Generic Company Test App", "0.2.0", "Generic Company Inc. (fictional)",
                                         ["main.py", "db.py", "icon/app.ico"], ["{dir}\\main.py"])
        self.cwd = os.getcwd()

    def tearDown(self):
        """Return to the starting folder (uninstall moves to the temp folder), then remove the files."""
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def plan(self, **kw):
        """A sandbox plan with a fixed interpreter and date, so the values can be compared exactly."""
        return installer.plan(self.program, self.src, env={}, root=self.root, interpreter=r"C:\Py\python.exe",
                              today=datetime.date(2026, 10, 17), **kw)

    def test_plan_paths_and_registry(self):
        """Folder, both shortcuts, the uninstall entry's values and the quoted shortcut argument."""
        p = self.plan(desktop=True)
        self.assertEqual(p["install_dir"], os.path.join(self.root, "Programs", "Generic Company Inc", "Generic Company Test App"))
        self.assertEqual([os.path.basename(s["path"]) for s in p["shortcuts"]], ["Generic Company Test App.lnk"] * 2)
        reg = p["registry"]
        self.assertEqual(reg["DisplayVersion"], "0.2.0")
        self.assertEqual(reg["DisplayName"], "Generic Company Test App 0.2.0")
        self.assertEqual(reg["InstallDate"], "20261017")
        self.assertEqual((reg["NoModify"], reg["NoRepair"]), (1, 1))
        self.assertTrue(reg["DisplayIcon"].endswith(os.path.join("icon", "app.ico")))
        self.assertIn("--uninstall --root", reg["UninstallString"])
        self.assertTrue(reg["QuietUninstallString"].endswith("--quiet"))
        self.assertEqual(p["registry_key"], installer.UNINSTALL_KEY + "\\GenericCompany.Test")
        self.assertEqual(p["shortcuts"][0]["args"], '"' + os.path.join(p["install_dir"], "main.py") + '"')

    def test_real_locations(self):
        """Without a sandbox the folders come from LOCALAPPDATA and APPDATA, and the registry is the real one (None)."""
        env = {"LOCALAPPDATA": r"C:\L", "APPDATA": r"C:\R", "USERPROFILE": r"C:\U"}
        programs, start, desk, reg = installer.locations(env)
        self.assertEqual(programs, os.path.join(r"C:\L", "Programs", "Generic Company Inc"))
        self.assertEqual(start, os.path.join(r"C:\R", "Microsoft", "Windows", "Start Menu", "Programs", "Generic Company Inc"))
        self.assertIsNone(reg)

    def test_script_quotes_and_registry(self):
        """A ' in a path is doubled inside PowerShell quotes; ints are written as DWORD, text as String.

        O'Brien is the classic name that breaks naive quoting.
        """
        p = installer.plan(self.program, self.src, env={"LOCALAPPDATA": r"C:\O'Brien"}, interpreter=r"C:\Py\python.exe")
        script = installer.ps_script(p)
        self.assertIn("'C:\\O''Brien\\Programs\\Generic Company Inc\\Generic Company Test App\\icon\\app.ico,0'", script)
        self.assertIn("-Name 'NoModify' -Value '1' -PropertyType DWord", script)
        self.assertIn("-Name 'DisplayVersion' -Value '0.2.0' -PropertyType String", script)
        self.assertIn("New-Item -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GenericCompany.Test'", script)
        removal = installer.ps_script(p, remove=True)
        self.assertIn("Remove-Item -LiteralPath 'HKCU:", removal)
        self.assertNotIn("CreateShortcut", removal)

    def test_sandbox_script_never_touches_registry(self):
        """Neither the install nor the removal script of a sandbox names HKCU."""
        self.assertNotIn("HKCU", installer.ps_script(self.plan()))
        self.assertNotIn("HKCU", installer.ps_script(self.plan(), remove=True))

    def test_round_trip(self):
        """Install, reinstall over itself, uninstall from inside the folder: all gone but the database.

        The uninstall starts with the install folder as the working folder, as the Start-menu
        shortcut would; three scripts ran (two installs, one removal).
        """
        p, run = self.plan(), Recorder()
        db = os.path.join(self.root, "generic_company.db")
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
        """Uninstall will not delete a folder without our marker; install will not write into another program's."""
        p = self.plan()
        os.makedirs(p["install_dir"])
        with open(os.path.join(p["install_dir"], "keep.txt"), "w") as f:
            f.write("not ours")
        with self.assertRaises(RuntimeError):
            installer.uninstall(p, Recorder())
        with open(os.path.join(p["install_dir"], installer.MARKER), "w") as f:
            json.dump({"app_id": "GenericCompany.Other"}, f)
        with self.assertRaises(RuntimeError):
            installer.install(p, Recorder())
        self.assertTrue(os.path.exists(os.path.join(p["install_dir"], "keep.txt")))

    def test_purge_only_the_data_folder(self):
        """purge_dir removes the program's data folder and nothing above it."""
        p, run = self.plan(), Recorder()
        data = os.path.join(self.root, "data", "GenericCompany.Test")
        os.makedirs(data)
        installer.install(p, run)
        installer.uninstall(p, run, purge_dir=data)
        self.assertFalse(os.path.exists(data))
        self.assertTrue(os.path.exists(os.path.join(self.root, "data")))

    def test_program_files_skip_tests_and_caches(self):
        """test_ files, tests/ and __pycache__/ folders and missing entries are all left out."""
        os.makedirs(os.path.join(self.src, "pkg", "__pycache__"))
        os.makedirs(os.path.join(self.src, "pkg", "tests"))
        for rel in ("pkg/a.py", "pkg/test_b.py", "pkg/__pycache__/a.pyc", "pkg/tests/t.py", "test_main.py"):
            open(os.path.join(self.src, *rel.split("/")), "w").close()
        self.assertEqual(installer.program_files(self.src, ["main.py", "pkg", "test_main.py", "missing.py"]),
                         ["main.py", "pkg/a.py"])

    def wizard_install(self, p, app_id="GenericCompany.Test"):
        """What a setup made by Generic Company Wizard Maker leaves: its files, uninstall.exe and a marker with sha256 and
        installer; then notes.txt changes, as a user would change it."""
        os.makedirs(p["install_dir"], exist_ok=True)
        files = ["main.py", "notes.txt", "app.ico", installer.WIZARD_UNINSTALLER]
        for rel in files:
            with open(os.path.join(p["install_dir"], rel), "w") as f:
                f.write("as installed")
        with open(os.path.join(p["install_dir"], installer.MARKER), "w") as f:
            json.dump({"app_id": app_id, "name": p["name"], "version": p["version"], "files": files, "shortcuts": [],
                       "sha256": {"notes.txt": "e3b0"}, "installer": "Generic Company Wizard Maker 0.1.0"}, f)
        with open(os.path.join(p["install_dir"], "notes.txt"), "w") as f:
            f.write("changed by the user")

    def test_wizard_install_is_its_uninstallers_to_remove(self):
        """Only a marker that names this app id and an installer makes uninstall.exe the one to run."""
        p = self.plan()
        self.assertIsNone(installer.wizard_uninstaller(p))
        installer.install(p, Recorder())
        self.assertIsNone(installer.wizard_uninstaller(p))  # the program's own install
        self.wizard_install(p, "GenericCompany.Other")
        self.assertIsNone(installer.wizard_uninstaller(p))  # never another program's uninstaller
        self.wizard_install(p)
        self.assertEqual(installer.wizard_uninstaller(p), os.path.join(p["install_dir"], "uninstall.exe"))

    def test_uninstall_args(self):
        """No flags by default; quiet, purge and an absolute root in that order."""
        self.assertEqual(installer.uninstall_args(), [])
        self.assertEqual(installer.uninstall_args("sb", quiet=True, purge=True),
                         ["-quiet", "-purge", "-root", os.path.abspath("sb")])

    def test_run_uninstaller_keeps_changed_files_and_its_exit_code(self):
        """A failing uninstaller's exit code and message come back in UninstallerFailed, and nothing is deleted here.

        Also: the process leaves the install folder before running it, a success returns its output,
        a silent cancel (exit 3) reads "Uninstall cancelled.", and a folder with no wizard install
        is refused without running anything.
        """
        p, calls = self.plan(), []
        self.wizard_install(p)

        def busy(exe, args):
            """Stand-in uninstaller: record the command line, exit 4 as one already running would."""
            calls.append([exe, *args])
            return 4, "Setup or uninstall of Generic Company Test App is already running."

        os.chdir(p["install_dir"])
        with self.assertRaises(installer.UninstallerFailed) as failed:
            installer.run_uninstaller(p, installer.uninstall_args(self.root, quiet=True), run=busy)
        self.assertEqual(failed.exception.code, 4)
        self.assertIn("already running", str(failed.exception))
        self.assertEqual(calls, [[os.path.join(p["install_dir"], "uninstall.exe"), "-quiet", "-root", os.path.abspath(self.root)]])
        self.assertTrue(os.path.samefile(os.getcwd(), tempfile.gettempdir()))  # left the folder for it
        with open(os.path.join(p["install_dir"], "notes.txt")) as f:
            self.assertEqual(f.read(), "changed by the user")
        self.assertEqual(installer.run_uninstaller(p, [], run=lambda exe, args: (0, "Removed Generic Company Test App 0.2.0.")),
                         "Removed Generic Company Test App 0.2.0.")
        with self.assertRaises(installer.UninstallerFailed) as cancelled:
            installer.run_uninstaller(p, [], run=lambda exe, args: (installer.CANCELLED, ""))
        self.assertEqual((cancelled.exception.code, str(cancelled.exception)), (3, "Uninstall cancelled."))
        elsewhere = installer.plan(self.program, self.src, env={}, root=os.path.join(self.root, "x"))
        with self.assertRaises(RuntimeError):  # no install there: nothing to run
            installer.run_uninstaller(elsewhere, [], run=busy)
        self.assertEqual(len(calls), 1)

    def entry(self, p, folder):
        """The sandbox uninstall entry naming folder, as a setup writes it."""
        os.makedirs(self.root, exist_ok=True)
        with open(p["registry_file"], "w") as f:
            json.dump({p["registry_key"]: {"InstallLocation": folder}}, f)

    def test_located_finds_a_wizard_install_elsewhere(self):
        """The sandbox entry leads to a wizard install in another folder, but not when missing or stale."""
        p = self.plan()

        def real(script):
            """Fail the test: a sandbox must read registry.json, never PowerShell."""
            raise AssertionError("read the real registry in a sandbox")

        self.assertIs(installer.located(p, real), p)  # no entry
        elsewhere = dict(p, install_dir=os.path.join(self.root, "Apps", "Journal"))
        self.entry(p, elsewhere["install_dir"])
        self.assertIs(installer.located(p, real), p)  # a stale entry
        self.wizard_install(elsewhere)
        there = installer.located(p, real)
        self.assertEqual(there["install_dir"], elsewhere["install_dir"])
        calls = []
        self.assertEqual(installer.run_uninstaller(there, ["-quiet"], run=lambda exe, args: calls.append(exe) or (0, "")), "")
        self.assertEqual(calls, [os.path.join(elsewhere["install_dir"], "uninstall.exe")])

    def test_located_never_clears_an_install_elsewhere(self):
        """Another program's install, or a folder with no marker, where the entry points is refused; the entry stays."""
        p = self.plan()
        elsewhere = dict(p, install_dir=os.path.join(self.root, "Apps", "Journal"))
        self.entry(p, elsewhere["install_dir"])
        self.wizard_install(elsewhere, "GenericCompany.Other")
        with self.assertRaises(RuntimeError):
            installer.located(p)
        os.remove(os.path.join(elsewhere["install_dir"], installer.MARKER))
        with self.assertRaises(RuntimeError):
            installer.located(p)
        with open(p["registry_file"]) as f:
            self.assertIn(p["registry_key"], json.load(f))

    def test_located_reads_the_real_registry(self):
        """Outside a sandbox the entry is read with Get-ItemProperty; a relative or empty answer is ignored."""
        p = installer.plan(self.program, self.src, env={}, interpreter=r"C:\Py\python.exe")
        folder, scripts = os.path.join(self.root, "Apps", "Journal"), []
        self.wizard_install(dict(p, install_dir=folder))
        there = installer.located(p, lambda script: scripts.append(script) or folder)
        self.assertEqual(there["install_dir"], folder)
        self.assertIn("Get-ItemProperty -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
                      "\\GenericCompany.Test' -Name InstallLocation", scripts[0])
        self.assertIs(installer.located(p, lambda script: "Apps"), p)  # never a relative folder
        self.assertIs(installer.located(p, lambda script: ""), p)

    @unittest.skipUnless(os.name == "nt", "PowerShell")
    def test_read_powershell(self):
        """Real PowerShell: a non-ASCII character comes back intact (UTF-8), and a missing key reads as ""."""
        self.assertEqual(installer.read_powershell("'M' + [char]0xF6 + 'tley'"), "M\u00f6tley")
        p = installer.plan(self.program, self.src, env={}, interpreter=r"C:\Py\python.exe")
        p["registry_key"] = installer.UNINSTALL_KEY + "\\GenericCompany.NoSuchProgram.Test"
        self.assertEqual(installer.install_location(p), "")

    @unittest.skipUnless(os.name == "nt", "cmd.exe")
    def test_run_and_wait_returns_the_exit_code(self):
        """cmd.exe exiting 4 gives (4, its output); a program that does not exist raises OSError."""
        self.assertEqual(installer.run_and_wait("cmd.exe", ["/d", "/c", "echo kept & exit 4"]), (4, "kept"))
        with self.assertRaises(OSError):
            installer.run_and_wait(os.path.join(self.tmp.name, "uninstall.exe"), [])

    @unittest.skipUnless(os.name == "nt", "Windows shortcuts")
    def test_real_shortcut_in_sandbox(self):
        """Real PowerShell makes the .lnk in the sandbox Start menu; uninstall removes it and its emptied folder."""
        p = self.plan()
        installer.install(p, installer.run_powershell)
        link = p["shortcuts"][0]["path"]
        self.assertTrue(os.path.isfile(link))
        installer.uninstall(p, installer.run_powershell)
        self.assertFalse(os.path.exists(link))
        self.assertFalse(os.path.exists(os.path.dirname(link)))


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=27e424fb484f9bad39080c9bb9004e696b59a3a116fd886f606f4463b16df66b ====
