# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: docpipe/ingest/hashing.py
# About: Content hashing for ingest: duplicate detection and provenance.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Content hashing for ingest: duplicate detection and provenance.

A SHA-256 digest (FIPS 180-4) is a 256-bit fingerprint of a file's bytes,
written as 64 hex characters. Equal bytes always give the same digest, and
finding two different files with the same digest is not practical, so the
digest can stand in for the content: as a dedupe key, or as a record of
exactly what was produced.

docpipe.output.documents hashes every file it writes with ``sha256_of``,
and the manifest carries the result.
"""

import hashlib

# Default read size: big enough that the per-call overhead is negligible,
# small enough that memory use stays flat for files of any size.
CHUNK = 1 << 20  # 1 MiB


def sha256_of(path, chunk=CHUNK):
    """Return the hex SHA-256 digest of the file at ``path``.

    The file is read in ``chunk``-byte blocks, so a large input never has to
    sit in memory whole.

    Errors are raised, never returned as a value: OSError (missing file,
    permission denied, a directory, ...) propagates to the caller. A dedupe
    index keyed on an error string would treat two unreadable files as
    duplicates of each other. A ``chunk`` of zero or less raises ValueError:
    read(0) would return b"" at once, so every file would hash as empty, and
    a negative size would read the whole file in one piece.
    """
    if chunk <= 0:
        raise ValueError("chunk must be a positive number of bytes")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        # iter(callable, sentinel) calls read() until it returns b"" at end of file
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()

# ==== stamp v1 | author=kjFriday | hmac-sha256=b8ced54e85616fc4ae7bbe85d99bcd8437aff8f5fcb5aec775b2fe22b05fa6be ====
