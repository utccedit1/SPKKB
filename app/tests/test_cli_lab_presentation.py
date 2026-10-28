import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks.cli_lab_presentation import phrases,split_captions,emphasis

class PresentationTests(unittest.TestCase):
    def test_split_preserves_text_coverage_time_and_independent_materials(self):
        text='เราสามารถใช้เอไอช่วยลดระยะเวลาทำงานจากหนึ่งเดือนเหลือหนึ่งสัปดาห์และทำให้งานมีความถูกต้องมากขึ้น'
        draft={'duration':15000000,'materials':{'texts':[{'id':'m','content':json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':10}]})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':4000000,'duration':8000000}}]}]}
        original=copy.deepcopy(draft['materials']['texts'][0])
        from ks.cli_lab_presentation import phrases
        parts=phrases(text,18)
        timings={'s':[dict(word=part,start=i*8/len(parts),end=(i+1)*8/len(parts)) for i,part in enumerate(parts)]}
        self.assertGreater(split_captions(draft,timings),1)
        segments=draft['tracks'][0]['segments'];lookup={m['id']:m for m in draft['materials']['texts']}
        self.assertEqual(''.join(json.loads(lookup[s['material_id']]['content'])['text'].replace('\n','') for s in segments),text)
        self.assertEqual(segments[0]['target_timerange']['start'],4000000)
        self.assertEqual(sum(s['target_timerange']['duration'] for s in segments),8000000)
        for left,right in zip(segments,segments[1:]):self.assertEqual(left['target_timerange']['start']+left['target_timerange']['duration'],right['target_timerange']['start'])
        self.assertEqual(draft['materials']['texts'][0],original)
        for _,_,chosen in emphasis(draft):self.assertIn(chosen,text)

    def test_english_wrap_keeps_words(self):
        self.assertEqual(' '.join(phrases('What makes teams work?',18)),'What makes teams work?')

    def test_missing_word_times_never_guesses_timing(self):
        draft={'materials':{'texts':[{'id':'m','content':json.dumps({'text':'ข้อความยาวมาก'*20})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':10000000}}]}]}
        original=copy.deepcopy(draft)
        self.assertEqual(split_captions(draft),0)
        self.assertEqual(draft,original)

    def test_pauses_use_measured_boundaries_instead_of_character_ratio(self):
        from ks.cli_lab_alignment import native_words
        material={'content':json.dumps({'text':'first second'}),'words':{'text':['first ','second'],'start_time':[200,2500],'end_time':[700,3000]}}
        measured=native_words(material,4000000)
        self.assertEqual(measured[1]['start'],2.5)
        material['words']['text'][1]='wrong'
        self.assertIsNone(native_words(material,4000000))

    def test_coverage_rejects_one_source_and_accepts_both(self):
        from ks.cli_lab_story import check_coverage
        captions=[{'sources':['a.mov']},{'sources':['b.mov']}]
        story={'cuts':[{'first_id':0,'last_id':0}]}
        with self.assertRaisesRegex(ValueError,'b.mov'):check_coverage(story,captions)
        story['cuts'].append({'first_id':1,'last_id':1})
        check_coverage(story,captions)
        self.assertEqual(story['source_count'],2)

    def test_explicit_one_line_fallback_preserves_all_text_and_labels_estimated_times(self):
        text='ข้อความยาวมากที่ต้องแบ่งให้เป็นบรรทัดเดียวและไม่ทิ้งคำพูดแม้ว่าจะไม่มีเวลารายคำจากต้นฉบับ'
        draft={'duration':10000000,'materials':{'texts':[{'id':'m','content':json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':10}]})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':10000000}}]}]}
        report=[];split_captions(draft,allow_estimated=True,report=report)
        self.assertEqual(len(report),1)
        materials={m['id']:m for m in draft['materials']['texts']}
        pieces=[materials[s['material_id']] for s in draft['tracks'][0]['segments']]
        self.assertEqual(''.join(json.loads(m['content'])['text'] for m in pieces),text)
        for m in pieces:
            self.assertNotIn('\n',json.loads(m['content'])['text'])
            self.assertEqual(m['line_feed'],0)
            self.assertEqual(m['base_content'],m['content'])
            self.assertEqual(m['ks_timing_mode'],'estimated')
            self.assertEqual(m['words']['text'],[])
