import threading,time,unittest
from unittest.mock import patch
from ks import event_clip as E, cli_lab_webhook as W, core_engine as CE, ce_config as C

class EventWebhookResilience(unittest.TestCase):
 def tearDown(self):
  E._CONTEXT.__dict__.clear()
  with E._CACHE_LOCK:
   E._ANALYSIS_CACHE.clear()
   if hasattr(E,'_WINDOW_CACHE'):E._WINDOW_CACHE.clear()
 def test_event_webhook_waits_with_progress_and_sends_once(self):
  E._CONTEXT.conf={'ai_backend':'webhook','webhook_url':'https://example.invalid/test'};messages=[];E._CONTEXT.progress=lambda **kw:messages.append(kw.get('message',''))
  def delayed(*a,**k):time.sleep(.04);return '[{"summary":"one","keywords":[]}]'
  with patch.object(CE,'call_webhook',side_effect=delayed) as send,patch.object(W,'POLL_SECONDS',.01):
   self.assertEqual(E.ask('fixture')[0]['summary'],'one')
  self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.kwargs['timeout'],300);self.assertTrue(any('ผ่านไป' in m for m in messages))
 def test_retry_reuses_validated_windows_only_for_same_owner(self):
  rows=[{'id':0,'start':0,'end':2,'text':'first','speaker':None},{'id':1,'start':10,'end':12,'text':'second','speaker':None}]
  E._CONTEXT.conf={'ai_backend':'webhook','webhook_url':'https://example.invalid/test'}
  with patch.object(E,'transcript',return_value=({},rows,'digest')),patch.object(C,'get_current_uid',return_value='alice'):
   with patch.object(E,'ask',side_effect=[[{'summary':'first','keywords':[]}],TimeoutError('fixture')]) as ask:
    with self.assertRaises(TimeoutError):E.analyze('/fixture',{})
    self.assertEqual(ask.call_count,2)
   with patch.object(E,'ask',return_value=[{'summary':'second','keywords':[]}]) as ask:
    result=E.analyze('/fixture',{});self.assertEqual(ask.call_count,1);self.assertEqual([t['summary'] for t in result['topics']],['first','second'])
  with patch.object(E,'transcript',return_value=({},rows,'digest')),patch.object(C,'get_current_uid',return_value='bob'),patch.object(E,'ask',return_value=[{'summary':'bob','keywords':[]}]) as ask:
   E.analyze('/fixture',{});self.assertEqual(ask.call_count,2)
 def test_completed_windows_never_cross_ai_config_or_anonymous_context(self):
  rows=[{'id':0,'start':0,'end':2,'text':'first','speaker':None},{'id':1,'start':10,'end':12,'text':'second','speaker':None}]
  E._CONTEXT.conf={'ai_backend':'webhook','webhook_url':'https://example.invalid/one'}
  with patch.object(E,'transcript',return_value=({},rows,'digest')),patch.object(C,'get_current_uid',return_value='alice'):
   with patch.object(E,'ask',side_effect=[[{'summary':'one','keywords':[]}],TimeoutError()]):
    with self.assertRaises(TimeoutError):E.analyze('/fixture',{})
   E._CONTEXT.conf={'ai_backend':'webhook','webhook_url':'https://example.invalid/two'}
   with patch.object(E,'ask',return_value=[{'summary':'two','keywords':[]}]) as ask:E.analyze('/fixture',{});self.assertEqual(ask.call_count,2)
  with patch.object(E,'transcript',return_value=({},rows,'digest')),patch.object(C,'get_current_uid',return_value=''),patch.object(E,'ask',return_value=[{'summary':'anon','keywords':[]}]) as ask:
   E.analyze('/fixture',{});E.analyze('/fixture',{});self.assertEqual(ask.call_count,4)
 def test_cancel_discards_late_webhook_answer(self):
  E._CONTEXT.conf={'ai_backend':'webhook','webhook_url':'https://example.invalid/test'};released=threading.Event()
  def progress(**kw):
   if 'ผ่านไป' in kw.get('message',''):raise InterruptedError('cancelled')
  E._CONTEXT.progress=progress
  try:
   with patch.object(CE,'call_webhook',side_effect=lambda *a,**k:(released.wait(1) or '[{"summary":"late"}]')),patch.object(W,'POLL_SECONDS',.01):
    with self.assertRaises(InterruptedError):E.ask('fixture')
  finally:released.set()
