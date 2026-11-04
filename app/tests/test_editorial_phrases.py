"""Grounded editorial selection: no topic-specific examples or rewritten claims."""
import unittest
from ks.editorial_phrases import select


def parts(*texts):
    return [dict(text=t, start=i, end=i + 1) for i, t in enumerate(texts)]


class EditorialPhraseTests(unittest.TestCase):
    def test_short_action_prefix_keeps_complete_support(self):
        source = 'เพื่อทำภารกิจให้สำเร็จ'
        result = select(source, parts('เพื่อทำ', 'ภารกิจให้สำเร็จ'))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['เพื่อทำ', 'ภารกิจให้สำเร็จ'])

    def test_long_question_does_not_turn_tail_into_unqualified_claim(self):
        texts = ['ทำไมชุมชนจึงต้องร่วมมือกัน', 'คนในชุมชนร่วมกันดูแลพื้นที่สีเขียว' * 3,
                 'โรงเรียนจัดกิจกรรมเรียนรู้ธรรมชาติ' * 3, 'ครอบครัวช่วยกันดูแลทรัพยากร' * 3]
        self.assertIsNone(select(' '.join(texts), parts(*texts)))

    def test_long_contrast_never_loses_original_negation(self):
        texts = ['เราไม่ได้ยกเลิกการดูแลพื้นที่สีเขียว' * 3,
                 'แต่คนในชุมชนร่วมกันดูแลพื้นที่สีเขียว' * 2,
                 'โรงเรียนจัดกิจกรรมเรียนรู้ธรรมชาติ' * 2]
        result = select(' '.join(texts), parts(*texts))
        self.assertTrue(result is None or 'ไม่ได้' in ' '.join(result['rows']))

    def test_measured_question_keeps_topic_and_question_as_two_rows(self):
        for left, right in [('แคมเปญแปะสติ๊กเกอร์', 'รับส่วนลดไหมคะ'),
                            ('โครงการฟื้นฟูแนวปะการัง', 'ชุมชนจะร่วมดูแลอย่างไร')]:
            result = select(left + right, parts(left, right))
            self.assertIsNotNone(result)
            self.assertEqual(result['rows'], [left, right])
            self.assertEqual(result['role'], 'question')

    def test_excessive_input_is_declined(self):
        self.assertIsNone(select('ดูแลชุมชน' * 3000, parts('ดูแลชุมชน' * 3000)))
        self.assertIsNone(select('คน' * 501, parts(*(['คน'] * 501))))

    def test_long_paragraph_uses_compact_adjacent_measured_rows(self):
        phrases = ['alpha beta gamma'] * 12
        result = select(' '.join(phrases), parts(*phrases))
        self.assertIsNotNone(result)
        self.assertEqual(len(result['rows']), 2)
        self.assertTrue(all(len(row) <= 40 for row in result['rows']))

    def test_question_and_answer_paragraph_can_select_complete_question_clause(self):
        question = 'ทำไมชุมชนจึงต้องร่วมมือกันรู้ไหมคะ'
        explanation = 'เพราะพื้นที่สีเขียวต้องอาศัยทุกคนช่วยกันดูแล' * 4
        result = select(question + explanation, parts(question, explanation))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], [question])
        self.assertEqual(result['role'], 'question')

    def test_independent_contrast_before_complete_question_is_not_suppressed(self):
        statement = 'เราไม่ได้ลดคุณภาพ แต่ลดขั้นตอนที่ไม่จำเป็น'
        question = 'เพราะอะไรรู้ไหมคะ'
        explanation = 'เพราะทุกคนร่วมมือกันปรับปรุงการทำงาน' * 5
        result = select(statement + question + explanation, parts(statement, question, explanation))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['เราไม่ได้ลดคุณภาพ', 'แต่ลดขั้นตอนที่ไม่จำเป็น'])
        self.assertEqual(result['role'], 'contrast')

    def test_prefers_economical_complete_definition_over_long_adjacent_blob(self):
        texts = ['ความร่วมมือในการช่วยกันดูแลสิ่งแวดล้อมของคนในพื้นที่',
                 'คือการร่วมกันสร้างพื้นที่เรียนรู้ให้สมาชิกในชุมชนทุกคน',
                 'ชุมชนร่วมกันดูแลพื้นที่สีเขียว' * 12,
                 'ภูมิคุ้มกันชุมชน', 'คือความร่วมมือในการดูแลคนรอบตัว']
        result = select(' '.join(texts), parts(*texts))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['ภูมิคุ้มกันชุมชน', 'คือความร่วมมือในการดูแลคนรอบตัว'])

    def test_definition_keeps_concept_and_explanation(self):
        source = 'ภูมิคุ้มกันชุมชน คือความร่วมมือในการดูแลคนรอบตัว'
        result = select(source, parts(source))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['ภูมิคุ้มกันชุมชน', 'คือความร่วมมือในการดูแลคนรอบตัว'])
        self.assertEqual(result['role'], 'definition')

    def test_question_retains_whole_unfamiliar_question(self):
        source = 'ทำไมแมลงกลางคืนจึงบินเข้าหาแสงไฟ'
        result = select(source, parts(source))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], [source])
        self.assertEqual(result['role'], 'question')

    def test_contrast_preserves_negation_and_source_order(self):
        source = 'เราไม่ได้ลดคุณภาพ แต่ลดขั้นตอนที่ไม่จำเป็น'
        result = select(source, parts('เราไม่ได้ลดคุณภาพ', 'แต่ลดขั้นตอนที่ไม่จำเป็น'))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['เราไม่ได้ลดคุณภาพ', 'แต่ลดขั้นตอนที่ไม่จำเป็น'])
        self.assertEqual(result['role'], 'contrast')

    def test_cause_result_remains_grounded(self):
        source = 'เพราะดินเก็บความชื้นได้ดี ต้นกล้าจึงเติบโตเร็วขึ้น'
        result = select(source, parts('เพราะดินเก็บความชื้นได้ดี', 'ต้นกล้าจึงเติบโตเร็วขึ้น'))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], ['เพราะดินเก็บความชื้นได้ดี', 'ต้นกล้าจึงเติบโตเร็วขึ้น'])
        self.assertEqual(result['role'], 'result')

    def test_units_and_english_compound_are_not_isolated(self):
        source = 'ใช้ machine learning ลดเวลาจาก 20 นาที เหลือ 5 นาที'
        result = select(source, parts('ใช้ machine learning', 'ลดเวลาจาก 20 นาที', 'เหลือ 5 นาที'))
        self.assertIsNotNone(result)
        self.assertIn('machine learning', ' '.join(result['rows']))
        self.assertIn('20 นาที', ' '.join(result['rows']))
        self.assertIn('5 นาที', ' '.join(result['rows']))
        self.assertNotEqual(result['form'], 'numeric')

    def test_numeric_unit_at_measured_boundary_is_not_split(self):
        source = 'เก็บน้ำได้ 20 ลิตรต่อวัน ช่วยลดการใช้น้ำประปา'
        result = select(source, parts('เก็บน้ำได้ 20', 'ลิตรต่อวัน', 'ช่วยลดการใช้น้ำประปา'))
        self.assertIsNotNone(result)
        self.assertIn('20 ลิตรต่อวัน', ' '.join(result['rows']))
        self.assertFalse(any(row.endswith('20') for row in result['rows']))

    def test_rejects_unordered_or_invented_parts(self):
        for measured in [parts('ต้นกล้าเติบโต', 'ดินเก็บน้ำ'), parts('ดินเก็บน้ำ', 'ผลผลิตเพิ่ม')]:
            self.assertIsNone(select('ดินเก็บน้ำ ต้นกล้าเติบโต', measured))

    def test_rejects_dangling_connectors_and_fragmentary_labels(self):
        for source in ['เพราะ', 'เราเลือกแนวทางนี้เพราะ', 'และ แต่ เพราะ', 'นวัตกรรม',
                       'ต้นกล้าเติบโตได้ดีเมื่อ', 'ทุกคนร่วมมือกันฉะนั้น',
                       'กลุ่มนักเรียนเลือกซื้อในราคา', 'เราต้องร่วมกันทำสิ่งที่อยาก',
                       'สิ่งหนึ่งที่อาจจะ', 'ทำให้คุณไม่รู้เลยด้วยซ้ำว่าคุณ',
                       'เพราะถ้าเกิดครอบครัวมีสิ่งของ']:
            self.assertIsNone(select(source, parts(source)))

    def test_keeps_short_complete_phrase_without_rewriting(self):
        source = 'ชุมชนช่วยดูแลผู้สูงอายุ'
        result = select(source, parts(source))
        self.assertIsNotNone(result)
        self.assertEqual(result['rows'], [source])

    def test_long_generic_source_uses_adjacent_measured_phrases(self):
        texts = ['ชุมชนร่วมกันดูแลพื้นที่สีเขียว' * 2,
                 'ทุกครอบครัวช่วยแยกขยะก่อนทิ้ง' * 2,
                 'โรงเรียนจัดกิจกรรมเรียนรู้ธรรมชาติ' * 2,
                 'เด็กนำความรู้กลับไปใช้ในครอบครัว' * 2]
        source = ' '.join(texts)
        result = select(source, parts(*texts))
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result['rows']), 2)
        self.assertTrue(all(len(row) <= 100 for row in result['rows']))
        cursor = 0
        for row in result['rows']:
            offset = source.find(row, cursor)
            self.assertGreaterEqual(offset, cursor)
            cursor = offset + len(row)


if __name__ == '__main__':
    unittest.main()
