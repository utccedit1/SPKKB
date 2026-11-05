"""AI suggestions are untrusted; exercise real source/timing/layout validation."""
import copy
import json
import unittest
from unittest.mock import patch
from test_caption_presets import draft
from ks import editorial_ai as A, kinetic_full as F


class EditorialAITests(unittest.TestCase):
    def setUp(self):
        self.d = draft()
        self.d['canvas_config'] = dict(width=1920, height=1080)
        self.source = 'เราไม่ได้ลดคุณภาพ แต่ลดขั้นตอนที่ไม่จำเป็น'
        self.d['materials']['texts'][0]['content'] = json.dumps(dict(text=self.source, styles=[]))
        self.p = F.plan(self.d)
        self.choice = dict(cue_id='one', rows=['เราไม่ได้ลดคุณภาพ', 'แต่ลดขั้นตอนที่ไม่จำเป็น'],
                           form='contrast', role='contrast', accent=1)

    def call(self, response):
        with patch('ks.event_clip.provider_config', return_value=({}, 'test')) as config, patch('ks.cli_lab_webhook.request', return_value=response) as request:
            result = A.design(self.d, self.p, dict(font=''), 'route', lambda _: None)
            config.assert_called_once_with('route', feature='suggest')
            self.assertEqual(request.call_count, 1)
            return result

    def test_grounded_choice_preserves_times_camera_and_omits_other_cues(self):
        self.p['blocks'][0]['camera_move'] = 'cinematic'
        before = copy.deepcopy(self.p)
        out = self.call(dict(blocks=[self.choice]))
        self.assertEqual([(u['start'], u['end']) for u in out['blocks'][0]['units']], [(0, 1), (0, 1)])
        self.assertEqual(out['blocks'][0]['camera_move'], 'cinematic')
        self.assertFalse(out['blocks'][1]['enabled'])
        self.assertTrue(out['blocks'][1]['editorial_skip'])
        self.assertEqual(self.p, before)

    def test_invented_reordered_dropped_negation_and_timing_are_rejected(self):
        bad = [dict(self.choice, rows=['คุณภาพดีขึ้น']),
               dict(self.choice, rows=list(reversed(self.choice['rows']))),
               dict(self.choice, rows=['ลดคุณภาพ', 'แต่ลดขั้นตอนที่ไม่จำเป็น']),
               dict(self.choice, start=99),
               dict(self.choice, cue_id='unknown')]
        for choice in bad:
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                self.call(dict(blocks=[choice]))

    def test_missing_middle_qualification_cannot_be_removed(self):
        with self.assertRaises(ValueError):
            self.call(dict(blocks=[dict(self.choice, rows=['เราไม่ได้', 'แต่ลดขั้นตอนที่ไม่จำเป็น'])]))

    def test_duplicate_cues_and_unreadable_layout_are_rejected(self):
        with self.assertRaises(ValueError):self.call(dict(blocks=[self.choice, self.choice]))
        self.d['canvas_config'] = dict(width=1080, height=1920)
        with self.assertRaisesRegex(ValueError, 'พื้นที่อ่านง่าย'):
            self.call(dict(blocks=[self.choice]))

    def test_oversized_cue_fails_before_provider_request(self):
        self.d['materials']['texts'][0]['content'] = json.dumps(dict(text='ชุมชน' * 4000, styles=[]))
        with patch('ks.event_clip.provider_config') as config, patch('ks.cli_lab_webhook.request') as request:
            with self.assertRaises(ValueError):A.design(self.d, self.p, {}, 'route', lambda _: None)
            config.assert_not_called()
            request.assert_not_called()

    def test_exact_but_dangling_pronoun_is_not_a_complete_super(self):
        self.d['materials']['texts'][0]['content']=json.dumps(dict(text='มันคือความคุ้มค่าเงิน',styles=[]))
        self.p=F.plan(self.d)
        with self.assertRaises(ValueError):
            self.call(dict(blocks=[dict(self.choice,rows=['มัน'],form='punch',role='detail',accent=0)]))

    def test_timeout_is_one_request_no_fallback(self):
        with patch('ks.event_clip.provider_config', return_value=({}, 'test')), patch('ks.cli_lab_webhook.request', side_effect=TimeoutError('timeout')) as request:
            with self.assertRaises(TimeoutError):A.design(self.d, self.p, {}, 'route', lambda _: None)
            self.assertEqual(request.call_count, 1)

    def test_empty_ai_selection_is_valid_caption_only(self):
        out = self.call(dict(blocks=[]))
        self.assertTrue(out['caption_only'])
        self.assertTrue(all(not b['enabled'] and b['editorial_skip'] for b in out['blocks']))

    def test_batches_are_bounded_and_no_batch_can_select_another_cue(self):
        d = self.d
        template = d['tracks'][0]['segments'][0]
        d['tracks'][0]['segments'] = [dict(copy.deepcopy(template), id='c'+str(i), target_timerange=dict(start=i*1000000,duration=1000000)) for i in range(21)]
        d['duration'] = 21000000
        with patch('ks.event_clip.provider_config', return_value=({}, 'test')), patch('ks.cli_lab_webhook.request', return_value=dict(blocks=[])) as request:
            A.design(d, F.plan(d), {}, 'route', lambda _: None)
            self.assertEqual(request.call_count, 2)
            for args in request.call_args_list:
                self.assertLessEqual(len(args.args[0]), 16000)
        with patch('ks.event_clip.provider_config', return_value=({}, 'test')), patch('ks.cli_lab_webhook.request', return_value=dict(blocks=[dict(self.choice,cue_id='c20')])) as request:
            with self.assertRaises(ValueError):A.design(d, F.plan(d), {}, 'route', lambda _: None)
            self.assertEqual(request.call_count, 1)
