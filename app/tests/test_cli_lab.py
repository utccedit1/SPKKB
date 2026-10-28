import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ks import cli_lab as L, pages, core_engine as CE


class LabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.draft = self.root / 'draft_info.json'
        self.draft.write_text(json.dumps({'duration': 60000000, 'materials': {'texts': [
            {'id': 'm', 'content': json.dumps({'text': 'ประเด็นหลักของงาน'})}]},
            'tracks': [{'type': 'text', 'segments': [{'id': 's', 'material_id': 'm',
                'target_timerange': {'start': 10000000, 'duration': 20000000}}]}]}))
        self.raw = self.draft.read_bytes()
        L._plans.clear()

    def plan(self, response='{"start": 10, "end": 30, "reason": "ประเด็นครบ"}'):
        with patch.object(L.E, 'provider_config', return_value=({}, 'UTCC')), \
             patch.object(L.CE, 'api_captions', return_value={'captions': []}), \
             patch.object(L.CE, 'call_webhook', return_value=response):
            return L.handle('alice', self.root, {'action': 'plan', 'instruction': 'เลือกประเด็นหลัก'})

    def test_missing_captions_requires_capcut_without_external_work(self):
        self.draft.write_text(json.dumps({'duration': 60000000, 'tracks': [], 'materials': {'texts': []}}))
        with patch.object(L.CE, 'call_webhook') as webhook, patch.object(L, 'run_cli') as cli:
            with self.assertRaisesRegex(ValueError, 'CapCut'):
                L.handle('alice', self.root, {'action': 'plan', 'instruction': 'เลือกประเด็นหลัก'})
            webhook.assert_not_called()
            cli.assert_not_called()
        with self.assertRaises(ValueError):
            L.handle('alice', self.root, {'action': 'start', 'operation': 'transcribe'})

    def test_invalid_ai_ranges_are_rejected(self):
        for response in ('{"start":-1,"end":20}', '{"start":0,"end":61}',
                         '{"start":true,"end":2}', '{"start":0,"end":NaN}',
                         '{"start":"0; rm","end":2}'):
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.plan(response)
        self.assertEqual(self.draft.read_bytes(), self.raw)

    def test_owner_and_changed_source_rejected_before_cli(self):
        plan = self.plan()
        with patch.object(L, 'run_cli') as cli:
            with self.assertRaises(ValueError):
                L.handle('bob', self.root, {'action': 'apply', 'plan_id': plan['plan_id']})
            self.draft.write_text('{"duration":10000000}')
            with self.assertRaises(ValueError):
                L.handle('alice', self.root, {'action': 'apply', 'plan_id': plan['plan_id']})
            cli.assert_not_called()

    def test_apply_uses_frozen_copy_and_preserves_original(self):
        plan = self.plan()
        def cut(command, source, start, end, flag, output):
            self.assertNotEqual(Path(source), self.root)
            self.assertEqual((Path(source) / 'draft_info.json').read_bytes(), self.raw)
            Path(output).write_bytes(self.raw)
            return {'output': 'ok'}
        with patch.object(L, 'executable', return_value='/fake/capcut'), \
             patch('ks.capcut_session.status', return_value={'state': 'closed'}), \
             patch.object(L.CE, 'CONFIG_DIR', str(self.root / 'config')), \
             patch.object(L, 'run_cli', side_effect=cut):
            result = L.handle('alice', self.root, {'action': 'apply', 'plan_id': plan['plan_id']})
        self.assertTrue(result['ok'])
        self.assertEqual(self.draft.read_bytes(), self.raw)
        self.assertNotIn(plan['plan_id'], L._plans)

    def test_building_independent_copy_does_not_require_closing_editor(self):
        plan = self.plan()
        def cut(command, source, start, end, flag, output):
            Path(output).write_bytes(self.raw)
            return {'output': 'ok'}
        with patch('ks.capcut_session.status', return_value={'state': 'editor'}) as status, \
             patch.object(L, 'executable', return_value='/fake/capcut'), \
             patch.object(L.CE, 'CONFIG_DIR', str(self.root/'config')), \
             patch.object(L, 'run_cli', side_effect=cut):
            result=L.handle('alice', self.root, {'action': 'apply', 'plan_id': plan['plan_id']})
        status.assert_not_called()
        self.assertTrue(result['ok'])
        self.assertEqual(self.draft.read_bytes(), self.raw)

    def test_cli_passes_arguments_without_shell(self):
        with patch.object(L, 'executable', return_value='/bin/capcut'), \
             patch.object(L.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{}'
            run.return_value.stderr = ''
            L.run_cli('info', '/project with spaces')
            self.assertEqual(run.call_args.args[0], ['/bin/capcut', 'info', '/project with spaces'])
            self.assertFalse(run.call_args.kwargs['shell'])

    def test_editor_preserves_existing_tabs(self):
        html = pages.build_editor_page(CE.EDITOR_PAGE)
        for name in ('clilab', 'main', 'super', 'caps', 'event', 'hist', 'chat', 'broll', 'airoute', 'mykey', 'proofread'):
            self.assertEqual(html.count('id="tab_' + name + '"'), 1, name)

    def test_ai_receives_timestamps_without_local_paths(self):
        with patch.object(L.E, 'provider_config', return_value=({}, 'UTCC')), \
             patch.object(L.CE, 'call_webhook', return_value='{"start":10,"end":30}') as call:
            L.handle('alice', self.root, {'action': 'plan', 'instruction': 'เลือกประเด็นหลัก'})
        prompt = call.call_args.args[0]
        self.assertIn('"start": 10.0', prompt)
        self.assertIn('"end": 30.0', prompt)
        self.assertNotIn(str(self.root), prompt)
        self.assertGreaterEqual(call.call_args.kwargs['max_retries'], 1)

    def test_real_cli_cuts_text_timeline_and_preserves_original(self):
        try:
            L.executable()
        except ValueError:
            self.skipTest('capcut-cli is optional')
        draft = json.loads(self.raw)
        draft.update(fps=30, canvas_config={'width': 1080, 'height': 1920})
        draft['tracks'][0]['segments'][0]['extra_material_refs'] = []
        self.draft.write_text(json.dumps(draft))
        before = self.draft.read_bytes()
        plan = self.plan()
        with patch.object(L.CE, 'CONFIG_DIR', str(self.root / 'config')), \
             patch('ks.capcut_session.status', return_value={'state': 'closed'}):
            result = L.handle('alice', self.root, {'action': 'apply', 'plan_id': plan['plan_id']})
        output = json.loads((Path(result['destination']) / 'draft_info.json').read_text())
        self.assertEqual(output['duration'], 20000000)
        segment = output['tracks'][0]['segments'][0]
        self.assertEqual(segment['target_timerange']['start'], 0)
        self.assertEqual(segment['target_timerange']['duration'], 20000000)
        self.assertEqual(self.draft.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
