"""ACME Doc Pipeline: orders in, document files and a manifest out.

    python -m docpipe [--db PATH | --mock]     open the window
    python -m docpipe --cli [--out out] [--orders N] [--register] [--db PATH | --mock]
    python -m docpipe --install | --uninstall  install for this user / remove it again

It reads the shared ACME database by path (--db, ACME_DB, the saved setting, or
%LOCALAPPDATA%\\ACME Inc\\acme.db) and falls back to the bundled mock/ snapshot when there is none.
--register writes back a `documents` row for each order that had none and one `documents.generated`
event summarising the run (which the notification hub can pick up).
"""

import argparse
import json
import os
import sys

from docpipe import APP_ID, NAME, PUBLISHER, __version__, installer, paths, pipeline

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = ["docpipe_app.py", "docpipe", "icon", "mock", "README.md"]


def program():
    return installer.Program(APP_ID, NAME, __version__, PUBLISHER, installer.program_files(HERE, RUNTIME),
                             ["{dir}\\docpipe_app.py"])


def do_install(remove=False, root=None, desktop=False, purge=False):
    plan = installer.plan(program(), HERE, root=root, desktop=desktop)
    if remove:
        gone = installer.uninstall(plan, purge_dir=paths.data_dir(APP_ID) if purge else None)
        return f"{NAME} uninstalled." + ("" if gone else " (It was not installed.)") + " The database is kept."
    installer.install(plan)
    return f"{NAME} {__version__} installed in {plan['install_dir']}. Find it in the Start menu under ACME Inc."


def parse(argv):
    ap = argparse.ArgumentParser(prog="python -m docpipe", description=NAME)
    ap.add_argument("--db", help="shared database file")
    ap.add_argument("--mock", nargs="?", const=pipeline.MOCK, default=None, metavar="DIR",
                    help="use the mock snapshot (default: the bundled one)")
    ap.add_argument("--cli", action="store_true", help="run once in the console instead of opening the window")
    ap.add_argument("--out", help="output folder (window default: %%LOCALAPPDATA%%\\ACME Inc\\ACME.DocPipe\\out)")
    ap.add_argument("--orders", type=int, default=400, help="how many of the newest orders")
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
    print(message)
    if not quiet and sys.stdout is None:  # pythonw: no console
        from tkinter import messagebox
        messagebox.showinfo(NAME, message)


def cli(args, db_path):
    from docpipe.gui import describe_source
    kind, text = describe_source(db_path, args.mock is not None)
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
    args = parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        tell(f"{NAME} {__version__}", args.quiet)
        return 0
    if args.install or args.uninstall:
        try:
            tell(do_install(args.uninstall, args.root, args.desktop_shortcut, args.purge), args.quiet)
        except Exception as e:
            tell(f"{NAME}: {e}", args.quiet)
            return 1
        return 0
    db_path = paths.resolve_db(args.db, APP_ID)
    if args.cli:
        return cli(args, db_path)

    import tkinter as tk
    from docpipe import gui
    gui.windows_identity()
    root = tk.Tk()
    out = args.out or os.path.join(paths.data_dir(APP_ID), "out")
    window = gui.PipelineWindow(root, db_path, out, force_mock=args.mock is not None,
                                installer_action=lambda remove: do_install(remove))
    root.after(300, window.start)  # a read-only pass straight away, so the window opens on results
    if args.smoke:
        def report():
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
        root.after(800, report)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
