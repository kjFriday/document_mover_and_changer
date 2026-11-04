# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/installer.py
# About: Install or uninstall a Generic Company program for the current user (no admin rights).
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Install or uninstall a Generic Company program for the current user (no admin rights).

Install copies the program to %LOCALAPPDATA%\\Programs\\Generic Company Inc\\<name>\\ with an install.json marker,
adds a Start-menu shortcut (and, if asked, a desktop one) with the program's pixel icon, and registers
an uninstall entry under HKCU\\...\\CurrentVersion\\Uninstall\\<app id> so it shows in Apps & features.
Uninstall removes all three. The shared database and settings are never touched (--purge also removes
the program's own data folder). An install that a setup made by Generic Company Wizard Maker left (its marker names
the installer), here or in the folder its uninstall entry names, is removed by its own uninstall.exe instead,
which keeps the files changed since.

Three layers, so the tests never touch the real system:
  plan()      pure: every path, shortcut and registry value
  ps_script() pure: the PowerShell that makes shortcuts and writes the registry (fed on stdin)
  install() / uninstall()  do it, with a replaceable command runner
With root=DIR everything lands under DIR instead (a sandbox) and the registry becomes DIR\\registry.json.

Who calls it: main.py (do_install, program) for --install, --uninstall and the Help menu. It calls
paths.py for %LOCALAPPDATA%, PowerShell (for shortcuts and the registry) and, for a Wizard Maker
install, that install's uninstall.exe.

Main flow of an install:
1. plan() turns a Program into plain data: install folder, file copies, shortcuts, registry values.
2. install() copies the files, writes install.json (the marker that proves the folder is ours),
   then runs ps_script() to make the shortcuts and the uninstall entry.
Of an uninstall:
1. located() follows the uninstall entry to the folder the program is really in.
2. wizard_uninstaller() decides who removes it: a Wizard Maker install goes to run_uninstaller(),
   anything else to uninstall(), which removes shortcuts, entry and folder (after safe_to_remove()).

