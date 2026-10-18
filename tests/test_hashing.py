# ==== ACME Inc. portfolio ===============================================
# Project: document_mover_and_changer | File: tests/test_hashing.py
# About: Tests for hashing.py.
# Copyright (c) 2026 kjFriday | SPDX-License-Identifier: AGPL-3.0-only
# You may change this file under the AGPL-3.0. The stamp at the end marks
# the version kjFriday wrote. Verify with the portfolio's stamp.py --check.
# Reused code, if any, is mapped in PROVENANCE.md.
# ========================================================================

import hashlib
import os
import tempfile
import unittest

from docpipe.ingest.hashing import sha256_of


class Sha256OfTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_known_vectors(self):
        self.assertEqual(
            sha256_of(self._write("abc.bin", b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(
            sha256_of(self._write("empty.bin", b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_chunk_size_does_not_change_the_digest(self):
        data = bytes(range(256)) * 41 + b"tail"
        path = self._write("data.bin", data)
        want = hashlib.sha256(data).hexdigest()
        for chunk in (1, 7, 256, 1 << 20):
            with self.subTest(chunk=chunk):
                self.assertEqual(sha256_of(path, chunk=chunk), want)

    def test_unreadable_files_raise_instead_of_colliding(self):
        # Two different unreadable paths must not produce equal "digests".
        for path in (os.path.join(self.dir, "missing-a.pdf"),
                     os.path.join(self.dir, "missing-b.pdf")):
            with self.subTest(path=path):
                with self.assertRaises(OSError):
                    sha256_of(path)

    def test_directory_raises(self):
        with self.assertRaises(OSError):
            sha256_of(self.dir)

    def test_non_positive_chunk_is_rejected(self):
        path = self._write("x.bin", b"x")
        for chunk in (0, -1):
            with self.subTest(chunk=chunk):
                with self.assertRaises(ValueError):
                    sha256_of(path, chunk=chunk)


if __name__ == "__main__":
    unittest.main()

# ==== stamp v1 | author=kjFriday | hmac-sha256=635cf31a5455a10dd430ad8ebbe2dbc1b252eabbe8b23734499f72aa7a3ea4f0 ====
