import copy
import json
from pathlib import Path
import tempfile
import unittest
from ks.cli_lab_polish import clean,candidates
from ks.cli_lab_visuals import library,select


class PolishTests(unittest.TestCase):
    def fixture(self):
        words=[dict(word='สวัสดี ',start=.1,end=.6),dict(word='เอ่อ ',start=.7,end=1),dict(word='ทุกคน',start=1.1,end=2)]
        draft={'duration':3000000,'fps':30,'materials':{'texts':[{'id':'m','content':json.dumps({'text':'สวัสดี เอ่อ ทุกคน','styles':[]})}],'videos':[]},'tracks':[{'id':'v','type':'video','segments':[{'id':'v1','material_id':'video','speed':2,'source_timerange':{'start':10000000,'duration':6000000},'target_timerange':{'start':0,'duration':3000000}}]},{'id':'t','type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':3000000}}]},{'id':'a','type':'audio','segments':[{'id':'a1','source_timerange':{'start':2000000,'duration':3000000},'target_timerange':{'start':0,'duration':3000000}}]}]}
        return draft,{'s':words}

    def test_ripple_preserves_sources_and_all_tracks_and_text(self):
        d,t=self.fixture();original=copy.deepcopy(d)
        out,times,report=clean(d,t)
        self.assertEqual(d,original);self.assertEqual(out['duration'],2700000)
        self.assertEqual(len(report['removed']),1)
        v=out['tracks'][0]['segments'];self.assertEqual([s['target_timerange']['start'] for s in v],[0,700000])
        self.assertEqual(v[1]['source_timerange']['start'],12000000)
        self.assertEqual(v[0]['_speech_motion'],v[1]['_speech_motion'])
        lookup={m['id']:json.loads(m['content'])['text'] for m in out['materials']['texts']}
        text=''.join(lookup[s['material_id']] for s in out['tracks'][1]['segments'])
        self.assertNotIn('เอ่อ',text);self.assertIn('ทุกคน',text)
        self.assertEqual(out['tracks'][2]['segments'][1]['source_timerange']['start'],3000000)
        self.assertEqual(len(times),2)

    def test_never_delete_meaningful_words_or_shared_or_uncertain_tokens(self):
        d,t=self.fixture();t['s'][1]['word']='คือ แบบ ก็ '
        d['materials']['texts'][0]['content']=json.dumps({'text':'สวัสดี คือ แบบ ก็ ทุกคน'})
        self.assertEqual(candidates(d,t),[])
        d,t=self.fixture();t['s'][1]['start']=.55
        self.assertEqual(candidates(d,t),[])
        d,t=self.fixture();t['s'][1]['word']='เอ่อทุกคน'
        self.assertEqual(candidates(d,t),[])

    def test_missing_times_cannot_fabricate_edits(self):
        d,t=self.fixture();out,times,report=clean(d,{})
        self.assertEqual(out,d);self.assertEqual(report['saved_seconds'],0)

    def test_library_matches_real_local_files_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'sample.png').write_bytes(b'fixture')
            (root/'library.json').write_text(json.dumps([{'file':'sample.png','tags':['ทุกคน'],'kind':'sticker'}]))
            records=library(root);d,t=self.fixture();d['duration']=16000000;d['tracks'][1]['segments'][0]['target_timerange']['start']=5000000
            chosen=select(d,records);self.assertEqual(chosen[0]['kind'],'sticker')
            self.assertEqual(select(d,[dict(records[0],tags=['ไม่มีคำนี้'])]),[])
            (root/'library.json').write_text(json.dumps([{'file':'../sample.png','tags':['test']}]))
            with self.assertRaises(ValueError):library(root)

if __name__=='__main__':unittest.main()
