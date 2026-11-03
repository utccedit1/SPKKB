import copy,json,unittest
from ks import caption_presets as P


def draft():
    return {'id':'main','duration':4000000,'canvas_config':{'width':1080,'height':1920},'materials':{'texts':[{'id':'m','type':'subtitle','group_id':'native','content':json.dumps({'text':'😀 เข้าใจผู้บริโภค','styles':[]})}]},'tracks':[{'type':'text','segments':[{'id':'one','material_id':'m','target_timerange':{'start':0,'duration':1000000}},{'id':'two','material_id':'m','target_timerange':{'start':2000000,'duration':1000000}}]}]}


class PresetTests(unittest.TestCase):
    def test_catalog_has_six_original_styles_and_motion_ends_at_identity(self):
        self.assertEqual(len(P.catalog()),6)
        for row in P.catalog():
            cfg=P.settings({'preset':row['id']},[])
            points=P.motion(cfg,120000)
            self.assertTrue(all(0<=p['t']<=120000 for p in points))
            self.assertEqual(points[-1]['scale'],1)
            self.assertEqual(points[-1]['alpha'],1)
            self.assertEqual(points[-1]['dy'],0)
    def test_invalid_settings_and_font_paths_fail_closed(self):
        for cfg in ({'preset':'unknown'},{'size':float('nan')},{'y':1},{'entry':0},{'color':'red'},{'font':'/private/no.ttf'}):
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):P.settings(cfg,[])
    def test_selected_shared_material_is_detached_without_changing_other_caption(self):
        source=draft();before=copy.deepcopy(source)
        cfg=P.settings({'keyword':'เข้าใจ','preset':'punch'},[])
        count=P.apply(source,['one'],cfg)
        self.assertEqual(count,1)
        segments=source['tracks'][0]['segments'];lookup={m['id']:m for m in source['materials']['texts']}
        self.assertEqual(segments[1],before['tracks'][0]['segments'][1])
        self.assertEqual(lookup['m'],before['materials']['texts'][0])
        m=lookup[segments[0]['material_id']];c=json.loads(m['content'])
        self.assertEqual(c['text'],'😀 เข้าใจผู้บริโภค')
        self.assertIn([3,9],[s['range'] for s in c['styles']])
        self.assertEqual(segments[0]['target_timerange'],before['tracks'][0]['segments'][0]['target_timerange'])
        self.assertEqual(m['type'],'subtitle');self.assertEqual(m['group_id'],'native')
    def test_invalid_selection_is_atomic(self):
        value=draft();before=copy.deepcopy(value)
        with self.assertRaises(ValueError):P.apply(value,['one','missing'],P.settings({},[]))
        self.assertEqual(value,before)
    def test_user_title_is_not_a_speech_caption(self):
        value=draft();value['materials']['texts'].append({'id':'title','type':'text','content':json.dumps({'text':'ชื่อตอน','styles':[]})})
        value['tracks'].append({'type':'text','name':'My title','segments':[{'id':'title-seg','material_id':'title','target_timerange':{'start':0,'duration':4000000}}]})
        self.assertEqual([s['id'] for _,s,m,t in P.caption_rows(value)],['one','two'])
        before=copy.deepcopy(value)
        with self.assertRaises(ValueError):P.apply(value,['title-seg'],P.settings({},[]))
        self.assertEqual(value,before)
    def test_empty_font_does_not_inherit_a_missing_source_path(self):
        value=draft();c=json.loads(value['materials']['texts'][0]['content']);c['styles']=[{'font':{'path':'/missing/inherited.ttf'}}];value['materials']['texts'][0]['content']=json.dumps(c)
        P.apply(value,['one'],P.settings({},[]))
        new=json.loads(value['materials']['texts'][-1]['content'])
        self.assertNotIn('/missing/inherited.ttf',json.dumps(new))
    def test_imported_srt_subtitle_track_is_supported(self):
        value=draft();value['materials']['texts'][0].update(type='text',group_id='')
        value['tracks'][0]['name']='subtitle'
        self.assertEqual(len(P.caption_rows(value)),2)

    def test_style_ranges_are_utf16_start_end_pairs(self):
        value=draft();P.apply(value,['one'],P.settings({'keyword':'เข้าใจ'},[]))
        c=json.loads(value['materials']['texts'][-1]['content'])
        ranges=[st['range'] for st in c['styles']]
        self.assertEqual(ranges,[[0,3],[3,9],[9,18]])
