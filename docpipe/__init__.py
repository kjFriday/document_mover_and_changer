"""docpipe: a small, stdlib-only document pipeline.

Subpackages follow the pipeline stages:

    docpipe.ingest   Stage 1, ingestion (content hashing for dedupe/provenance)
    docpipe.enrich   Stage 4, normalisation and enrichment
    docpipe.output   Stage 5, document files and their manifest

docpipe.source reads the rows (mock snapshot or CRUD hub); ``python -m docpipe`` runs it all.
"""
