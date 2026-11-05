import copy
import json
import unittest
from ks import editorial_checks


def segment(start, duration, **extra):
    return dict(target_timerange=dict(start=int(start*1e6), duration=int(duration*1e6)), **extra)


class EditorialChecksTests(unittest.TestCase):
    def test_uncovered_timeline_intervals_include_head_internal_tail(self):
        draft = dict(duration=5000000, tracks=[dict(type='video', segments=[segment(1, 1), segment(3, 1)])])
        result = editorial_checks.report(draft, {})
        self.assertEqual([(r['start'], r['end']) for r in result['issues'] if r['code']=='visual_timeline_gap'], [(0,1),(2,3),(4,5)])
        self.assertTrue(all(r['severity']=='warning' and r['reason'] for r in result['issues']))

    def test_secondary_video_covers_gap_and_disabled_video_does_not(self):
        draft = dict(duration=3000000, tracks=[dict(type='video', segments=[segment(0,1),segment(2,1)]),dict(type='video', segments=[segment(1,1)])])
        self.assertFalse(editorial_checks.report(draft,{})['issues'])
        draft['tracks'][1]['segments'][0]['visible']=False
        self.assertEqual(editorial_checks.report(draft,{})['issues'][0]['start'],1)

    def test_caption_newlines_dense_short_text_and_overlay_exclusion(self):
        draft = dict(duration=3000000, materials=dict(texts=[dict(id='a',content=json.dumps(dict(text='first\nsecond'))),dict(id='b',content=json.dumps(dict(text='Dense readable words need enough time')))]),tracks=[dict(type='video',segments=[segment(0,3)]),dict(type='text',segments=[segment(0,1,material_id='a'),segment(1,.3,material_id='b')]),dict(type='text',ks_role='overlay',segments=[segment(0,.1,material_id='b')])])
        before=copy.deepcopy(draft)
        result=editorial_checks.report(draft,{})
        self.assertEqual([r['code'] for r in result['issues']],['caption_multiline','caption_reading_pace'])
        self.assertEqual(result['issues'][1]['evidence_kind'],'heuristic')
        self.assertEqual(draft,before)
        self.assertIn('audio_listening',result['unsupported_checks'])
        self.assertIn('face_crop_tracking',result['unsupported_checks'])

    def test_missing_and_invalid_evidence_never_claims_clean(self):
        result=editorial_checks.report(dict(duration=1000000,tracks=[]),{})
        self.assertEqual(result['status'],'needs_review')
        self.assertIn('video_timeline',result['missing_evidence'])
        result=editorial_checks.report(dict(duration=-1,tracks=[]),{})
        self.assertIn('valid_duration',result['missing_evidence'])

    def test_unknown_video_interval_does_not_invent_a_gap(self):
        draft=dict(duration=3000000,tracks=[dict(type='video',segments=[segment(0,1),dict(target_timerange=dict(start='unknown',duration=2000000))])])
        result=editorial_checks.report(draft,{})
        self.assertIn('invalid_video_interval',result['missing_evidence'])
        self.assertFalse(result['issues'])

    def test_hidden_attribute_video_cannot_cover_timeline_gap(self):
        draft=dict(duration=3000000,tracks=[dict(type='video',segments=[segment(0,1),segment(2,1)]),dict(type='video',attribute=1,segments=[segment(1,1)])])
        before=copy.deepcopy(draft)
        gaps=editorial_checks.report(draft,{})['issues']
        self.assertEqual([(r['start'],r['end']) for r in gaps],[(1,2)])
        self.assertEqual(draft,before)

    def test_hidden_speech_and_generic_kinetic_super_do_not_warn(self):
        draft=dict(duration=3000000,materials=dict(texts=[dict(id='a',content=json.dumps(dict(text='long caption\nsecond line dense words')))]),tracks=[dict(type='video',segments=[segment(0,3)]),dict(type='text',attribute=1,segments=[segment(0,.1,material_id='a')]),dict(type='text',ks_role='kinetic_super',segments=[segment(0,.1,material_id='a')])])
        before=copy.deepcopy(draft)
        self.assertFalse(editorial_checks.report(draft,{})['issues'])
        self.assertEqual(draft,before)

    def test_nested_selected_camera_partial_and_internal_gaps(self):
        draft=self._nested([segment(.2,.6),segment(1.2,.6)])
        before=copy.deepcopy(draft)
        result=editorial_checks.report(draft,{})
        self.assertEqual([(round(r['start'],3),round(r['end'],3)) for r in result['issues']],[(0,.2),(.8,1.2),(1.8,2)])
        self.assertEqual(draft,before)

    def test_nested_speed_and_source_offset_map_to_parent_target(self):
        draft=self._nested([segment(1.4,2)])
        draft['duration']=5000000
        parent=draft['tracks'][0]['segments'][0]
        parent.update(speed=2,source_timerange=dict(start=1000000,duration=4000000),target_timerange=dict(start=3000000,duration=2000000))
        result=editorial_checks.report(draft,{})
        self.assertEqual([(round(r['start'],3),round(r['end'],3)) for r in result['issues']],[(0,3.2),(4.2,5)])

    def test_nested_unknown_reference_or_curve_suppresses_gap_claim(self):
        for mode in ('reference','curve'):
            draft=self._nested([segment(.2,1.6)])
            if mode=='reference':
                draft['materials']['drafts']=[]
            else:
                draft['materials']['speeds']=[dict(id='curve',curve_speed=dict(points=[1]))]
                draft['tracks'][0]['segments'][0]['extra_material_refs'].append('curve')
            result=editorial_checks.report(draft,{})
            self.assertFalse(result['issues'])
            self.assertTrue(result['missing_evidence'])

    def _nested(self, child_segments):
        child=dict(tracks=[dict(id='A',type='video',segments=[segment(0,2)]),dict(id='B',type='video',segments=child_segments)])
        return dict(duration=2000000,materials=dict(videos=[dict(id='wrapper',multi_camera_info=dict(cur_camera_track_id='B'))],drafts=[dict(id='child',draft=child)]),tracks=[dict(type='video',segments=[segment(0,2,material_id='wrapper',extra_material_refs=['child'],source_timerange=dict(start=0,duration=2000000))])])
