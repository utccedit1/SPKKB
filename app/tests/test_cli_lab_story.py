import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ks import cli_lab as L, cli_lab_story as S


class StoryTests(unittest.TestCase):
    def setUp(self):
        # Timeline fixtures use dummy media bytes for stamps; audio decoding is exercised in test_audio_levels.
        levels=patch("ks.audio_levels.normalize_speech",return_value={});levels.start();self.addCleanup(levels.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.work = self.root/'work'; self.work.mkdir()
        self.media=self.root/'video.mp4';self.media.write_bytes(b'fixture media')
        self.captions = [{'start': i*3, 'end': (i+1)*3, 'text': text}
                         for i, text in enumerate(['Beginning', 'Main point', 'Evidence', 'Conclusion'])]
        self.raw = {'cuts': [{'first_id': 2, 'last_id': 2, 'role': 'hook'},
                            {'first_id': 0, 'last_id': 0, 'role': 'body'},
                            {'first_id': 3, 'last_id': 3, 'role': 'conclusion'}],
                    'hook': 'What makes teams work?', 'cta': 'Share your team tip', 'reason': 'Complete story'}
        self.plan = dict(S.validate(self.raw, self.captions, 8, 10), effects=True, style='bold')
        self.draft = {'id': 'source', 'duration': 12000000, 'fps': 30,
            'canvas_config': {'width': 1080, 'height': 1920},
            'materials': {'videos': [{'id': 'v', 'path': str(self.media), 'type': 'video'}], 'texts': []},
            'tracks': [{'id': 'video-track', 'type': 'video', 'segments': [{'id': 'vseg', 'material_id': 'v',
                'extra_material_refs': [], 'speed': 1, 'volume': 1,
                'clip': {'scale': {'x': .8, 'y': .8}, 'alpha': 1, 'transform': {'x': 0, 'y': 0}, 'rotation': 0},
                'source_timerange': {'start': 0, 'duration': 12000000},
                'target_timerange': {'start': 0, 'duration': 12000000}}]},
                {'id': 'caption-track', 'type': 'text', 'segments': []}]}
        for i, c in enumerate(self.captions):
            self.draft['materials']['texts'].append({'id': f'm{i}', 'type': 'subtitle',
                'content': json.dumps({'text': c['text'], 'styles': []})})
            self.draft['tracks'][1]['segments'].append({'id': f's{i}', 'material_id': f'm{i}',
                'extra_material_refs': [], 'speed': 1,
                'target_timerange': {'start': round(c['start']*1e6), 'duration': 3000000}})
        (self.root/'draft_info.json').write_text(json.dumps(self.draft))

    def cli(self):
        try: L.executable()
        except ValueError: self.skipTest('CLI optional')
        return L.run_cli

    def test_invalid_plans_refuse_overlap_ids_roles_or_duration(self):
        bad = []
        p = copy.deepcopy(self.raw);p['cuts'][1]['first_id']=2;p['cuts'][1]['last_id']=2;bad.append(p)
        p = copy.deepcopy(self.raw);p['cuts'][0]['first_id']=True;bad.append(p)
        p = copy.deepcopy(self.raw);p['cuts'][-1]['last_id']=99;bad.append(p)
        p = copy.deepcopy(self.raw);p['cuts'][0]['role']='body';bad.append(p)
        p = copy.deepcopy(self.raw);p['cta']='';bad.append(p)
        for p in bad:
            with self.subTest(plan=p), self.assertRaises(ValueError): S.validate(p, self.captions, 8, 10)
        with self.assertRaises(ValueError): S.validate(self.raw, self.captions, 30, 45)

    def test_super_quotes_must_be_grounded_in_selected_speech(self):
        raw=dict(self.raw,supers=['Evidence'])
        self.assertEqual(S.validate(raw,self.captions,8,10)['supers'],['Evidence'])
        with self.assertRaises(ValueError):S.validate(dict(self.raw,supers=['Invented claim']),self.captions,8,10)

    def test_parser_accepts_html_markdown_prose_and_nested_response(self):
        import html
        encoded=json.dumps(self.raw)
        for response in ('Here is your plan:\n```json\n'+encoded+'\n```',
                         '<pre><code>'+html.escape(encoded)+'</code></pre>',
                         {'result':{'text':encoded}}):
            self.assertEqual(S.parse(response),self.raw)
        with self.assertRaises(ValueError): S.parse('No plan available')

    def test_real_cli_preserves_editorial_order_and_media_offsets(self):
        before = (self.root/'draft_info.json').read_bytes()
        result = S.build(self.draft, self.plan['cuts'], self.work, self.cli(), lambda m: None)
        video = result['tracks'][0]['segments']
        self.assertEqual([s['source_timerange']['start'] for s in video], [6000000, 0, 9000000])
        self.assertEqual([s['target_timerange']['start'] for s in video], [0, 3000000, 6000000])
        self.assertEqual(len({s['id'] for t in result['tracks'] for s in t['segments']}), 6)
        self.assertEqual(result['duration'], 9000000)
        self.assertEqual((self.root/'draft_info.json').read_bytes(), before)

    def test_real_cli_creates_editable_overlays_styles_zoom_and_fades(self):
        cli = self.cli()
        S.build(self.draft, self.plan['cuts'], self.work, cli, lambda m: None)
        result = S.decorate(self.work, self.plan, cli, lambda m: None)
        text = [' '.join(r[3].split()) for r in L.CE.text_segments(result)]
        self.assertIn(self.plan['hook'], text);self.assertIn(self.plan['cta'], text)
        video = next(t for t in result['tracks'] if t['type']=='video')
        for index, segment in enumerate(video['segments']):
            props = {g['property_type'] for g in segment.get('common_keyframes',[])}
            self.assertIn('KFTypeScaleX', props);self.assertIn('KFTypeScaleY', props)
            self.assertTrue(all(k['curveType']=='Line' for g in segment['common_keyframes'] for k in g['keyframe_list']))
            self.assertGreaterEqual(len(segment['common_keyframes'][0]['keyframe_list']),2)
            first=next(g for g in segment['common_keyframes'] if g['property_type']=='KFTypeScaleX')['keyframe_list'][0]['values'][0]
            self.assertGreaterEqual(first,.8);self.assertLessEqual(first,.8*1.09)
            self.assertNotIn('KFTypeVolume', props)
            self.assertEqual(segment['volume'], 1)
        self.assertEqual(result['duration'], 9000000)

    def test_video_motion_uses_native_source_times_in_locked_aspect_mode(self):
        self.draft['tracks'][0]['segments'][0]['uniform_scale']={'on':True,'value':1}
        S.build(self.draft,self.plan['cuts'],self.work,self.cli(),lambda m:None)
        result=S.decorate(self.work,self.plan,self.cli(),lambda m:None)
        for segment in next(t for t in result['tracks'] if t['type']=='video')['segments']:
            groups=segment.get('common_keyframes',[])
            self.assertEqual({g['property_type'] for g in groups},{'KFTypeScaleX','KFTypeScaleY'})
            for group in groups:
                first,last=group['keyframe_list'][0],group['keyframe_list'][-1]
                self.assertEqual(first['time_offset'],segment['source_timerange']['start'])
                self.assertLess(last['time_offset'],segment['source_timerange']['start']+segment['source_timerange']['duration'])
                self.assertGreater(last['values'][0],first['values'][0])

    def test_filler_microcuts_follow_one_motion_curve_and_caption_clock(self):
        self.draft['materials']['texts']=self.draft['materials']['texts'][:1]
        self.draft['materials']['texts'][0]['content']=json.dumps({'text':'Hello um everyone','styles':[]})
        self.draft['tracks'][1]['segments']=self.draft['tracks'][1]['segments'][:1]
        words=[dict(word='Hello ',start=.1,end=.6),dict(word='um ',start=.7,end=1),dict(word='everyone',start=1.1,end=2)]
        self.draft['materials']['texts'][0]['words']={'text':[w['word'] for w in words],'start_time':[int(w['start']*1000) for w in words],'end_time':[int(w['end']*1000) for w in words]}
        (self.work/'draft_info.json').write_text(json.dumps(self.draft))
        plan=dict(self.plan,duration=12,clean_speech=True,trim_silence=False)
        result=S.decorate(self.work,plan,self.cli(),lambda m:None)
        self.assertEqual(result['duration'],11700000)
        video=next(t for t in result['tracks'] if t['type']=='video')['segments']
        self.assertEqual(len(video),2)
        def values(seg):return next(g for g in seg['common_keyframes'] if g['property_type']=='KFTypeScaleX')['keyframe_list']
        self.assertLess(abs(values(video[0])[-1]['values'][0]-values(video[1])[0]['values'][0]),.001)
        self.assertEqual(values(video[1])[0]['time_offset'],1000000)
        self.assertFalse(any('_speech_motion' in seg for t in result['tracks'] for seg in t['segments']))
        spoken=[r[3] for r in L.CE.text_segments(result) if r[1]['material_id'] not in {s['material_id'] for t in result['tracks'] if str(t.get('name','')).startswith('ช่วยด้วยจ้า ·') for s in t['segments']}]
        self.assertNotIn('um',' '.join(spoken));self.assertIn('everyone',' '.join(spoken))

    def test_story_api_validates_and_cuts_with_reviewed_text(self):
        cfg = dict(action='plan', mode='story', instruction='Make a story', min_seconds=8, max_seconds=10, clean_speech=False)
        with patch.object(L.E,'provider_config',return_value=({},'UTCC')), \
             patch.object(L.CE,'call_webhook',return_value=json.dumps(self.raw)):
            plan = L.handle('owner',self.root,cfg)
        self.assertEqual(plan['mode'],'story');self.assertEqual(len(plan['cuts']),3)
        with patch('ks.capcut_session.status',return_value={'state':'closed'}), \
             patch.object(L.CE,'CONFIG_DIR',str(self.root/'config')):
            result = L.handle('owner',self.root,dict(action='apply',plan_id=plan['plan_id'],hook='Reviewed headline',cta='Follow for more'))
        output = Path(result['destination'])
        d = json.loads((output/'draft_info.json').read_text())
        self.assertIn('Reviewed headline',[r[3] for r in L.CE.text_segments(d)])
        self.assertTrue((output/'edit_plan.json').is_file())
        self.assertEqual(d['duration'],9000000)

    def test_duration_retry_receives_exact_computed_budget(self):
        bad=copy.deepcopy(self.raw);bad['cuts'][1]['last_id']=1
        cfg=dict(action='plan',mode='story',instruction='Make a story',min_seconds=8,max_seconds=10,clean_speech=False)
        with patch.object(L.E,'provider_config',return_value=({},'UTCC')), patch.object(L.CE,'call_webhook',side_effect=[bad,self.raw]) as webhook:
            result=L.handle('owner',self.root,cfg)
        self.assertEqual(result['duration'],9)
        self.assertIn('"actual_total_seconds": 12',webhook.call_args_list[1].args[0])

    def test_stock_retry_cannot_change_approved_story(self):
        from ks import stock_project
        bad=dict(self.raw,stock_requests=[dict(kind='broll',query='office documents',required_terms=['university'],first_id=0)])
        repaired=copy.deepcopy(bad);repaired['stock_requests'][0]['required_terms']=['documents']
        repaired['cuts']=[dict(first_id=0,last_id=3,role='body')]  # ignored: story was already approved
        cfg=dict(action='plan',mode='story',instruction='Make a story',min_seconds=8,max_seconds=10,clean_speech=False,auto_stock=True)
        with patch.object(S,'preflight'),patch.object(stock_project,'settings',return_value={'destination':str(self.root/'media')}),patch.object(L.E,'provider_config',return_value=({},'UTCC')),patch.object(L.CE,'call_webhook',side_effect=[bad,repaired]) as webhook:
            result=L.handle('owner',self.root,cfg)
        self.assertEqual(result['duration'],9)
        self.assertEqual([c['first_id'] for c in result['cuts']],[2,0,3])
        self.assertEqual(result['stock_requests'][0]['required_terms'],['documents'])
        self.assertIn('APPROVED',webhook.call_args_list[1].args[0])

    def test_failed_decoration_never_publishes_output(self):
        token='fail'
        path,digest,_=L.snapshot(self.root)
        L._plans[token]=dict(self.plan,owner='owner',project=str(path),digest=digest,mode='story',created=__import__('time').time())
        with patch('ks.capcut_session.status',return_value={'state':'closed'}), \
             patch.object(L.CE,'CONFIG_DIR',str(self.root/'config')), \
             patch.object(S,'decorate',side_effect=ValueError('effect failed')):
            with self.assertRaisesRegex(ValueError,'effect failed'):
                L.handle('owner',self.root,dict(action='apply',plan_id=token))
        self.assertFalse((self.root/'config/cli_lab_outputs').exists())
        self.assertIn(token,L._plans)

    def test_asset_change_is_rejected(self):
        media=self.root/'music.wav';media.write_bytes(b'fixture')
        selected=S.assets(self.root,{'music':str(media)})
        S.check_assets({'assets':selected})
        media.write_bytes(b'changed')
        with self.assertRaises(ValueError):S.check_assets({'assets':selected})

    def test_source_changed_during_edit_is_not_published(self):
        path,digest,_=L.snapshot(self.root)
        token='concurrent-source'
        L._plans[token]=dict(self.plan,owner='owner',project=str(path),digest=digest,mode='story',created=__import__('time').time())
        def changed(*args,**kwargs):
            (self.root/'draft_info.json').write_text('{}')
        with patch.object(L.CE,'CONFIG_DIR',str(self.root/'config')),patch.object(S,'decorate',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'ต้นฉบับเปลี่ยน'):
                L.handle('owner',self.root,dict(action='apply',plan_id=token))
        self.assertFalse((self.root/'config/cli_lab_outputs').exists())

    def test_real_cli_adds_optional_broll_and_quiet_music(self):
        import struct, zlib, wave
        def chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        image=self.root/'broll.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,2,0,0,0))+
                          chunk(b'IDAT',zlib.compress((b'\0'+b'\0\0\xff'*32)*32))+chunk(b'IEND',b''))
        music=self.root/'music.wav'
        with wave.open(str(music),'wb') as out:
            out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(__import__('array').array('h',[round(4000*__import__('math').sin(2*__import__('math').pi*440*i/16000)) for i in range(64000)]).tobytes())
        self.draft['materials']['videos'][0]['has_audio']=False
        cli=self.cli()
        S.build(self.draft,self.plan['cuts'],self.work,cli,lambda m:None)
        plan=dict(self.plan,effects=False,style_captions=False,
                  assets=S.assets(self.root,{'broll':str(image),'music':str(music)}))
        result=S.decorate(self.work,plan,cli,lambda m:None)
        broll=next(t for t in result['tracks'] if t.get('name')=='ช่วยด้วยจ้า · B-roll')
        audio=next(t for t in result['tracks'] if t.get('name')=='ช่วยด้วยจ้า · Music')
        self.assertEqual(broll['segments'][0]['volume'],0)
        self.assertEqual(broll['segments'][0]['target_timerange']['start'],2600000)  # cover the edit at 3s
        self.assertEqual(audio['segments'][0]['volume'],1.0)
        self.assertTrue(list((self.work/'assets/stock_prepared').glob('music_level_*.wav')))
        self.assertTrue(result['materials']['audio_fades'])
        destination=S.publish(self.work,result,self.root/'outputs',plan)
        published=json.loads((destination/'draft_info.json').read_text())
        music_id=audio['segments'][0]['material_id']
        material=next(m for m in published['materials']['audios'] if m['id']==music_id)
        self.assertTrue(Path(material['path']).is_file())
        self.assertTrue(Path(material['path']).is_relative_to(destination))



    def test_refresh_accepts_stock_only_webhook_and_preserves_existing_video(self):
        from ks import cli_lab_enhance as H,stock_accounts as A,cli_lab_alignment as alignment,stock_project as storage
        original=copy.deepcopy(self.draft)
        for material in original['materials']['texts']:material['content']=json.dumps({'text':'ข้อความยาวมากที่ต้องแบ่งซับให้สั้นและอ่านง่ายขึ้นบรรทัดเดียว','styles':[]})
        (self.root/'draft_info.json').write_text(json.dumps(original))
        reply={'output':'```json\n'+json.dumps({'stock_requests':[dict(kind='broll',first_id=2,query='paper desk',required_terms=['paper'])]})+'\n```'}
        from ks import core_engine as CE,event_clip as E
        with patch.object(A,'ensure_ready'),patch.object(A,'wait_download',return_value=None),patch.object(E,'provider_config',return_value=({},None)),patch.object(CE,'call_webhook',side_effect=[{'stock_requests':[dict(kind='broll',first_id=2,query='paper desk',required_terms=['AI'])]},reply]),patch.object(CE,'CONFIG_DIR',str(self.root/'config')),patch.object(alignment,'align_existing',return_value={}),patch.object(storage,'settings',return_value={'destination':str(self.root/'media')}):
            result=H.enhance('owner',self.root,{'auto_stock':True},lambda message:None,L.run_cli)
        edited=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        self.assertEqual(edited['tracks'][0],original['tracks'][0])
        self.assertEqual(edited['duration'],original['duration'])
        self.assertEqual(json.loads((self.root/'draft_info.json').read_bytes()),original)
        from ks.caption_roles import speech_rows
        self.assertTrue(all('\n' not in text for *_,text in speech_rows(edited)))
        self.assertIn('0',result['output'])
