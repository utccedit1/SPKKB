import unittest

from ks.cli_highlight_coherence import check, judge, verdict


class HighlightCoherenceTests(unittest.TestCase):
    def test_single_candidate_cannot_pass_without_grounded_evidence(self):
        candidate={'axis':'ทัศนคติ','cuts':[{'role':'hook','text':'ทัศนคติสำคัญอย่างไร'},
                    {'role':'conclusion','text':'เปิดใจเรียนรู้เสมอ'}]}
        with self.assertRaisesRegex(ValueError,'ความต่อเนื่อง'):
            judge([candidate],lambda prompt:'{"coherent":true}')
    def test_parses_fenced_critical_verdict(self):
        self.assertFalse(verdict('```json\n{"coherent":false,"reason":"topic adjacent"}\n```'))
        with self.assertRaises(ValueError):
            verdict('{"coherent":"false"}')

    def test_rejects_disconnected_middle_despite_complete_boundaries(self):
        story={'cuts':[{'role':'hook','text':'เบื้องหลังงานต้องเตรียมอย่างไร'},
                       {'role':'body','text':'เลือกอินฟลูเอนเซอร์ให้ตรงกลุ่ม'},
                       {'role':'conclusion','text':'งานสร้างคุณค่าได้'}]}
        with self.assertRaisesRegex(ValueError,'เรื่องเดียวกัน'):
            check(story, lambda prompt:'{"coherent":false}')
        check(story, lambda prompt:'{"coherent":true}')

    def test_judge_requires_grounded_evidence_for_every_passage(self):
        candidates = [
            {'axis': 'เตรียมงานเบื้องหลัง', 'cuts': [
                {'role': 'hook', 'text': 'วันนี้พาดูเบื้องหลังการจัดงานตั้งแต่เริ่ม'},
                {'role': 'body', 'text': 'การเลือกอินฟลูเอนเซอร์ต้องดูกลุ่มเป้าหมายก่อน'},
                {'role': 'conclusion', 'text': 'เมื่อเตรียมทีมครบงานจึงออกมาราบรื่น'}]},
            {'axis': 'เลือกอินฟลูเอนเซอร์ให้ตรงกลุ่มเป้าหมาย', 'cuts': [
                {'role': 'hook', 'text': 'ทำไมบางแคมเปญใช้อินฟลูเอนเซอร์แล้วเงียบ'},
                {'role': 'body', 'text': 'การเลือกอินฟลูเอนเซอร์ต้องดูกลุ่มเป้าหมายก่อน'},
                {'role': 'conclusion', 'text': 'เมื่อเลือกคนตรงกลุ่มผลลัพธ์จะชัดเจน'}]},
        ]
        # Candidate 1 claims coherent=true with fabricated quote not in passage 2 -> rejected!
        reply = {'verdicts': [
            {'candidate': 1, 'coherent': True,
             'evidence': ['เบื้องหลังการจัดงาน', 'เตรียมไฟและเวทีหลังบ้าน', 'เตรียมทีมครบงานจึงออกมาราบรื่น']},
            {'candidate': 2, 'coherent': True,
             'evidence': ['ใช้อินฟลูเอนเซอร์แล้วเงียบ', 'ต้องดูกลุ่มเป้าหมายก่อน', 'เลือกคนตรงกลุ่มผลลัพธ์จะชัดเจน']},
        ], 'best': 1}
        verdicts, preferred = judge(candidates, lambda prompt: reply)
        self.assertFalse(verdicts[0]['coherent'])
        self.assertIn('2', verdicts[0]['issue'])
        self.assertTrue(verdicts[1]['coherent'])
        self.assertIsNone(preferred)
