import copy
import unittest
from ks import stock_media as M


class CompositionTests(unittest.TestCase):
    def test_density_scales_with_duration_and_is_bounded(self):
        self.assertEqual(M.budget(82),7)
        self.assertLess(M.budget(82,'sparse'),M.budget(82,'rich'))
        self.assertEqual(M.budget(180,'rich'),20)
        self.assertLessEqual(M.budget(600,'rich'),30)

    def test_speaker_window_crosses_cut_and_keeps_speed_refs_without_audio(self):
        segments=[]
        for i in range(2):
            segments.append(dict(id=str(i),material_id=str(i),target_timerange=dict(start=i*5000000,duration=5000000),source_timerange=dict(start=10000000,duration=10000000),volume=1,extra_material_refs=['speed','animation'],common_keyframes=[dict(id='old')],clip=dict(scale=dict(x=1,y=1))))
        draft=dict(tracks=[dict(type='video',segments=segments)],materials=dict(material_animations=[dict(id='animation')]))
        original=copy.deepcopy(draft)
        self.assertEqual(M.speaker_window(draft,4,3,14001),2)
        pieces=draft['tracks'][-1]['segments']
        self.assertEqual(draft['tracks'][0],original['tracks'][0])
        self.assertEqual([p['target_timerange']['duration'] for p in pieces],[1000000,2000000])
        self.assertEqual([p['source_timerange']['start'] for p in pieces],[18000000,10000000])
        for p in pieces:
            self.assertEqual(p['volume'],0)
            self.assertEqual(p['extra_material_refs'],['speed'])
            self.assertEqual(p['common_keyframes'],[])
            self.assertNotIn(p['id'],['0','1'])

    def test_alternatives_cannot_contain_urls(self):
        captions=[dict(start=0,text='paper')]
        story=dict(duration=20,cuts=[dict(first_id=0,last_id=0,start=0,end=20)])
        request=dict(kind='broll',query='paper documents',first_id=0,alternatives=[dict(query='https://bad.test',required_terms=['paper'])])
        with self.assertRaises(ValueError):M.requests(dict(stock_requests=[request]),story,captions,True)

    def test_downloads_follow_speech_order_and_only_no_match_uses_fallback(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from ks import stock_accounts as A
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'draft_info.json'
            path.write_text(json.dumps(dict(duration=80000000,tracks=[])))
            plan=dict(auto_stock=True,stock_provider='artlist',stock_requests=[dict(kind='broll',query='paper desk',start=47),dict(kind='broll',query='calendar week',start=18,alternatives=[dict(query='weekly planner',required_terms=['planner'])])])
            seen=[]
            def download(owner,provider,request,progress):seen.append((request['query'],request['start']));return None
            with patch.object(A,'wait_download',side_effect=download):M.apply(folder,plan,'owner',lambda *a:None,lambda *a:None)
            self.assertEqual(seen,[('calendar week',18),('weekly planner',18),('paper desk',47)])
            with patch.object(A,'wait_download',side_effect=ValueError('login required')) as download:
                with self.assertRaisesRegex(ValueError,'login required'):M.apply(folder,plan,'owner',lambda *a:None,lambda *a:None)
                self.assertEqual(download.call_count,1)

    def test_generated_stock_is_never_used_as_speaker(self):
        draft=dict(tracks=[dict(type='video',name='ช่วยด้วยจ้า · B-roll ออนไลน์',segments=[])])
        self.assertEqual(M.speaker_window(draft,4,3,14001),0)

    def test_trim_density_preserves_grounding_and_spreads_valid_shots(self):
        captions=[dict(start=i*5,text='calendar') for i in range(8)]
        story=dict(duration=35,cuts=[dict(first_id=0,last_id=7,start=0,end=35)])
        rows=[dict(kind='broll',first_id=i,query='calendar dates',required_terms=['calendar']) for i in (1,2,3,4,5)]
        selected=M.requests(dict(stock_requests=rows),story,captions,True,trim_excess=True)
        self.assertLessEqual(len(selected),M.budget(35))
        self.assertEqual(selected[0]['start'],5)
        self.assertEqual(selected[-1]['start'],25)
        rows[-1]['first_id']=99
        with self.assertRaisesRegex(ValueError,'นอกช่วง'):
            M.requests(dict(stock_requests=rows),story,captions,True,trim_excess=True)
