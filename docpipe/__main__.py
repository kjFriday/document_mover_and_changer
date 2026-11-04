# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/__main__.py
# About: Generic Company Doc Pipeline: orders in, document files and a manifest out.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Generic Company Doc Pipeline: orders in, document files and a manifest out.

    python -m docpipe [--db PATH | --mock]     open the window
    python -m docpipe --cli [--out out] [--orders N] [--register] [--db PATH | --mock]
    python -m docpipe --install | --uninstall  install for this user / remove it again

It reads the shared Generic Company database by path (--db, GENERIC_COMPANY_DB, the saved setting, or
%LOCALAPPDATA%\\Generic Company Inc\\generic_company.db) and falls back to the bundled mock/ snapshot when there is none.
--register writes back a `documents` row for each order that had none and one `documents.generated`
event summarising the run. The event is stored with status "sent", so the notification hub's
dispatcher, which only handles "pending" events, records it without sending anything.

`python -m docpipe` runs this module, and the installed launcher docpipe_app.py calls the same
main(). main() checks the flags in this order:

1. --version prints the name and version and exits 0.
2. --install / --uninstall go to do_install(), which drives docpipe.installer. An install made by a
   Generic Company Wizard Maker setup is handed to that setup's own uninstaller.
3. Otherwise paths.resolve_db() picks the database path (flag, environment, saved setting, default).
4. --cli runs pipeline.run() once in cli() and prints a summary; no tkinter is imported on this path.
5. With no mode flag the Tk window (docpipe.gui) opens and starts a read-only run straight away.
   --smoke FILE then writes a JSON report once that run finishes and closes the window, for the
   portfolio's verify script.

