"""docpipe: a small, stdlib-only document pipeline.

Subpackages follow the pipeline stages:

    docpipe.ingest   Stage 1, ingestion (content hashing for dedupe/provenance)
    docpipe.enrich   Stage 4, normalisation and enrichment
    docpipe.output   Stage 5, document files and their manifest

docpipe.store reads and writes the shared database (by path), docpipe.source the bundled mock snapshot,
docpipe.pipeline runs it all, and docpipe.gui is the window that ``python -m docpipe`` opens.
"""

__version__ = "0.2.0"

APP_ID = "ACME.DocPipe"
NAME = "ACME Doc Pipeline"
TITLE = f"ACME Inc. — {NAME} {__version__}"
PUBLISHER = "ACME Inc. (fictional)"
CREDIT = ("Icon: Silk by Mark James (famfamfam.com/lab/icons/silk), CC BY 2.5 "
          "(creativecommons.org/licenses/by/2.5), enlarged by nearest-neighbour.")
