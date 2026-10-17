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
| 5. Storage & Querying | - | Not started. |

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
