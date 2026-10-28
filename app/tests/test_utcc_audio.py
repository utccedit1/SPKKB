import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ks import utcc_audio as A


class AudioTests(unittest.TestCase):
    def test_timed_text_and_global_offset(self):
        rows = A.parse_transcript({'transcript': '[00:00] สวัสดี\n[00:02] Content'}, 5, 180)
        self.assertEqual(rows, [{'start':180,'end':182,'text':'สวัสดี'},
                                {'start':182,'end':185,'text':'Content'}])

    def test_no_invented_timestamps(self):
        for value in ({'reply':'สรุปการประชุม'}, {'transcript':'สวัสดี'},
                      {'transcript':'[00:04] a [00:02] b'},
                      {'transcript':'[00:59] a'}, {'transcript':'[00:70] a'}):
            with self.assertRaises(ValueError): A.parse_transcript(value, 10)

    def test_credentials_are_opt_in_and_external(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(A,'CONFIG_DIR',folder):
            self.assertEqual(A.settings(), {})
            p=pathlib.Path(folder)/'audio_webhook.json'
            p.write_text('{"enabled":true,"url":"https://other.example/audio","secret":"x"}')
            self.assertEqual(A.settings(), {})

    def test_chunks_have_no_time_gap_or_extra_chunk(self):
        with patch.object(A,'send_audio',side_effect=lambda p,c,d,o: [{'start':o,'end':o+d,'text':'a'}]):
            calls=[]
            rows=A.transcribe('source',{},360,lambda v,p,o,d:calls.append((o,d)))
            self.assertEqual(calls,[(0,180),(180,180)])
            self.assertEqual(rows[-1]['end'],360)

    def test_pdf_only_backend_is_rejected(self):
        with tempfile.NamedTemporaryFile() as f, patch('requests.post') as post:
            post.return_value.status_code=400
            post.return_value.text='{"detail":"file must be PDF"}'
            with self.assertRaisesRegex(RuntimeError,'PDF'):
                A.send_audio(f.name,{'url':'https://chat.utcc.ac.th/test','secret':'x'},10)


if __name__=='__main__': unittest.main()
