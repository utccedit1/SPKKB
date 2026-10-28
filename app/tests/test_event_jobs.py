import pathlib
import sys
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from ks import event_clip as E, event_jobs as J


class EventJobsTests(unittest.TestCase):
    def tearDown(self):
        with J._lock: J._jobs.clear()

    def test_progress_owner_and_cancel(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event()
        def analyze(proj,cfg):
            E.progress(completed=1,total=4,start=90,end=180)
            entered.set()
            release.wait(3)
            try: E.progress(completed=2)
            finally: finished.set()
            return {'ok':True}
        with patch.object(E,'provider_config',return_value=({},'Webhook UTCC')),patch.object(E,'analyze',side_effect=analyze):
            result=J.start('a','project','analyze',{})
            self.assertTrue(entered.wait(2))
            jid=result['job_id']
            self.assertFalse(J.status('b',jid)['ok'])
            self.assertEqual(J.status('a',jid)['completed'],1)
            with self.assertRaises(ValueError): J.start('a','project','analyze',{})
            self.assertIn('ยกเลิก',J.status('a',jid,cancel=True)['message'])
            release.set();self.assertTrue(finished.wait(2))
        # Completion notification occurs just before the worker catches cancellation.
        for t in threading.enumerate():
            if t.name.startswith('event-'): t.join(2)
        self.assertEqual(J.status('a',jid)['state'],'cancelled')

    def test_utcc_route_is_explicit(self):
        with patch.object(E.CE,'load_config',return_value={'ai_backend':'gemini','utcc_webhook_url':'https://example.invalid/hook','utcc_webhook_headers':{'X-Secret':'test'}}):
            conf,label=E.provider_config('utcc')
        self.assertEqual(conf['ai_backend'],'webhook')
        self.assertTrue(conf['webhook_utcc'])
        self.assertEqual(label,'Webhook UTCC')
        self.assertNotIn('example',label)

    def test_webhook_does_not_fall_back_to_gemini(self):
        E._CONTEXT.conf={'ai_backend':'webhook','webhook_utcc':True,'webhook_url':'https://example.invalid/hook'}
        try:
            with patch.object(E.CE,'call_webhook',return_value='[{"summary":"ok","keywords":[]}]') as webhook,patch.object(E.CE,'call_gemini') as gemini:
                self.assertEqual(E.ask('test')[0]['summary'],'ok')
            gemini.assert_not_called()
            self.assertEqual(webhook.call_args.kwargs['max_retries'],1)
            self.assertEqual(webhook.call_args.kwargs['timeout'],75)
        finally:E._CONTEXT.__dict__.clear()

    def test_copy_job_does_not_require_ai(self):
        with patch.object(J.event_timeline,'ensure_closed'), patch.object(E,'provider_config') as provider, patch.object(J.event_timeline,'apply',return_value={'ok':True,'project':'/test/copy'}):
            result=J.start('copy-owner','project','apply',{'source_hash':'test','segments':[[0,3]]})
            for t in threading.enumerate():
                if t.name.startswith('event-'):t.join(2)
        provider.assert_not_called()
        status=J.status('copy-owner',result['job_id'])
        self.assertEqual(status['state'],'done')
        self.assertEqual(status['result']['project'],'/test/copy')

if __name__=='__main__':unittest.main()
