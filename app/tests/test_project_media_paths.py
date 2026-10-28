import copy,json,tempfile,unittest
from pathlib import Path
from ks.cli_lab_story import resolve_media_paths

class SavedMediaPathTests(unittest.TestCase):
    def test_saved_placeholder_resolves_to_real_project_media_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();timeline=root/'Timelines/main';timeline.mkdir(parents=True)
            media=timeline/'cli_lab_assets/clip.mp4';media.parent.mkdir();media.write_bytes(b'fixture')
            draft={'materials':{'videos':[{'path':'##_draftpath_placeholder_ABC-123_##/Timelines/main/cli_lab_assets/clip.mp4'}],'audios':[{'path':'cli_lab_assets/clip.mp4'}]}}
            before=copy.deepcopy(draft);result=resolve_media_paths(draft,timeline)
            self.assertEqual(draft,before)
            self.assertEqual(result['materials']['videos'][0]['path'],str(media))
            self.assertEqual(result['materials']['audios'][0]['path'],str(media))

    def test_missing_or_escaping_placeholder_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in ('missing.mp4','../outside.mp4'):
                with self.assertRaises(ValueError):resolve_media_paths({'materials':{'videos':[{'path':'##_draftpath_placeholder_A_##/'+value}]}},folder)
