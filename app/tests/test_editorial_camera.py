"""Camera choice must preserve source edits, shared materials and selected audio."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ks import editorial_camera as C
from ks.cli_lab_nested import audio_view


def fixture(folder):
    videos=[];tracks=[]
    for camera in ('A','B'):
        path=Path(folder)/(camera+'.mp4');path.touch()
        videos.append(dict(id=camera,path=str(path)))
        tracks.append(dict(id=camera,type='video',segments=[dict(id='child'+camera,material_id=camera,target_timerange=dict(start=0,duration=4000000),source_timerange=dict(start=0,duration=4000000))]))
    child=dict(materials=dict(videos=videos),tracks=tracks)
    segments=[dict(id='s'+str(i),material_id='parent',extra_material_refs=['nested'],target_timerange=dict(start=i*2000000,duration=2000000),source_timerange=dict(start=i*2000000,duration=2000000)) for i in range(2)]
    return dict(duration=4000000,materials=dict(videos=[dict(id='parent',multi_camera_info=dict(cur_camera_track_id='A',audio_open_track_id_list=['A']))],drafts=[dict(id='nested',draft=child)]),tracks=[dict(id='main',type='video',segments=segments)])


def observation(source,*args):
    # Shot one has a stable spacious B frame; shot two has equal A/B evidence.
    x=.08 if source['path'].endswith('B.mp4') and source['offset']<2 else .4
    return dict(complete=True,hands=[],faces=[dict(x=x,y=.2,width=.18,height=.22,confidence=.99)])


class EditorialCameraTests(unittest.TestCase):
    def test_changes_only_evidenced_shot_and_preserves_shared_material_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            draft=fixture(folder);before=copy.deepcopy(draft)
            with patch('ks.assisted_framing._observe',side_effect=observation),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(draft,folder,lambda message:None)
            self.assertEqual(draft,before)
            self.assertEqual(report['changed'],1)
            segments=out['tracks'][0]['segments']
            self.assertNotEqual(segments[0]['material_id'],'parent')
            self.assertEqual(segments[1]['material_id'],'parent')
            materials={m['id']:m for m in out['materials']['videos']}
            chosen=materials[segments[0]['material_id']]['multi_camera_info']
            self.assertEqual(chosen,dict(cur_camera_track_id='B',audio_open_track_id_list=['A']))
            self.assertEqual(materials['parent'],before['materials']['videos'][0])
            for original,updated in zip(before['tracks'][0]['segments'],segments):
                self.assertEqual({k:v for k,v in original.items() if k!='material_id'}, {k:v for k,v in updated.items() if k!='material_id'})
            for view in (audio_view(before),audio_view(out)):
                self.assertEqual({Path(m['path']).name for m in view['materials']['audios']},{'A.mp4'})

    def test_camera_review_has_timeline_intervals_and_explains_text_space(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ks.assisted_framing._observe',side_effect=observation),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(fixture(folder),folder)
        first=report['records'][0]
        self.assertEqual(first.get('interval'),[0,2])
        self.assertEqual([c.get('reason') for c in first['cameras']],['no_clear_text_lane','clear_text_lane'])
        self.assertEqual(first['cameras'][1].get('sample_times'),[.4,1,1.6])

    def test_uncertainty_reports_missing_detector_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ks.assisted_framing._observe',return_value=dict(complete=False,faces=[],hands=[])),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(fixture(folder),folder)
        self.assertEqual(report['records'][0]['cameras'][0].get('reason'),'detector_incomplete')
        self.assertEqual(report['changed'],0)

    def test_uncertain_detector_and_missing_media_keep_original(self):
        with tempfile.TemporaryDirectory() as folder:
            draft=fixture(folder)
            with patch('ks.assisted_framing._observe',return_value=dict(complete=False,faces=[],hands=[])),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(draft,folder,lambda message:None)
            self.assertEqual(out,draft);self.assertEqual(report['changed'],0)
            Path(folder,'B.mp4').unlink()
            with patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(draft,folder,lambda message:None)
            self.assertEqual(out,draft);self.assertEqual(report['changed'],0)

    def test_budget_declines_whole_input_and_never_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            draft=fixture(folder);draft['tracks'][0]['segments']*=21
            with patch('ks.assisted_framing._observe') as detector:
                out,report=C.select(draft,folder,lambda message:None)
            detector.assert_not_called();self.assertEqual(out,draft)
            self.assertEqual(report['changed'],0)

    def test_visible_hands_only_block_the_lane_they_occupy(self):
        face=dict(x=.08,y=.2,width=.18,height=.22,confidence=.99)
        safe=dict(x=.12,y=.65,width=.15,height=.2,confidence=.7)
        blocking=dict(x=.7,y=.4,width=.2,height=.3,confidence=.7)
        sample=lambda hands: [dict(complete=True,faces=[face],hands=hands) for _ in range(3)]
        self.assertIsNotNone(C._score(sample([safe])))
        self.assertGreater(C._score(sample([safe])),.6)
        self.assertEqual(C._score(sample([safe,blocking])),0)
        self.assertIsNone(C._score(sample([dict(safe,x=float('nan'))])))

    def test_native_parent_or_child_transform_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            for child in (False,True):
                draft=fixture(folder)
                segment=(draft['materials']['drafts'][0]['draft']['tracks'][1]['segments'][0]
                         if child else draft['tracks'][0]['segments'][0])
                segment['clip']=dict(scale=dict(x=1.3,y=1.3))
                with patch('ks.assisted_framing._observe',side_effect=observation),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                    out,report=C.select(draft,folder,lambda message:None)
                self.assertEqual(out,draft)
                self.assertEqual(report['changed'],0)

    def test_candidate_must_cover_whole_shot_not_only_observed_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            for spans in (((200000,1600000),), ((0,700000),(800000,3200000))):
                draft=fixture(folder)
                child=draft['materials']['drafts'][0]['draft']
                base=child['tracks'][1]['segments'][0]
                child['tracks'][1]['segments']=[]
                for start,duration in spans:
                    seg=copy.deepcopy(base)
                    seg['target_timerange']=dict(start=start,duration=duration)
                    seg['source_timerange']=dict(start=start,duration=duration)
                    child['tracks'][1]['segments'].append(seg)
                with patch('ks.assisted_framing._observe',side_effect=observation),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                    out,report=C.select(draft,folder,lambda message:None)
                self.assertEqual(out,draft)
                self.assertEqual(report['changed'],0)

    def test_nested_speed_mapped_internal_gap_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            draft=fixture(folder)
            draft['tracks'][0]['segments']=draft['tracks'][0]['segments'][:1]
            draft['duration']=2000000
            child=draft['materials']['drafts'][0]['draft']
            inner_segments=[]
            for start,duration in ((0,700000),(800000,3200000)):
                inner_segments.append(dict(material_id='leaf',target_timerange=dict(start=start,duration=duration),source_timerange=dict(start=start,duration=duration)))
            inner=dict(materials=dict(videos=[dict(id='leaf',path=str(Path(folder,'B.mp4')))]),tracks=[dict(id='D',type='video',segments=inner_segments)])
            child['materials']['drafts']=[dict(id='deep',draft=inner)]
            child['materials']['videos'][1]['multi_camera_info']=dict(cur_camera_track_id='D',audio_open_track_id_list=['D'])
            child['tracks'][1]['segments'][0].update(extra_material_refs=['deep'],speed=.5)
            with patch('ks.assisted_framing._observe',side_effect=observation),patch('ks.core_engine.ac_ffmpeg_bin',return_value='fake'):
                out,report=C.select(draft,folder,lambda message:None)
            self.assertEqual(out,draft)
            self.assertEqual(report['changed'],0)
