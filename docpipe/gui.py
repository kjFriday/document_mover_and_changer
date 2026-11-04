# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/gui.py
# About: The Doc Pipeline window: run the pipeline, browse the manifest and read each document.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""The Doc Pipeline window: run the pipeline, browse the manifest and read each document.

The user picks the source and output, runs the pipeline and reads the documents it wrote.
docpipe.__main__ opens it when no --cli or install flag is given. The window shows:

    a source badge     the shared database, or the mock snapshot and why
    a control row      output folder, number of orders, "Register in database", Run
    the manifest       one row per document written: kind, order, path, hash prefix
    a preview          the text of the selected document
    a status bar       the last run's counts and manifest hash, or its error

How a run flows:

1. start() reads the controls and starts pipeline.run() on a daemon thread, with Run disabled.
2. The thread posts ("ok", summary) or ("error", exception) to a queue.Queue.
3. _poll() checks the queue every 100 ms with root.after(); Tk widgets may only be touched from
   the thread that runs the main loop, so the worker never touches them itself.
4. show() fills the manifest list and the status bar; selecting a row calls show_document().

File > Database... saves the chosen path in this program's settings.json (docpipe.paths). Help
offers install and uninstall through the installer_action that __main__ passes in, and About.
windows_identity() and set_icon() handle the Windows taskbar identity and icon.
"""

import ctypes
import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from docpipe import APP_ID, CREDIT, NAME, PUBLISHER, TITLE, __version__, paths, pipeline
from docpipe.pipeline import describe_source

# The project folder (installed or not), which holds icon/: the multi-size .ico for the window and
# taskbar, and the 32-pixel PNG the About box enlarges.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON =os.path.join(HERE, "icon", "app.ico")
ICON_PNG = os.path.join(HERE, "icon", "app-32.png")
MAX_ORDERS = 15000  # top of the Orders spinbox: as many orders as the CRUD hub's seed makes


def windows_identity():
    """Own taskbar button and icon (not Python's), and crisp pixels on scaled displays.

    Call it once, before the first window is created. Does nothing off Windows, and ignores a
    Windows too old to have either call.
    """
    if os.name != "nt":
        return
    try:
        # The AppUserModelID is the key Windows groups taskbar buttons by. Without one, every
        # pythonw.exe program shares Python's button and icon. It matches the Start-menu shortcut's
        # id (setup.json appUserModelId), so a pinned shortcut and the running window are one button.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        # 1 = PROCESS_SYSTEM_DPI_AWARE: Tk draws at the real pixel size instead of being bitmap-stretched
        # by Windows on a display scaled above 100%, which blurs text and the pixel icon
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def set_icon(root):
    """The pixel icon on the window, its taskbar button and every dialog; -> True when Windows shows it.

    Returns False when Tk cannot load the .ico, and True off Windows once it loaded. The --smoke
    report carries the result as icon_set.
    """
    try:
        root.iconbitmap(default=ICON)  # default=: the class icon, inherited by every later dialog
        root.iconbitmap(ICON)  # this window's own icon (Tk sends WM_SETICON), which the taskbar shows
    except tk.TclError:
        return False
    if os.name != "nt":
        return True
    root.update_idletasks()  # map the window first, so its frame handle exists
    # wm_frame() is the outer frame's HWND as a hex string. 0x7F is WM_GETICON and wParam 1 is
    # ICON_BIG: the window answers with its big icon's handle, or 0 when it has none.
    return bool(ctypes.windll.user32.SendMessageW(int(root.wm_frame(), 16), 0x7F, 1, 0))  # WM_GETICON


class PipelineWindow:
    """The main window. __main__ and its --smoke report use run_button, icon_set, last, start() and source().

    State: db_path is the database path the window offers (it may not exist), force_mock keeps it on
    the snapshot, and last holds the most recent run's summary dict (None before the first run).
    All methods run on the Tk thread except _work(), which runs on a worker thread.
    """

    def __init__(self, root, db_path, out, force_mock=False, installer_action=None):
        """Build the whole window inside root.

        out is the initial output folder. force_mock is True for --mock. installer_action(remove)
        installs (remove=False) or uninstalls (remove=True) and returns the message to show; without
        it the Help menu's install items do nothing. The first run is started by the caller.
        """
        self.root, self.db_path, self.force_mock = root, db_path, force_mock
        self.installer_action = installer_action
        root.title(TITLE)
        root.geometry("900x600")
        self.icon_set = set_icon(root)
        self.small = tk.PhotoImage(file=ICON_PNG) if os.path.exists(ICON_PNG) else None
        # Treeview rows have a fixed pixel height that does not follow display scaling; sizing them
        # from the font's line height keeps the text from being clipped at 125% or 150%
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style(root).configure("Treeview", rowheight=line + 6)
        self.results = queue.Queue()
        self.last = None
        self._build_menu()
        self._build_controls(out)
        self._build_panes()
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(root, textvariable=self.status, anchor="w", padding=(10, 2)).pack(side="bottom", fill="x")
        self.refresh_source()

    def _build_menu(self):
        """File (database, output folder, exit) and Help (install, uninstall, about)."""
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Database…", command=self.choose_db)
        file_menu.add_command(label="Open output folder", command=self.open_out)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Install for this user", command=lambda: self.run_installer(False))
        help_menu.add_command(label="Uninstall…", command=lambda: self.run_installer(True))
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.about)
        menu.add_cascade(label="File", menu=file_menu)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def _build_controls(self, out):
        """The source badge, then one row: output folder, order count, Register box and Run."""
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        self.badge = tk.StringVar()
        ttk.Label(top, text="Source:").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.badge).grid(row=0, column=1, columnspan=5, sticky="w", padx=6)
        ttk.Label(top, text="Output:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.out = tk.StringVar(value=out)
        ttk.Entry(top, textvariable=self.out).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(top, text="…", width=3, command=self.choose_out).grid(row=1, column=2, pady=(6, 0))
        ttk.Label(top, text="Orders:").grid(row=1, column=3, sticky="e", padx=(12, 4), pady=(6, 0))
        self.orders = tk.IntVar(value=pipeline.ORDERS)
        # the Spinbox and the IntVar share one Tcl variable, so typed text reaches self.orders unchecked
        ttk.Spinbox(top, from_=1, to=MAX_ORDERS, increment=100, width=7, textvariable=self.orders).grid(row=1, column=4, pady=(6, 0))
        self.register = tk.BooleanVar(value=False)
        self.register_box = ttk.Checkbutton(top, text="Register in database", variable=self.register)
        self.register_box.grid(row=1, column=5, padx=12, pady=(6, 0))
        self.run_button = ttk.Button(top, text="Run", command=self.start)
        self.run_button.grid(row=1, column=6, pady=(6, 0))
        top.columnconfigure(1, weight=1)

    def _build_panes(self):
        """The manifest list and, beside it, the preview of the selected document."""
        panes = ttk.PanedWindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        left = ttk.Frame(panes)
        self.tree = ttk.Treeview(left, columns=("kind", "order", "path", "sha"), show="headings")
        for col, label, width in (("kind", "Kind", 90), ("order", "Order", 60), ("path", "Path", 230), ("sha", "SHA-256", 130)):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center" if col == "order" else "w")
        bar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.show_document)
        # a monospaced font and no wrapping, since documents are laid out in 64 fixed columns; width 66
        # leaves a little margin. Disabled so the reader cannot edit the text by accident.
        self.preview = tk.Text(panes, wrap="none", font=("Consolas", 10), state="disabled", width=66)
        panes.add(left, weight=1)
        panes.add(self.preview, weight=1)

    # --- state ---

    def source(self):
        """Where a run would read from now: ("db", path) or ("mock", why) from pipeline.describe_source.

        It opens the database to check its schema, on the Tk thread, so a locked database can hold the
        window for up to the 5-second busy timeout.
        """
        return describe_source(self.db_path, self.force_mock)

    def refresh_source(self):
        """Update the source badge, and allow "Register in database" only when the source is the database."""
        kind, text = self.source()
        self.badge.set(("● shared database  " if kind == "db" else "○ ") + text)
        self.register_box.state(["!disabled"] if kind == "db" else ["disabled"])
        if kind != "db":
            self.register.set(False)

    def choose_db(self):
        """Ask for a database file; use it, leave mock mode and save it as this program's "db" setting.

        Cancelling the dialog changes nothing. The saved path is what paths.resolve_db() finds next time
        when neither --db nor GENERIC_COMPANY_DB is set.
        """
        path = filedialog.askopenfilename(parent=self.root, title="Shared database",
                                          initialdir=os.path.dirname(self.db_path),
                                          filetypes=[("SQLite database", "*.db"), ("All files", "*.*")])
        if path:
            self.db_path, self.force_mock = os.path.abspath(path), False
            paths.save_settings({"db": self.db_path}, APP_ID)
            self.refresh_source()

    def choose_out(self):
        """Ask for an output folder and put it in the Output box; it is not saved between sessions."""
        path = filedialog.askdirectory(parent=self.root, initialdir=self.out.get(), title="Output folder")
        if path:
            self.out.set(os.path.abspath(path))

    def open_out(self):
        """Open the output folder in Explorer (xdg-open elsewhere), creating it first if needed."""
        os.makedirs(self.out.get(), exist_ok=True)
        if os.name == "nt":
            os.startfile(self.out.get())
        else:
            subprocess.Popen(["xdg-open", self.out.get()])

    # --- running ---

    def start(self):
        """Start one pipeline run in the background with the current controls; Run stays disabled until it ends.

        Steps:
        1. Re-check the source, so a database that vanished since the last check falls back to mock.
        2. Collect the arguments for pipeline.run() (an order count of 0 means the default).
        3. Disable Run, start _work() on a daemon thread (it dies with the window), and begin polling.

        Known limitation: IntVar.get() raises TclError when the Orders box holds empty or non-numeric
        text; Tk reports that as a callback error and no run starts.
        """
        kind, _ = self.source()
        args = dict(out=self.out.get(), db_path=self.db_path if kind == "db" else None,
                    orders=max(1, int(self.orders.get() or pipeline.ORDERS)), register=self.register.get())
        self.run_button.state(["disabled"])
        self.status.set("Running…")
        threading.Thread(target=self._work, args=(args,), daemon=True).start()
        self.root.after(100, self._poll)

    def _work(self, args):
        """Worker thread: run the pipeline with args and post ("ok", summary) or ("error", exception).

        It touches no widget; every exception goes to the queue so the window always hears back.
        """
        try:
            self.results.put(("ok", pipeline.run(**args)))
        except Exception as e:
            self.results.put(("error", e))

    def _poll(self):
        """Tk thread: take the run's result if it is there, else check again in 100 ms.

        On a result it re-enables Run, then shows the summary, or the error in the status bar and a box.
        """
        try:
            kind, value = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return
        self.run_button.state(["!disabled"])
        if kind == "error":
            self.status.set(f"Failed: {value}")
            messagebox.showerror("Run failed", str(value), parent=self.root)
            return
        self.show(value)

    def show(self, result):
        """Show a pipeline.run() summary: keep it as last, list its manifest and write the status line.

        Each row's iid is its index in result["manifest"], which show_document() uses to find the entry.
        """
        self.last = result
        self.tree.delete(*self.tree.get_children())
        for i, m in enumerate(result["manifest"]):
            self.tree.insert("", "end", iid=str(i), values=(m["kind"], m["order_id"], m["path"], m["sha256"][:16]))
        kinds = ", ".join(f"{n} {k}" for k, n in sorted(result["kinds"].items()))
        reg = f"; registered {result['registered']} rows, event {result['event']}" if result["event"] else ""
        self.status.set(f"{result['orders']} orders from {result['source']} → {len(result['manifest'])} documents "
                        f"({kinds}); manifest {result['sha256'][:16]}{reg}")

    def show_document(self, _event=None):
        """Show the selected manifest entry's file in the preview, or the error when it cannot be read.

        Manifest paths always use "/", so the path is split and rejoined with this system's separator.
        """
        sel = self.tree.selection()
        if not sel or not self.last:
            return
        m = self.last["manifest"][int(sel[0])]
        try:
            with open(os.path.join(self.last["out"], *m["path"].split("/")), encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            text = str(e)
        self.preview.configure(state="normal")  # a disabled Text ignores insert and delete too
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    # --- help ---

    def run_installer(self, remove):
        """Help menu: install for this user (remove=False) or, after a confirmation, uninstall.

        The outcome is shown in a message box. After an uninstall the window closes, since the program
        it belongs to is gone.
        """
        if not self.installer_action:
            return
        if remove and not messagebox.askyesno("Uninstall", f"Uninstall {NAME}?\nThe database is kept.", parent=self.root):
            return
        try:
            message = self.installer_action(remove)
        except Exception as e:
            messagebox.showerror("Installer", str(e), parent=self.root)
            return
        messagebox.showinfo("Installer", message, parent=self.root)
        if remove:
            self.root.destroy()

    def about(self):
        """Open the About box: the icon at 3x, name, version, publisher, current source and the icon credit."""
        win = tk.Toplevel(self.root)
        win.title(f"About {NAME}")
        win.resizable(False, False)
        if self.small:
            # zoom(3) repeats each pixel 3 times, so the pixel art stays sharp at 96x96. It is kept on
            # win: Tk drops an image whose last Python reference is gone and the label goes blank.
            win.big = self.small.zoom(3)
            ttk.Label(win, image=win.big).pack(padx=24, pady=(20, 8))
        kind, text = self.source()
        ttk.Label(win, text=f"{NAME} {__version__}\n{PUBLISHER}\n\nSource: {text}\n\n{CREDIT}\n"
                            "Code: AGPL-3.0. All data is fictional.", justify="center", wraplength=420).pack(padx=24, pady=(0, 12))
        ttk.Button(win, text="OK", command=win.destroy).pack(pady=(0, 16))
        win.transient(self.root)

# ==== stamp v1 | author=kjFriday | hmac-sha256=599dc7effabbe84e2ea0db98c002d04b275723629e19d7bd5bcf8dd6059935ec ====
