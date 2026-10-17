"""The Doc Pipeline window: pick the source, run the pipeline, browse the manifest and read a document."""

import ctypes
import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from docpipe import APP_ID, CREDIT, NAME, PUBLISHER, TITLE, __version__, paths, pipeline, store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(HERE, "icon", "app.ico")
ICON_PNG = os.path.join(HERE, "icon", "app-32.png")


def windows_identity():
    """Own taskbar button and icon (not Python's), and crisp pixels on scaled displays."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def set_icon(root):
    """The pixel icon on the window, its taskbar button and every dialog; -> True when Windows shows it."""
    try:
        root.iconbitmap(default=ICON)
        root.iconbitmap(ICON)
    except tk.TclError:
        return False
    if os.name != "nt":
        return True
    root.update_idletasks()
    return bool(ctypes.windll.user32.SendMessageW(int(root.wm_frame(), 16), 0x7F, 1, 0))  # WM_GETICON


def describe_source(db_path, force_mock=False):
    """("db", path) when the shared database is usable, else ("mock", why)."""
    if force_mock:
        return "mock", "mock snapshot (--mock)"
    if not os.path.isfile(db_path):
        return "mock", f"mock snapshot — no database at {db_path}"
    try:
        conn = store.connect(db_path, readonly=True)
        try:
            store.check_schema(conn)
        finally:
            conn.close()
    except Exception as e:  # missing tables, locked, not a database
        return "mock", f"mock snapshot — {db_path}: {e}"
    return "db", db_path


class PipelineWindow:
    def __init__(self, root, db_path, out, force_mock=False, installer_action=None):
        self.root, self.db_path, self.force_mock = root, db_path, force_mock
        self.installer_action = installer_action
        root.title(TITLE)
        root.geometry("900x600")
        self.icon_set = set_icon(root)
        self.small = tk.PhotoImage(file=ICON_PNG) if os.path.exists(ICON_PNG) else None
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style(root).configure("Treeview", rowheight=line + 6)
        self.results = queue.Queue()
        self.last = None

        menu = tk.Menu(root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Database…", command=self.choose_db)
        file_menu.add_command(label="Open output folder", command=self.open_out)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.destroy)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Install for this user", command=lambda: self.run_installer(False))
        help_menu.add_command(label="Uninstall…", command=lambda: self.run_installer(True))
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.about)
        menu.add_cascade(label="File", menu=file_menu)
        menu.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menu)

        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill="x")
        self.badge = tk.StringVar()
        ttk.Label(top, text="Source:").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.badge).grid(row=0, column=1, columnspan=5, sticky="w", padx=6)
        ttk.Label(top, text="Output:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.out = tk.StringVar(value=out)
        ttk.Entry(top, textvariable=self.out).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(top, text="…", width=3, command=self.choose_out).grid(row=1, column=2, pady=(6, 0))
        ttk.Label(top, text="Orders:").grid(row=1, column=3, sticky="e", padx=(12, 4), pady=(6, 0))
        self.orders = tk.IntVar(value=400)
        ttk.Spinbox(top, from_=1, to=15000, increment=100, width=7, textvariable=self.orders).grid(row=1, column=4, pady=(6, 0))
        self.register = tk.BooleanVar(value=False)
        self.register_box = ttk.Checkbutton(top, text="Register in database", variable=self.register)
        self.register_box.grid(row=1, column=5, padx=12, pady=(6, 0))
        self.run_button = ttk.Button(top, text="Run", command=self.start)
        self.run_button.grid(row=1, column=6, pady=(6, 0))
        top.columnconfigure(1, weight=1)

        panes = ttk.PanedWindow(root, orient="horizontal")
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
        self.preview = tk.Text(panes, wrap="none", font=("Consolas", 10), state="disabled", width=66)
        panes.add(left, weight=1)
        panes.add(self.preview, weight=1)

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(root, textvariable=self.status, anchor="w", padding=(10, 2)).pack(side="bottom", fill="x")
        self.refresh_source()

    # --- state ---

    def source(self):
        return describe_source(self.db_path, self.force_mock)

    def refresh_source(self):
        kind, text = self.source()
        self.badge.set(("● shared database  " if kind == "db" else "○ ") + text)
        self.register_box.state(["!disabled"] if kind == "db" else ["disabled"])
        if kind != "db":
            self.register.set(False)

    def choose_db(self):
        path = filedialog.askopenfilename(parent=self.root, title="Shared database",
                                          initialdir=os.path.dirname(self.db_path),
                                          filetypes=[("SQLite database", "*.db"), ("All files", "*.*")])
        if path:
            self.db_path, self.force_mock = os.path.abspath(path), False
            paths.save_settings({"db": self.db_path}, APP_ID)
            self.refresh_source()

    def choose_out(self):
        path = filedialog.askdirectory(parent=self.root, initialdir=self.out.get(), title="Output folder")
        if path:
            self.out.set(os.path.abspath(path))

    def open_out(self):
        os.makedirs(self.out.get(), exist_ok=True)
        if os.name == "nt":
            os.startfile(self.out.get())
        else:
            subprocess.Popen(["xdg-open", self.out.get()])

    # --- running ---

    def start(self):
        kind, _ = self.source()
        args = dict(out=self.out.get(), db_path=self.db_path if kind == "db" else None,
                    orders=max(1, int(self.orders.get() or 400)), register=self.register.get())
        self.run_button.state(["disabled"])
        self.status.set("Running…")
        threading.Thread(target=self._work, args=(args,), daemon=True).start()
        self.root.after(100, self._poll)

    def _work(self, args):
        try:
            self.results.put(("ok", pipeline.run(**args)))
        except Exception as e:
            self.results.put(("error", e))

    def _poll(self):
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
        self.last = result
        self.tree.delete(*self.tree.get_children())
        for i, m in enumerate(result["manifest"]):
            self.tree.insert("", "end", iid=str(i), values=(m["kind"], m["order_id"], m["path"], m["sha256"][:16]))
        kinds = ", ".join(f"{n} {k}" for k, n in sorted(result["kinds"].items()))
        reg = f"; registered {result['registered']} rows, event {result['event']}" if result["event"] else ""
        self.status.set(f"{result['orders']} orders from {result['source']} → {len(result['manifest'])} documents "
                        f"({kinds}); manifest {result['sha256'][:16]}{reg}")

    def show_document(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.last:
            return
        m = self.last["manifest"][int(sel[0])]
        try:
            with open(os.path.join(self.last["out"], *m["path"].split("/")), encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            text = str(e)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    # --- help ---

    def run_installer(self, remove):
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
        win = tk.Toplevel(self.root)
        win.title(f"About {NAME}")
        win.resizable(False, False)
        if self.small:
            win.big = self.small.zoom(3)
            ttk.Label(win, image=win.big).pack(padx=24, pady=(20, 8))
        kind, text = self.source()
        ttk.Label(win, text=f"{NAME} {__version__}\n{PUBLISHER}\n\nSource: {text}\n\n{CREDIT}\n"
                            "Code: AGPL-3.0. All data is fictional.", justify="center", wraplength=420).pack(padx=24, pady=(0, 12))
        ttk.Button(win, text="OK", command=win.destroy).pack(pady=(0, 16))
        win.transient(self.root)