Exit codes: 0 done, 1 error, and a Wizard Maker uninstaller's own code passed through (3 cancelled,
4 refused, ...).
"""

import argparse
import json
import os
import sys

from docpipe import APP_ID, NAME, PUBLISHER, __version__, installer, paths, pipeline

# The project folder (the one holding docpipe/, icon/ and mock/), not this package's folder.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# What --install copies, relative to HERE. It must list the same entries as setup.json "files"
# (test_app checks this), so --install and a Wizard Maker setup install the same program.
RUNTIME = ["docpipe_app.py", "docpipe", "icon", "mock", "README.md"]


def program():
    """Describe this program for docpipe.installer: identity, runtime files and how the shortcut starts it.

    The files are RUNTIME expanded to single files, minus tests, test_* files and caches. The shortcut
    runs docpipe_app.py from the install folder; installer.plan() replaces "{dir}" with that folder.
    """
    return installer.Program(APP_ID, NAME, __version__, PUBLISHER, installer.program_files(HERE, RUNTIME),
                             ["{dir}\\docpipe_app.py"])


def do_install(remove=False, root=None, desktop=False, purge=False, quiet=False):
    """Install this program for the current user, or remove it; -> the message to show.

    root sandboxes everything (files, shortcuts, a registry.json stand-in) under that folder; desktop
    adds a desktop shortcut; purge also deletes this program's data folder on uninstall; quiet is
    passed on to a Wizard Maker uninstaller. The shared database is never deleted.

    Steps:
    1. Build the install plan (pure data) from program() and HERE.
    2. Install: copy the files, write the install marker, create the shortcuts and the Apps &
       features entry.
    3. Uninstall: aim the plan at the folder the Apps & features entry names (located()). If a Wizard
       Maker setup made that install, run its uninstaller and return what it printed; otherwise
       remove the shortcuts, entry and folder here.

    Raises installer.UninstallerFailed (with .code) when a Wizard Maker uninstaller stops, and
    RuntimeError or OSError for anything else that goes wrong.

    Known limitation: the purge folder is always paths.data_dir(APP_ID) under the real
    %LOCALAPPDATA%, even with root set, and that folder also holds the window's default output.
    """
    plan = installer.plan(program(), HERE, root=root, desktop=desktop)
    if remove:
        plan = installer.located(plan)
        if installer.wizard_uninstaller(plan):
            # a setup made by Generic Company Wizard Maker installed it: its uninstaller keeps the files changed since
            return installer.run_uninstaller(plan, installer.uninstall_args(root, quiet, purge)) or f"{NAME} uninstalled."
        gone = installer.uninstall(plan, purge_dir=paths.data_dir(APP_ID) if purge else None)
        return f"{NAME} uninstalled." + ("" if gone else " (It was not installed.)") + " The database is kept."
    installer.install(plan)
    return f"{NAME} {__version__} installed in {plan['install_dir']}. Find it in the Start menu under Generic Company Inc."


def parse(argv):
    """Parse the command-line flags in argv (without the program name); -> an argparse Namespace.

    --mock with no value means the bundled snapshot (pipeline.MOCK); without --mock, args.mock is None,
    which callers read as "use the database when there is one".
    """
    ap = argparse.ArgumentParser(prog="python -m docpipe", description=NAME)
    ap.add_argument("--db", help="shared database file")
    ap.add_argument("--mock", nargs="?", const=pipeline.MOCK, default=None, metavar="DIR",
                    help="use the mock snapshot (default: the bundled one)")
    ap.add_argument("--cli", action="store_true", help="run once in the console instead of opening the window")
    ap.add_argument("--out", help="output folder (window default: %%LOCALAPPDATA%%\\Generic Company Inc\\GenericCompany.DocPipe\\out)")
    ap.add_argument("--orders", type=int, default=pipeline.ORDERS, help="how many of the newest orders")
    ap.add_argument("--register", action="store_true", help="write documents rows and a summary event to the database")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--desktop-shortcut", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--root", help="sandbox: install under this folder instead")
    ap.add_argument("--smoke", metavar="FILE", help="open the window, run once, write a JSON report, close")
    return ap.parse_args(argv)


def tell(message, quiet):
    """Print message, and also show it in a message box when there is no console and quiet is false.

    Under pythonw.exe (the Start-menu shortcut and Apps & features) sys.stdout is None and print()
    writes nowhere, so the box is the only way the user sees the result.
    """
    print(message)
    if not quiet and sys.stdout is None:  # pythonw: no console
        from tkinter import messagebox
        messagebox.showinfo(NAME, message)


def cli(args, db_path):
    """Run the pipeline once in the console and print a summary; -> the exit code (0 done, 1 refused).

    args are parse()'s flags; db_path is the resolved database path, which may not exist.

    Steps:
    1. Decide the source: the database when it is usable and --mock was not given, else the snapshot.
    2. Refuse --register without the database (exit 1, message on stderr): there is nowhere to write.
    3. Run pipeline.run() into --out (default "out" in the current folder) and print the source, the
       counts, the manifest path and its hash prefix, and what was registered.
    """
    kind, text = pipeline.describe_source(db_path, args.mock is not None)
    if args.register and kind != "db":
        print(f"--register needs the shared database ({text})", file=sys.stderr)
        return 1
    result = pipeline.run(args.out or "out", db_path if kind == "db" else None, args.mock or pipeline.MOCK,
                          args.orders, args.register)
    print(f"source: {'shared database ' + db_path if kind == 'db' else text}")
    print(f"orders: {result['orders']}; documents written: {len(result['manifest'])} {result['kinds']}")
    print(f"orders with no documents row: {result['missing']}")
    print(f"manifest: {os.path.join(result['out'], 'manifest.jsonl')}  sha256 {result['sha256'][:16]}")
    if result["event"]:
        print(f"database: {result['registered']} documents rows added; documents.generated event {result['event']}")
    return 0


def main(argv=None):
    """Run the program with argv (default: sys.argv[1:]); -> the process exit code.

    The order of the checks is described in the module docstring. The window path blocks in Tk's
    main loop until the window closes. Install errors are shown with tell(), never raised.
    """
    args = parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        tell(f"{NAME} {__version__}", args.quiet)
        return 0
    if args.install or args.uninstall:
        try:
            tell(do_install(args.uninstall, args.root, args.desktop_shortcut, args.purge, args.quiet), args.quiet)
        except installer.UninstallerFailed as e:  # its exit code goes on: 3 cancelled, 4 refused, ...
            # a cancel was the user's own choice in the uninstaller's window: no message box for it
            tell(f"{NAME}: {e}", args.quiet or e.code == installer.CANCELLED)
            return e.code
        except Exception as e:
            tell(f"{NAME}: {e}", args.quiet)
            return 1
        return 0
    db_path = paths.resolve_db(args.db, APP_ID)
    if args.cli:
        return cli(args, db_path)

    # imported here, not at the top, so --cli and the installer never load tkinter
    import tkinter as tk
    from docpipe import gui
    gui.windows_identity()  # before the first window exists, or the taskbar groups it under Python
    root = tk.Tk()
    out = args.out or os.path.join(paths.data_dir(APP_ID), "out")
    # Known limitation: the window only learns that --mock was given, not its DIR; its runs always
    # read the bundled snapshot (pipeline.MOCK).
    window = gui.PipelineWindow(root, db_path, out, force_mock=args.mock is not None,
                                installer_action=lambda remove: do_install(remove))
    root.after(300, window.start)  # a read-only pass straight away, so the window opens on results
    if args.smoke:
        def report():
            """Write the --smoke JSON report once the first run is over, then close the window.

            Run is disabled while a run is in flight, so this re-checks every 200 ms until it is
            enabled again. The verify script reads title, icon_set, source, version and counts.
            """
            if window.run_button.instate(["disabled"]):
                root.after(200, report)
                return
            kind, _ = window.source()
            data = {"app_id": APP_ID, "version": __version__, "title": root.title(), "icon_set": window.icon_set,
                    "source": kind, "db": db_path if kind == "db" else None,
                    "counts": {"orders": window.last["orders"], "documents": len(window.last["manifest"])} if window.last else {}}
            with open(args.smoke, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            root.destroy()
        root.after(800, report)  # after the 300 ms start, so the first check sees the run in flight
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ==== stamp v1 | author=kjFriday | hmac-sha256=f9470ae52425e88080bd3ac4d16d58161474bfed711fef414b0cc7484f6bf87c ====
