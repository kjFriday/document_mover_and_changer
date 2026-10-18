# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: docpipe/ingest/hashing.py
# About: Content hashing for ingest: duplicate detection and provenance.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Content hashing for ingest: duplicate detection and provenance."""

import hashlib

CHUNK = 1 << 20  # 1 MiB


def sha256_of(path, chunk=CHUNK):
    """Return the hex SHA-256 digest of the file at ``path``.

    The file is read in ``chunk``-byte blocks, so a large input never has to
    sit in memory whole.

    Errors are raised, never returned as a value: OSError (missing file,
    permission denied, a directory, ...) propagates to the caller. A dedupe
    index keyed on an error string would treat two unreadable files as
    duplicates of each other.
    """
    if chunk <= 0:
        raise ValueError("chunk must be a positive number of bytes")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()

# ==== stamp v1 | author=kjFriday | hmac-sha256=4e10f09afad63f653600ae891d5c7a029150ff22137ed862343fe185e4759df1 ====
