import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from ks import core_engine as CE
from ks.cli_lab_backdrop import _black_photo, _needs_backdrop


def _png(path, color):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(b'\x00' + bytes(color))) + chunk(b'IEND', b'')
    path.write_bytes(data)


class BackdropTests(unittest.TestCase):
    def test_only_real_black_photo_placeholder_triggers(self):
        ffmpeg = CE.ac_ffmpeg_bin()
        if not ffmpeg:
            self.skipTest('ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as folder:
            black, bright = Path(folder) / 'black.png', Path(folder) / 'bright.png'
            _png(black, (0, 0, 0)); _png(bright, (180, 100, 20))
            self.assertTrue(_black_photo(black, ffmpeg))
            self.assertFalse(_black_photo(bright, ffmpeg))
            draft = {'materials': {'videos': [{'id': 'a', 'type': 'photo', 'path': str(black)}]},
                     'tracks': [{'type': 'video', 'attribute': 0, 'segments': [{'material_id': 'a'}]}]}
            self.assertTrue(_needs_backdrop(draft, ffmpeg))
            draft['materials']['videos'][0]['path'] = str(bright)
            self.assertFalse(_needs_backdrop(draft, ffmpeg))
            draft['materials']['videos'][0].update(path=str(black), type='video')
            self.assertFalse(_needs_backdrop(draft, ffmpeg))
            draft['materials']['videos'][0]['type'] = 'photo'
            draft['materials']['drafts'] = [{'id': 'nested'}]
            self.assertFalse(_needs_backdrop(draft, ffmpeg))
