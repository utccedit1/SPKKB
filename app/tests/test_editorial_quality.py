"""Exact-source editorial quality regressions; no provider or timing fixtures."""
import unittest
from ks.editorial_quality import review


class EditorialQualityTests(unittest.TestCase):
    def test_keeps_unfamiliar_complete_phrases(self):
        for text in ('สาหร่ายช่วยดูดซับคาร์บอนในทะเล', 'เราไม่ได้ลดคุณภาพเพื่อเพิ่มกำไร',
                     'ต้นทุนลดลง 30% ในไตรมาสนี้', 'Customer Experience คือประสบการณ์ลูกค้า'):
            with self.subTest(text=text):
                self.assertEqual([], review(text, [text]))

    def test_rejects_rewriting_gap_and_lost_negation(self):
        self.assertIn('not_exact_contiguous_source', review('ยอดขายยังไม่เพิ่ม', ['ยอดขายเพิ่ม']))
        self.assertIn('not_exact_contiguous_source', review('รายได้และต้นทุนลดลง', ['รายได้', 'ลดลง']))
        self.assertIn('omitted_negation', review('เราไม่ได้ลดคุณภาพ', ['ลดคุณภาพ']))

    def test_business_compound_cannot_be_split_or_selected_partially(self):
        self.assertIn('split_compound', review('การทำธุรกิจต้องเข้าใจลูกค้า', ['การทำธุร', 'กิจต้องเข้าใจลูกค้า']))
        self.assertIn('split_compound', review('ธุรกิจคือการแก้ปัญหา', ['กิจคือการแก้ปัญหา']))
        self.assertEqual([], review('ธุรกิจคือการแก้ปัญหา', ['ธุรกิจ', 'คือการแก้ปัญหา']))

    def test_rejects_isolated_pronouns_modals_and_connectors(self):
        for rows in (['เรา', 'สร้างคุณค่าให้ชุมชน'], ['ต้อง', 'สร้างคุณค่าให้ชุมชน'],
                     ['สร้างคุณค่าเพื่อ', 'ช่วยเหลือชุมชน']):
            with self.subTest(rows=rows):
                self.assertIn('dangling_fragment', review(''.join(rows), rows))

    def test_question_typography_allows_whole_questions_but_not_dangling_response(self):
        self.assertEqual([], review('แคมเปญแปะสติ๊กเกอร์รับส่วนลดไหมคะ', ['แคมเปญแปะสติ๊กเกอร์', 'รับส่วนลดไหมคะ'], 'question'))
        self.assertEqual([], review('ทำไมคนถึงเลือกสินค้านี้', ['ทำไมคนถึงเลือกสินค้านี้'], 'question'))
        self.assertIn('false_question_reveal', review('ลูกค้าต้องการอะไร?เพราะ', ['ลูกค้าต้องการอะไร?', 'เพราะ'], 'question'))
        self.assertEqual([], review('ลูกค้าต้องการอะไร?ความมั่นใจในคุณภาพ', ['ลูกค้าต้องการอะไร?', 'ความมั่นใจในคุณภาพ'], 'question'))
        self.assertEqual([], review('ทำไมคนถึงเลือกสินค้านี้', ['ทำไมคนถึงเลือกสินค้านี้'], 'matched'))

    def test_preserves_english_words_and_quantity_units(self):
        self.assertIn('split_compound', review('Customer Experience สำคัญ', ['Custo', 'mer Experience สำคัญ']))
        self.assertIn('split_quantity', review('ยอดขายเพิ่ม 30 เปอร์เซ็นต์', ['ยอดขายเพิ่ม 30', 'เปอร์เซ็นต์']))
        self.assertEqual([], review('ยอดขายเพิ่ม 30% ในปีนี้', ['ยอดขายเพิ่ม 30%', 'ในปีนี้']))

    def test_declines_unreadable_rows_and_malformed_input(self):
        text = 'การสร้างความสัมพันธ์กับลูกค้าและการรักษาความไว้วางใจในระยะยาวเป็นเรื่องสำคัญมากสำหรับองค์กร'
        self.assertIn('row_too_long', review(text, [text]))
        self.assertIn('invalid_rows', review('คำเดิม', []))
        self.assertIn('invalid_rows', review('คำเดิม', [' คำเดิม']))
