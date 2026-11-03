import copy,json,unittest
from ks import kinetic_karaoke as Q

class KaraokeTests(unittest.TestCase):
 def fixture(self):
  text='Hi 😀 there';material=dict(id='m',content=json.dumps(dict(text=text,styles=[dict(range=[0,11],fill=dict(content=dict(solid=dict(color=[1,1,1]))),font=dict(path='kept'))])))
  seg=dict(id='c',material_id='m',target_timerange=dict(start=1000000,duration=2000000))
  draft=dict(materials=dict(texts=[material]),tracks=[dict(type='text',name='subtitle',segments=[seg])])
  plan=dict(blocks=[dict(cue_id='c',units=[dict(text=text,start=1,end=3)])])
  words=[dict(word='Hi',start=0,end=.2),dict(word='😀',start=.3,end=.5),dict(word='there',start=.7,end=1)]
  return draft,plan,words
 def test_grounded_unicode_offsets_and_no_plan_mutation(self):
  d,p,w=self.fixture();out=Q.enrich(d,p,{'c':w});s=out['blocks'][0]['units'][0]['color_spans']
  self.assertEqual(s,[dict(first=0,last=2,start=1,end=1.2),dict(first=3,last=4,start=1.3,end=1.5),dict(first=5,last=10,start=1.7,end=2)])
  self.assertNotIn('color_spans',p['blocks'][0]['units'][0])
 def test_mismatch_uncertain_overlap_and_alias_do_not_fake_words(self):
  for change in ('wrong','low','overlap','alias'):
   d,p,w=self.fixture()
   if change=='wrong':w[-1]['word']='invented'
   if change=='low':w[0]['confidence']=.1
   if change=='overlap':w[1]['start']=.1
   if change=='alias':p['blocks'][0]['form']='numeric'
   o=Q.enrich(d,p,{'c':w});self.assertEqual(o['blocks'][0]['units'][0]['color_spans'],[])
 def test_native_utf16_and_motion_does_not_restart(self):
  d,p,w=self.fixture();e=Q.enrich(d,p,{'c':w})['blocks'][0]['units'][0]
  seg=d['tracks'][0]['segments'][0];seg['common_keyframes']=[dict(property_type='KFTypeAlpha',keyframe_list=[dict(time_offset=0,values=[0.],curveType='Line'),dict(time_offset=400000,values=[1.],curveType='Line')])]
  d['tracks'][0]['ks_role']='kinetic_super';entries=[e];report=Q.apply(d,entries,dict(base='#ffffff',accent='#ff0000',secondary='#00ff00'))
  self.assertEqual(report['measured_units'],1)
  segments=d['tracks'][0]['segments'];self.assertGreater(len(segments),3)
  at=next(s for s in segments if s['target_timerange']['start']==1300000)
  self.assertAlmostEqual(at['common_keyframes'][0]['keyframe_list'][0]['values'][0],.75)
  m=next(m for m in d['materials']['texts'] if m['id']==at['material_id']);content=json.loads(m['content'])
  self.assertEqual([s['range'] for s in content['styles']],[[0,3],[3,5],[5,11]])
  self.assertEqual(content['styles'][1]['fill']['content']['solid']['color'],[1.,0.,0.])
  self.assertTrue(all(s['font']['path']=='kept' for s in content['styles']))
  self.assertEqual(sum(s['target_timerange']['duration'] for s in segments),2000000)

 def test_native_word_times_and_partial_word_boundaries(self):
  d,p,w=self.fixture();d['materials']['texts'][0]['words']=dict(text=['Hi','😀','there'],start_time=[0,300,700],end_time=[200,500,1000])
  o=Q.enrich(d,p);self.assertEqual(len(o['blocks'][0]['units'][0]['color_spans']),3)
  p['blocks'][0]['units'][0]['text']='ther'
  o=Q.enrich(d,p);self.assertEqual(o['blocks'][0]['units'][0]['color_spans'],[])
 def test_nonlinear_existing_motion_kept_untouched(self):
  d,p,w=self.fixture();entry=Q.enrich(d,p,{'c':w})['blocks'][0]['units'][0]
  d['tracks'][0]['ks_role']='kinetic_super'
  d['tracks'][0]['segments'][0]['common_keyframes']=[dict(keyframe_list=[dict(time_offset=0,values=[0],curveType='Bezier')])]
  before=copy.deepcopy(d);r=Q.apply(d,[entry],dict(accent='#ff0000',secondary='#00ff00'))
  self.assertEqual(d,before);self.assertEqual(r['measured_units'],0)
