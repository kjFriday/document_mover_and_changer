"""Install or uninstall an ACME program for the current user (no admin rights needed).

Install copies the program to %LOCALAPPDATA%\\Programs\\ACME Inc\\<name>\\ with an install.json marker,
adds a Start-menu shortcut (and, if asked, a desktop one) with the program's pixel icon, and registers
an uninstall entry under HKCU\\...\\CurrentVersion\\Uninstall\\<app id> so it shows in Apps & features.
Uninstall removes all three. The shared database and settings are never touched (--purge also removes
the program's own data folder).

Three layers, so the tests never touch the real system:
  plan()      pure: every path, shortcut and registry value
  ps_script() pure: the PowerShell that makes shortcuts and writes the registry (fed on stdin)
  install() / uninstall()  do it, with a replaceable command runner
With root=DIR everything lands under DIR instead (a sandbox) and the registry becomes DIR\\registry.json.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

from docpipe import paths

UNINSTALL_KEY = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
MARKER = "install.json"


class Program:
    """What gets installed: identity, files (relative to source), and how the shortcut starts it."""

    def __init__(self, app_id, name, version, publisher, files, script_args, icon="icon/app.ico"):
        self.app_id, self.name, self.version, self.publisher = app_id, name, version, publisher
        self.files, self.script_args, self.icon = list(files), list(script_args), icon


def program_files(source_dir, include, exclude_prefixes=("test_",)):
    """Relative paths under source_dir for the given top-level files and folders, tests and caches left out."""
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
    """(programs dir, Start-menu dir, desktop dir, registry file or None)."""
    env = os.environ if env is None else env
    if root:
        root = os.path.abspath(root)
        return (os.path.join(root, "Programs", "ACME Inc"), os.path.join(root, "Start Menu", "ACME Inc"),
                os.path.join(root, "Desktop"), os.path.join(root, "registry.json"))
    appdata = env.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    profile = env.get("USERPROFILE") or os.path.expanduser("~")
    return (os.path.join(paths.local_appdata(env), "Programs", "ACME Inc"),
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "ACME Inc"),
            os.path.join(profile, "Desktop"), None)


def _quote(arg):
    return f'"{arg}"' if (" " in arg or not arg) and not arg.startswith('"') else arg


def plan(program, source_dir, env=None, root=None, desktop=False, interpreter=None, today=None):
    """Everything install() and uninstall() will do, as plain data."""
    programs, start_menu, desktop_dir, registry_file = locations(env, root)
    install_dir = os.path.join(programs, program.name)
    target = pythonw(interpreter)
    args = [a.replace("{dir}", install_dir) for a in program.script_args]
    sandbox = ["--root", os.path.abspath(root)] if root else []
    uninstall = " ".join(_quote(a) for a in [target, *args, "--uninstall", *sandbox])
    icon = os.path.join(install_dir, *program.icon.split("/"))
    links = [os.path.join(start_menu, program.name + ".lnk")]
    if desktop:
        links.append(os.path.join(desktop_dir, program.name + ".lnk"))
    size_kb = sum(os.path.getsize(os.path.join(source_dir, f)) for f in program.files) // 1024 + 1
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
    """PowerShell that creates (or removes) the shortcuts and the registry entry (unless sandboxed)."""
    lines = ["$ErrorActionPreference = 'Stop'"]
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
            f"$l.IconLocation = {ps_literal(s['icon'] + ',0')}",
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
    """The real runner: the script goes on stdin, so no quoting reaches the command line."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-Command", "-"], input=script, capture_output=True, text=True, creationflags=flags)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or f"PowerShell exited {done.returncode}")


def _read_registry_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_registry_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_marker(install_dir):
    try:
        with open(os.path.join(install_dir, MARKER), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def install(p, runner=run_powershell):
    """Copy the files, write the marker, then shortcuts and registry. Reinstalling over an older copy is fine."""
    marker = read_marker(p["install_dir"])
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
    """Only a folder under the programs dir whose marker names this program."""
    folder = os.path.abspath(p["install_dir"])
    inside = os.path.commonpath([folder, os.path.abspath(p["programs_dir"])]) == os.path.abspath(p["programs_dir"])
    marker = read_marker(folder)
    return inside and folder != os.path.abspath(p["programs_dir"]) and bool(marker) and marker.get("app_id") == p["app_id"]


def uninstall(p, runner=run_powershell, purge_dir=None):
    """Remove shortcuts, registry entry and install folder; the database is never removed."""
    marker = read_marker(p["install_dir"]) or {}
    extra = [s for s in marker.get("shortcuts", []) if s not in [x["path"] for x in p["shortcuts"]]]
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
        os.chdir(tempfile.gettempdir())  # the running script's folder can't be removed while it is the cwd
        shutil.rmtree(p["install_dir"])
        removed = True
    if purge_dir and os.path.isdir(purge_dir):
        shutil.rmtree(purge_dir)
    return removed
