# ==== Generic Company Inc. portfolio ====================================
# Project: doc_pipeline | File: tests/test_hashing.py
# About: Tests for docpipe.ingest.hashing.sha256_of.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's tools/stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

"""Tests for docpipe.ingest.hashing.sha256_of.

They pin the digest against published SHA-256 test values, show the chunk size cannot change it, and
check that unreadable paths and a bad chunk size raise instead of returning something hash-shaped.
"""

import hashlib
import os
import tempfile
import unittest

from docpipe.ingest.hashing import sha256_of


class Sha256OfTest(unittest.TestCase):
    """sha256_of on files in a fresh temporary folder per test."""

    def setUp(self):
        """Make the temporary folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        """Delete the temporary folder."""
        self._tmp.cleanup()

    def _write(self, name, data):
        """Write bytes data to a file called name in the folder; -> its path."""
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_known_vectors(self):
        """The standard SHA-256 digests of b"abc" (the FIPS 180 example) and of empty input."""
        self.assertEqual(
            sha256_of(self._write("abc.bin", b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(
            sha256_of(self._write("empty.bin", b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_chunk_size_does_not_change_the_digest(self):
        """Odd and even chunk sizes, from 1 byte to more than the file, give hashlib's digest of the whole.

        The data is 10,500 bytes: 256-byte chunks end on a short 4-byte block, and 1 MiB takes it in one read.
        """
        data = bytes(range(256)) * 41 + b"tail"
        path = self._write("data.bin", data)
        want = hashlib.sha256(data).hexdigest()
        for chunk in (1, 7, 256, 1 << 20):
            with self.subTest(chunk=chunk):
                self.assertEqual(sha256_of(path, chunk=chunk), want)

    def test_unreadable_files_raise_instead_of_colliding(self):
        """Missing files raise OSError rather than returning an error value as their digest."""
        # Two different unreadable paths must not produce equal "digests".
        for path in (os.path.join(self.dir, "missing-a.pdf"),
                     os.path.join(self.dir, "missing-b.pdf")):
            with self.subTest(path=path):
                with self.assertRaises(OSError):
                    sha256_of(path)

    def test_directory_raises(self):
        """A directory is not hashed: opening it raises OSError (IsADirectoryError or PermissionError)."""
        with self.assertRaises(OSError):
            sha256_of(self.dir)

    def test_non_positive_chunk_is_rejected(self):
        """Chunk sizes 0 and -1 raise ValueError instead of hashing the file wrongly."""
        path = self._write("x.bin", b"x")
        for chunk in (0, -1):
            with self.subTest(chunk=chunk):
                with self.assertRaises(ValueError):
                    sha256_of(path, chunk=chunk)


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=420f8f3319e59d38fc83fc79921e0ca0d6f349d6a63e574ccb6fa13609e19635 ====
