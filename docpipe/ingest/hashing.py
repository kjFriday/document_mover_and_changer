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