Types: Program (what to install), UninstallerFailed (an uninstaller's exit code). A plan is a dict;
see plan() for its keys. Start reading at plan(), then install() and uninstall().
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

from docpipe import paths

# the per-user uninstall list Apps & features reads, in PowerShell's registry-drive spelling
UNINSTALL_KEY = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
MARKER = "install.json"  # written into the install folder; uninstall deletes only a folder that holds ours
WIZARD_UNINSTALLER = "uninstall.exe"  # what a setup made by Generic Company Wizard Maker leaves in the install folder
CANCELLED = 3  # that uninstaller's exit code when the user cancels it in its window


class Program:
    """What gets installed: identity, files (relative to source), and how the shortcut starts it."""

    def __init__(self, app_id, name, version, publisher, files, script_args, icon="icon/app.ico"):
        """Store the program's description.

        app_id names the registry entry and the marker; name is the install folder and shortcut name;
        files are "/"-separated paths relative to the source folder; script_args are the shortcut's
        arguments after pythonw.exe, where "{dir}" stands for the install folder; icon is the icon
        file relative to the install folder.
        """
        self.app_id, self.name, self.version, self.publisher = app_id, name, version, publisher
        self.files, self.script_args, self.icon = list(files), list(script_args), icon


def program_files(source_dir, include, exclude_prefixes=("test_",)):
    """Relative paths under source_dir for the given top-level files and folders, tests and caches left out.

    include names files or folders directly under source_dir; folders are walked in sorted order,
    skipping __pycache__ and tests folders, .pyc files and names starting with exclude_prefixes.
    Missing entries are skipped. Paths use "/" on every system.
    """
    out = []
    for item in include:
        full = os.path.join(source_dir, item)
        if os.path.isdir(full):
            for folder, dirs, files in os.walk(full):
                dirs[:] = sorted(d for d in dirs if d != "__pycache__" and d != "tests")
                for f in sorted(files):
                    if not f.startswith(exclude_prefixes) and not f.endswith(".pyc"):
                        out.append(os.path.relpath(os.path.join(folder, f), source_dir).replace(os.sep, "/"))
        elif os.path.isfile(full) and not os.path.basename(item).startswith(exclude_prefixes):
            out.append(item)
    return out


def pythonw(executable=None):
    """pythonw.exe next to the running interpreter (no console window), or the interpreter itself."""
    exe = executable or sys.executable
    candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return candidate if os.path.isfile(candidate) else exe


def locations(env=None, root=None):
    """(programs dir, Start-menu dir, desktop dir, registry file or None).

    env is the environment to read (None: os.environ). With root, all four lie under root and the
    registry file is root\\registry.json; otherwise they are the user's real folders and None stands
    for the real registry.
    """
    env = os.environ if env is None else env
    if root:
        root = os.path.abspath(root)
        return (os.path.join(root, "Programs", "Generic Company Inc"), os.path.join(root, "Start Menu", "Generic Company Inc"),
                os.path.join(root, "Desktop"), os.path.join(root, "registry.json"))
    appdata = env.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    profile = env.get("USERPROFILE") or os.path.expanduser("~")
    return (os.path.join(paths.local_appdata(env), "Programs", "Generic Company Inc"),
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Generic Company Inc"),
            os.path.join(profile, "Desktop"), None)


def _quote(arg):
    """arg in double quotes when it holds a space or is empty (and is not quoted already), for a command line."""
    return f'"{arg}"' if (" " in arg or not arg) and not arg.startswith('"') else arg


def plan(program, source_dir, env=None, root=None, desktop=False, interpreter=None, today=None):
    """Everything install() and uninstall() will do, as plain data.

    program is a Program; source_dir holds its files; env and root as for locations(); desktop adds a
    desktop shortcut; interpreter and today replace sys.executable and the date (for tests).
    Reads the size of every file (for EstimatedSize); touches nothing else.

    The dict's keys: app_id, name, version, install_dir, programs_dir, copies [(source, target)],
    shortcuts [{path, target, args, workdir, icon, description}], registry_file (None: the real
    registry), registry_key and registry (the uninstall entry's values).

    The uninstall entry follows the Windows Uninstall key conventions: DisplayName and DisplayVersion
    are shown in Apps & features, UninstallString is the command its Uninstall button runs,
    QuietUninstallString the same without prompts, InstallDate is YYYYMMDD, NoModify/NoRepair = 1
    hide the Modify and Repair buttons, and EstimatedSize is in KB.
    """
    programs, start_menu, desktop_dir, registry_file = locations(env, root)
    install_dir = os.path.join(programs, program.name)
    target = pythonw(interpreter)
    args = [a.replace("{dir}", install_dir) for a in program.script_args]
    # a sandboxed install must uninstall from the same sandbox
    sandbox = ["--root", os.path.abspath(root)] if root else []
    uninstall = " ".join(_quote(a) for a in [target, *args, "--uninstall", *sandbox])
    icon = os.path.join(install_dir, *program.icon.split("/"))
    links = [os.path.join(start_menu, program.name + ".lnk")]
    if desktop:
        links.append(os.path.join(desktop_dir, program.name + ".lnk"))
    size_kb = sum(os.path.getsize(os.path.join(source_dir, f)) for f in program.files) // 1024 + 1  # rounded up
    return {
        "app_id": program.app_id,
        "name": program.name,
        "version": program.version,
        "install_dir": install_dir,
        "programs_dir": programs,
        "copies": [(os.path.join(source_dir, *f.split("/")), os.path.join(install_dir, *f.split("/")))
                   for f in program.files],
        "shortcuts": [{"path": p, "target": target, "args": " ".join(_quote(a) for a in args),
                       "workdir": install_dir, "icon": icon, "description": f"{program.name} {program.version}"}
                      for p in links],
        "registry_file": registry_file,
        "registry_key": UNINSTALL_KEY + "\\" + program.app_id,
        "registry": {
            "DisplayName": f"{program.name} {program.version}",
            "DisplayVersion": program.version,
            "Publisher": program.publisher,
            "DisplayIcon": icon,
            "InstallLocation": install_dir,
            "UninstallString": uninstall,
            "QuietUninstallString": uninstall + " --quiet",
            "InstallDate": (today or datetime.date.today()).strftime("%Y%m%d"),
            "NoModify": 1,
            "NoRepair": 1,
            "EstimatedSize": size_kb,
        },
    }


def ps_literal(text):
    """A PowerShell single-quoted string: nothing inside is expanded; ' is doubled."""
    return "'" + str(text).replace("'", "''") + "'"


def ps_script(p, remove=False):
    """PowerShell that creates (or removes) the shortcuts and the registry entry (unless sandboxed).

    p is a plan. Every value goes in through ps_literal, so paths with spaces or quotes are safe.
    In a sandbox (p["registry_file"] set) the script makes only the shortcuts; install() and
    uninstall() write the registry file themselves.

    Removal: delete each shortcut (a missing one is fine), then the Start-menu folder of the first
    shortcut if it is now empty (other programs of the company may share it), then the registry key.

    Creation: a .lnk shortcut is made through the WScript.Shell COM object: CreateShortcut() returns
    a shortcut object for the path, its properties are set and Save() writes the file. Then the
    registry key is created and each value written; ints become DWORD (32-bit) values, the rest strings.
    """
    lines = ["$ErrorActionPreference = 'Stop'"]  # any failing command ends the script with an error
    if remove:
        for s in p["shortcuts"]:
            lines.append(f"Remove-Item -LiteralPath {ps_literal(s['path'])} -Force -ErrorAction SilentlyContinue")
        folder = os.path.dirname(p["shortcuts"][0]["path"])
        lines.append(f"$f = {ps_literal(folder)}; if ((Test-Path -LiteralPath $f) -and "
                     "-not (Get-ChildItem -LiteralPath $f)) { Remove-Item -LiteralPath $f }")
        if not p["registry_file"]:
            lines.append(f"Remove-Item -LiteralPath {ps_literal(p['registry_key'])} -Recurse -ErrorAction SilentlyContinue")
        return "\n".join(lines) + "\n"
    lines.append("$shell = New-Object -ComObject WScript.Shell")
    for s in p["shortcuts"]:
        lines += [
            f"New-Item -ItemType Directory -Force -Path {ps_literal(os.path.dirname(s['path']))} | Out-Null",
            f"$l = $shell.CreateShortcut({ps_literal(s['path'])})",
            f"$l.TargetPath = {ps_literal(s['target'])}",
            f"$l.Arguments = {ps_literal(s['args'])}",
            f"$l.WorkingDirectory = {ps_literal(s['workdir'])}",
            f"$l.IconLocation = {ps_literal(s['icon'] + ',0')}",  # ",0": the first icon in the file
            f"$l.Description = {ps_literal(s['description'])}",
            "$l.Save()",
        ]
    if not p["registry_file"]:
        key = ps_literal(p["registry_key"])
        lines.append(f"New-Item -Path {key} -Force | Out-Null")
        for name, value in p["registry"].items():
            kind = "DWord" if isinstance(value, int) else "String"
            lines.append(f"New-ItemProperty -Path {key} -Name {ps_literal(name)} -Value {ps_literal(value)} "
                         f"-PropertyType {kind} -Force | Out-Null")
    return "\n".join(lines) + "\n"


def run_powershell(script):
    """The real runner: the script goes on stdin, so no quoting reaches the command line.

    "-Command -" makes PowerShell read the script from stdin; -NoProfile skips the user's profile
    script and -ExecutionPolicy Bypass lets it run where scripts are blocked. Raises RuntimeError
    with PowerShell's error text when it exits non-zero.
    """
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window flashes up; 0 off Windows
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-Command", "-"], input=script, capture_output=True, text=True, creationflags=flags)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or f"PowerShell exited {done.returncode}")


def read_powershell(script):
    """Run a script like run_powershell -> what it printed (it sets its output to UTF-8 first).

    Without the UTF-8 line PowerShell writes in the console code page, and a non-ASCII folder name
    would come back garbled. Raises RuntimeError when PowerShell exits non-zero.
    """
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-Command", "-"], input="[Console]::OutputEncoding = [Text.Encoding]::UTF8\n" + script,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or f"PowerShell exited {done.returncode}")
    return done.stdout.strip()


def _read_registry_file(path):
    """The sandbox registry file as a dict ({key: {name: value}}), or {} when it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_registry_file(path, data):
    """Write the sandbox registry file (sorted keys, LF), creating its folder."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_marker(install_dir):
    """The install.json in install_dir as a dict, or None when it is missing or not JSON."""
    try:
        with open(os.path.join(install_dir, MARKER), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def install(p, runner=run_powershell):
    """Copy the files, write the marker, then shortcuts and registry. Reinstalling over an older copy is fine.

    p is a plan; runner runs the PowerShell (tests pass a recorder). -> the install folder.
    Raises RuntimeError when the folder's marker names another program. Files from an older version
    that the new one no longer ships are left in place (they are not in the new marker either).

    Steps:
    1. Refuse a folder that belongs to another program.
    2. Copy every file (copy2 keeps the modified times).
    3. Write install.json: app id, name, version, the files and shortcuts, for uninstall to read.
    4. In a sandbox, add the uninstall entry to registry.json.
    5. Run the script that makes the shortcuts (and, outside a sandbox, the registry entry).
    """
    marker = read_marker(p["install_dir"])
    # Known limitation: an existing folder with no marker at all passes this check and is installed into
    if os.path.exists(p["install_dir"]) and (marker or {}).get("app_id") not in (None, p["app_id"]):
        raise RuntimeError(f"{p['install_dir']} belongs to another program")
    for src, dst in p["copies"]:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    with open(os.path.join(p["install_dir"], MARKER), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"app_id": p["app_id"], "name": p["name"], "version": p["version"],
                   "files": [os.path.relpath(d, p["install_dir"]).replace(os.sep, "/") for _, d in p["copies"]],
                   "shortcuts": [s["path"] for s in p["shortcuts"]]}, f, indent=2)
    if p["registry_file"]:
        data = _read_registry_file(p["registry_file"])
        data[p["registry_key"]] = p["registry"]
        _write_registry_file(p["registry_file"], data)
    runner(ps_script(p))
    return p["install_dir"]


def safe_to_remove(p):
    """Only a folder under the programs dir whose marker names this program.

    -> True when the install folder lies strictly inside the programs dir (not the dir itself) and
    its install.json names p's app id. This is what stops rmtree from ever reaching a folder that is
    not an install of this program.
    """
    folder = os.path.abspath(p["install_dir"])
    inside = os.path.commonpath([folder, os.path.abspath(p["programs_dir"])]) == os.path.abspath(p["programs_dir"])
    marker = read_marker(folder)
    return inside and folder != os.path.abspath(p["programs_dir"]) and bool(marker) and marker.get("app_id") == p["app_id"]


def uninstall(p, runner=run_powershell, purge_dir=None):
    """Remove shortcuts, registry entry and install folder; the database is never removed.

    p is a plan; runner runs the PowerShell; purge_dir, when given, is removed too (main.py passes the
    hub's own data folder, which holds its settings). -> True when an install folder was removed,
    False when there was none. Raises RuntimeError (after the shortcuts and entry are gone) when the
    folder is there but safe_to_remove() refuses it.

    Steps:
    1. Add the shortcuts the marker lists that the plan does not (a desktop shortcut made by an
       earlier --desktop-shortcut install); only their paths matter for removal.
    2. Run the removal script, then drop the sandbox registry entry.
    3. Check the folder, step out of it and delete it.
    4. Delete purge_dir.
    """
    marker = read_marker(p["install_dir"]) or {}
    extra =[s for s in marker.get("shortcuts", []) if s not in [x["path"] for x in p["shortcuts"]]]
    p = dict(p, shortcuts=p["shortcuts"] + [dict(p["shortcuts"][0], path=s) for s in extra])
    runner(ps_script(p, remove=True))
    if p["registry_file"]:
        data = _read_registry_file(p["registry_file"])
        data.pop(p["registry_key"], None)
        _write_registry_file(p["registry_file"], data)
    removed = False
    if os.path.isdir(p["install_dir"]):
        if not safe_to_remove(p):
            raise RuntimeError(f"refusing to delete {p['install_dir']}: no matching {MARKER}")
        os.chdir(tempfile.gettempdir())  # the running script's folder can't be removed while it is the cwd (Windows locks it)
        shutil.rmtree(p["install_dir"])
        removed = True
    if purge_dir and os.path.isdir(purge_dir):
        shutil.rmtree(purge_dir)
    return removed


class UninstallerFailed(RuntimeError):
    """A wizard-made install's uninstaller did not finish; .code is its exit code (CANCELLED, 4 refused, ...)."""

    def __init__(self, code, message):
        """Keep the uninstaller's exit code (non-zero) beside its message."""
        super().__init__(message)
        self.code = code


def wizard_uninstaller(p):
    """The uninstaller of an install that a setup made by Generic Company Wizard Maker left in the install folder (its
    marker names this program and an installer), or None for this program's own install. Such an install is
    removed by that uninstaller, which takes away only the files still as installed."""
    marker = read_marker(p["install_dir"]) or {}
    if marker.get("app_id") == p["app_id"] and marker.get("installer"):
        return os.path.join(p["install_dir"], WIZARD_UNINSTALLER)
    return None


def install_location(p, read=read_powershell):
    """The folder the uninstall entry names, or "": from root\\registry.json in a sandbox, else the registry.

    read runs a PowerShell script and returns its output (tests pass a stand-in). A missing key or
    value prints nothing, so the result is "" then.
    """
    if p["registry_file"]:
        entry = _read_registry_file(p["registry_file"]).get(p["registry_key"])
        location = entry.get("InstallLocation") if isinstance(entry, dict) else None
        return location if isinstance(location, str) else ""
    return read(f"(Get-ItemProperty -LiteralPath {ps_literal(p['registry_key'])} -Name InstallLocation "
                "-ErrorAction SilentlyContinue).InstallLocation\n")


def located(p, read=read_powershell):
    """p aimed at the install its uninstall entry names when that lies outside p's install folder: a setup made
    by Generic Company Wizard Maker installs where the user picks. Only such an install (see wizard_uninstaller) is handed
    on; any other folder still there is refused, so its entry and shortcuts are never cleared.

    -> p itself when the entry is missing, relative, names p's own folder or names a folder that no
    longer exists; else a copy of p with install_dir set to that folder. Raises RuntimeError when
    that folder holds something other than a Wizard Maker install of this program.
    """
    location = install_location(p, read)
    if not os.path.isabs(location):
        return p
    location = os.path.normpath(location)
    if os.path.normcase(location) == os.path.normcase(os.path.normpath(p["install_dir"])):
        return p
    if not os.path.exists(location):
        return p  # a stale entry: clearing it orphans nothing
    there = dict(p, install_dir=location)
    if not wizard_uninstaller(there):
        raise RuntimeError(f"{p['name']} is installed in {location}, which this copy cannot uninstall: "
                           "use Apps & features")
    return there


def uninstall_args(root=None, quiet=False, purge=False):
    """The flags --uninstall passes on to that uninstaller.

    Wizard Maker's uninstall.exe spells them with one dash (-quiet, -purge, -root DIR).
    """
    return (["-quiet"] if quiet else []) + (["-purge"] if purge else []) + (["-root", os.path.abspath(root)] if root else [])


def run_and_wait(exe, args):
    """The real runner for a program: wait for it -> (exit code, what it printed). It starts in the temp
    folder, so it never holds the folder it removes.

    Raises OSError when exe cannot be started.
    """
    done = subprocess.run([exe, *args], cwd=tempfile.gettempdir(), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode, (done.stdout + done.stderr).strip()


def run_uninstaller(p, args, run=run_and_wait):
    """Remove a wizard-made install (see wizard_uninstaller) through its uninstaller, run with args -> what it
    printed. Raises UninstallerFailed, with its exit code, when it does not finish.

    run starts the program and waits (tests pass a stand-in). Raises RuntimeError when p's folder
    holds no Wizard Maker install, or the uninstaller cannot be started. With no output of its own,
    a cancel reads "Uninstall cancelled." and any other failure names the exit code.
    """
    exe = wizard_uninstaller(p)
    if not exe:
        raise RuntimeError(f"{p['install_dir']} holds no wizard-made install of {p['name']}")
    os.chdir(tempfile.gettempdir())  # this process may outlive the uninstaller: its cwd must not hold the folder
    try:
        code, said = run(exe, args)
    except OSError as e:
        raise RuntimeError(f"run {exe}: {e}") from e
    if code:
        raise UninstallerFailed(code, said or ("Uninstall cancelled." if code == CANCELLED
                                               else f"{WIZARD_UNINSTALLER} exited with {code}"))
    return said

# ==== stamp v1 | author=kjFriday | hmac-sha256=5df27a318ec2893eb6a6e8d4a3d1388dae7d5f70b2cd5c160bd0d9efd11eb205 ====
