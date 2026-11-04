# docpipe

A small document-processing pipeline for Generic Company Inc. (a fictional company),
written in standard-library Python. It follows the five-stage design in
[idea.md](idea.md). Only the stages listed below have code so far.

| idea.md stage | Module | What it does |
|---|---|---|
| 1. Ingestion & Routing | `docpipe.ingest.hashing` | `sha256_of(path, chunk=1 << 20)`: a chunked SHA-256 of each incoming file, for dedupe and provenance. It raises `OSError` on unreadable files instead of returning a value, so two failures never look like the same document. |
| 2. Parsing & Extraction | - | Not started. |
| 3. Chunking & Structuring | - | Not started. |
| 4. Validation, Normalization & Enrichment | `docpipe.enrich.normalize` | `fold(value, limit=240)`: folds titles, authors and table cells to one line of printable ASCII. It is lossy, so it is never used on body text. |
| 4. Validation, Normalization & Enrichment | `docpipe.enrich.shape` | Text-shape signatures (character classes, line lengths, distinct tokens) and a nearest-neighbour lookup against a catalog of labelled exemplars. It returns document-type hints, which can also feed Stage 1 routing. Letters without case (CJK, Arabic, ...) get their own bucket. |
| 5. Storage & Querying | `docpipe.output.documents` | Renders each order's documents (invoice, receipt, packing slip) as plain text at the path its `documents` row names, and returns a manifest with each file's SHA-256. |

## How it works

1. `docpipe_app.py` (shortcut, Apps & features, setup) or `python -m docpipe` calls `docpipe/__main__.py` `main()`,
   which parses the flags. `--version`, `--install` and `--uninstall` stop here.
2. `paths.resolve_db()` picks the database path: `--db`, `GENERIC_COMPANY_DB`, the saved setting, then the default.
3. `pipeline.describe_source()` opens that file read-only and runs `store.check_schema()`. If the file is missing
   or lacks a table or column in `store.NEEDS`, or `--mock` was given, the run uses the `mock/` snapshot.
4. `--cli` calls `pipeline.run()` once in `cli()` and prints a summary. Otherwise `gui.PipelineWindow` opens and
   starts a read-only run on a worker thread; the thread hands its result back through a queue.
5. `pipeline.run()` reads the rows with `store.from_db()` (newest `store.ORDERS` = 400 orders) or `source.from_mock()`.
6. `output.documents.build()` folds names with `enrich.normalize.fold()`, renders each document as 64-column
   ASCII text, writes it at its stored path (or `default_path()` for an order with no row) and hashes it with
   `ingest.hashing.sha256_of()`.
7. With **Register** / `--register`, `store.register()` adds the missing `documents` rows and one
   `documents.generated` event (status `sent`) in one transaction, every string cleaned by `textsafe.clean()`.
8. `pipeline.run()` writes `manifest.jsonl` (JSON Lines, sorted keys); `pipeline.digest()` is the SHA-256 of
   those exact bytes. The window lists the manifest and previews the selected file.

Where state lives:

