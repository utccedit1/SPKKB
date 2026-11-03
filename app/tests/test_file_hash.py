import hashlib
from pathlib import Path
import tempfile
import unittest
from ks.file_hash import sha256_file


class FileHashTests(unittest.TestCase):
    def test_empty_and_multiple_chunks_match_full_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'media'
            for data in (b'', b'abc', b'abc' * 800000):
                path.write_bytes(data)
                self.assertEqual(sha256_file(path), hashlib.sha256(data).hexdigest())

    def test_missing_file_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                sha256_file(Path(folder) / 'missing')
