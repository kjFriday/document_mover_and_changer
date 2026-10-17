# docpipe

A small document-processing pipeline for ACME Inc. (a fictional company),
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

## Run

```
python -m docpipe
```

Opens the **ACME Doc Pipeline** window. It reads the shared ACME database by path: `--db PATH`, the
`ACME_DB` environment variable, the file chosen with **File → Database…**, or
`%LOCALAPPDATA%\ACME Inc\acme.db`. With no database it runs on the bundled `mock/` snapshot (400 orders
and their documents) and says so. **Run** renders the newest orders' documents; **Register in database**
also writes a `documents` row for each order that had none and one `documents.generated` event with the
run's manifest hash. The manifest lists every file with its SHA-256; select one to read it.

The same run in a console:

```
python -m docpipe --cli --register
```

Files and `manifest.jsonl` go to `--out` (the window's default is `%LOCALAPPDATA%\ACME Inc\ACME.DocPipe\out`).
The same input always gives the same files and hashes. A stored path that would climb out of the output
folder is refused.

## Install

```
python -m docpipe --install
```

Installs for the current user: copies the program to `%LOCALAPPDATA%\Programs\ACME Inc\ACME Doc Pipeline\`,
adds it to the Start menu under **ACME Inc** with its pixel icon (`--desktop-shortcut` for the desktop too),
and lists it in **Apps & features**. `python -m docpipe --uninstall` (or Apps & features) removes it; the
database is never deleted. The shortcut uses the `pythonw.exe` that installed it, so reinstall after
upgrading Python. `--root DIR` sandboxes all of it in DIR.

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

## Tests

From this folder:

```
python -m unittest discover -s tests
```

Where each adapted function came from is listed in [PROVENANCE.md](PROVENANCE.md).