| What | Where | Written by |
|---|---|---|
| Shared database | `generic_company.db` in `%LOCALAPPDATA%\Generic Company Inc\` (or `--db`, `GENERIC_COMPANY_DB`) | the CRUD hub; this program only reads it, and inserts with `--register` |
| Settings | `settings.json` in `%LOCALAPPDATA%\Generic Company Inc\GenericCompany.DocPipe\` (just the database path) | **File → Database…** via `docpipe/paths.py` |
| Output | `--out` folder; the window's default is `out\` in the same data folder; `manifest.jsonl` at its top | `docpipe/output/documents.py`, `docpipe/pipeline.py` |
| Mock snapshot | `mock/*.json`, `mock/schema.sql` | the CRUD hub's `export_mock.py` (read-only here) |
| Install | the install folder with its `install.json` marker; Start-menu shortcut; `HKCU\...\Uninstall\GenericCompany.DocPipe` (a `registry.json` stand-in under `--root`) | `docpipe/installer.py` |

## Code map

In reading order:

| File | What it holds |
|---|---|
| `docpipe_app.py` | Launcher for shortcuts and setups; calls `docpipe.__main__.main()`. Must stay beside `docpipe/`. |
| `docpipe/__main__.py` | Entry point: flags, `cli()`, `do_install()`, `--smoke`, opening the window. |
| `docpipe/__init__.py` | Identity constants: `__version__`, `APP_ID`, `NAME`, `TITLE`, `PUBLISHER`, `CREDIT`. |
| `docpipe/pipeline.py` | One run for window and console: `describe_source()`, `run()`, `manifest_lines()`, `digest()`. |
| `docpipe/store.py` | The shared database: `connect()`, `check_schema()`, `from_db()`, `register()`; `NEEDS` and `ORDERS`. |
| `docpipe/source.py` | The bundled mock snapshot: `from_mock()`. |
| `docpipe/output/documents.py` | Stage 5: `render()`, `build()`, `default_path()`, `money()`. |
| `docpipe/enrich/normalize.py` | Stage 4: `fold()` for names and other short fields. |
| `docpipe/ingest/hashing.py` | Stage 1: `sha256_of()`. |
| `docpipe/enrich/shape.py` | Stage 4: text-shape signatures and nearest-exemplar hints, with its own command line; the app does not call it yet. |
| `docpipe/gui.py` | The Tk window: worker thread and queue, manifest list, preview, menus, taskbar identity and icon. |
| `docpipe/paths.py` | Where the database, data folder and `settings.json` are (copy of the CRUD hub's). |
| `docpipe/textsafe.py` | Strips control and bidi characters before anything is written to the database (copy of the hub's). |
| `docpipe/installer.py` | Per-user install and uninstall, Wizard Maker hand-off (copy of the hub's). |
| `docpipe/ingest/__init__.py`, `enrich/__init__.py`, `output/__init__.py` | Stage packages; docstrings only. |
| `tests/dbfixture.py` | Builds a real SQLite file from `mock/schema.sql` and the snapshot. |
| `tests/test_app.py` | Version, title, icon files and hashes, install contents against `setup.json`. |
| `tests/test_store.py`, `tests/test_documents.py` | Database reads and registering, rendering, `pipeline.run()` and `--cli`. |
| `tests/test_hashing.py`, `tests/test_normalize.py`, `tests/test_shape.py` | The stage modules. |
| `tests/test_paths.py`, `tests/test_textsafe.py`, `tests/test_installer.py` | The copied hub modules. |

Also here: `idea.md` (the five-stage design), `setup.json` (the Wizard Maker setup), `mock/` and `icon/`
(both generated; see their READMEs) and `PROVENANCE.md`.

## Run

```
python -m docpipe
```

Opens the **Generic Company Doc Pipeline** window. It reads the shared Generic Company database by path: `--db PATH`, the
`GENERIC_COMPANY_DB` environment variable, the file chosen with **File → Database…**, or
`%LOCALAPPDATA%\Generic Company Inc\generic_company.db`. With no database it runs on the bundled `mock/` snapshot (400 orders
and their documents) and says so. **Run** renders the newest orders' documents; **Register in database**
also writes a `documents` row for each order that had none and one `documents.generated` event with the
run's manifest hash. The manifest lists every file with its SHA-256; select one to read it.

The same run in a console:

```
python -m docpipe --cli --register
```

Files and `manifest.jsonl` go to `--out` (the window's default is `%LOCALAPPDATA%\Generic Company Inc\GenericCompany.DocPipe\out`).
The same input always gives the same files and hashes. A stored path that would climb out of the output
folder is refused.

## Install

```
python -m docpipe --install
```

Installs for the current user: copies the program to `%LOCALAPPDATA%\Programs\Generic Company Inc\Generic Company Doc Pipeline\`,
adds it to the Start menu under **Generic Company Inc** with its pixel icon (`--desktop-shortcut` for the desktop too),
and lists it in **Apps & features**. `python -m docpipe --uninstall` (or Apps & features) removes it; the
database is never deleted. The shortcut uses the `pythonw.exe` that installed it, so reinstall after
upgrading Python. `--root DIR` sandboxes all of it in DIR.

The window's **Help** menu offers the same install and uninstall.

Generic Company Wizard Maker makes the setup from this folder,
`..\wizard_maker\wizard-maker.exe build setup.json`, as `dist\Generic Company Doc Pipeline-0.2.0-setup.exe`.

The icon is Silk "folder_go" by Mark James, CC BY 2.5, enlarged by nearest-neighbour (`icon/README.md`).
## Shape hints

```
python -m docpipe.enrich.shape FILE [--catalog catalog.json] [--weights weights.json] [-n 3]
```

The command prints the file's signature as JSON. Given a catalog, it also
prints the catalog's age and the closest exemplars. Without `--weights`, the
built-in `FALLBACK_WEIGHTS` are used, and a weights file only needs the axes
it changes. The catalog and weights formats are documented at the top of
`docpipe/enrich/shape.py`.

## Developing

Standard-library Python 3.10 or later (`setup.json` requires 3.10); nothing to install. From this folder:

| Task | Command |
|---|---|
| Run the window | `python -m docpipe` (add `--mock` to ignore the database) |
| Run once in the console | `python -m docpipe --cli --mock --out out` |
| Test (93 tests) | `python -m unittest discover -s tests` |
| Smoke check | `python -m docpipe --mock --out out --smoke smoke.json`: opens the window, runs once, writes a JSON report (title, icon, source, counts) and closes. The portfolio's `tools/verify.ps1` runs this against a sandbox database. |
| Version | `python -m docpipe --version` |
| Build the setup | `..\wizard_maker\wizard-maker.exe build setup.json` |

`out/`, `dist/` and `__pycache__/` are ignored by git.

Where to add things:

- A new document kind: add its heading to `TITLES` in `docpipe/output/documents.py` (and any kind-specific
  lines in `render()`); test it in `tests/test_documents.py`.
- A new run option: add the flag in `parse()` and use it in `cli()` in `docpipe/__main__.py`, pass it on to
  `pipeline.run()`, and add the matching control in `PipelineWindow._build_controls()` in `docpipe/gui.py`.
- A new stage (for example parsing): a new subpackage beside `ingest/`, `enrich/` and `output/`, called
  from `pipeline.run()`, with its row in the stage table above.

Twins (kept the same as another program's copy; change both):

| Here | Twin in `company/crud_hub/` |
|---|---|
| `docpipe/textsafe.py`, `tests/test_textsafe.py` | `textsafe.py`, `tests/test_textsafe.py` |
| `docpipe/paths.py`, `tests/test_paths.py` | `paths.py`, `tests/test_paths.py` (only `APP_ID` differs) |
| `docpipe/installer.py`, `tests/test_installer.py` | `installer.py`, `tests/test_installer.py` (only the import path differs) |
| `default_path()` in `docpipe/output/documents.py` | the document path layout in `seed.py` |
| `store.NEEDS` | the schema in `db.py`, which this program only reads |

Traps the code warns about:

- The version is written twice: `__version__` in `docpipe/__init__.py` and `"version"` in `setup.json`. The
  Dev Console bumps both, and `tools/verify.ps1` expects the exact value (0.2.0) in the smoke report.
- `APP_ID` must match `paths.APP_ID` and the `id`, `appUserModelId` and `purge` path in `setup.json`.
- `RUNTIME` in `docpipe/__main__.py` must list the same entries as `"files"` in `setup.json` (`tests/test_app.py` checks).
- `store.ORDERS` is 400 because the snapshot holds 400 orders and `tools/verify.ps1` expects that count.
- `WIDTH = 64` in `docpipe/output/documents.py`: the column widths in `render()` add up to it by hand.
- `mock/` is generated by the CRUD hub's `export_mock.py` and `icon/` by `tools/pixel_icons.py`; do not edit
  either by hand.
- tkinter is imported inside `main()` on purpose, so `--cli` and the installer never load it. In `gui.py` only
  the main-loop thread may touch widgets; the worker posts to the queue.
- Each source file ends in a signed stamp line; `tools/stamp.py --check` in the portfolio reports files changed since.

Where each adapted function came from is listed in [PROVENANCE.md](PROVENANCE.md).

## License

AGPL-3.0, as the rest of the portfolio; see [LICENSE](LICENSE).
