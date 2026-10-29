"""Batch duration is distinct from an individual request timeout."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ks import cli_lab as L, stock_accounts as A


class InlineThread:
    def __init__(self, target, **kwargs):self.target=target
    def start(self):self.target()


class BatchDeadlineTests(unittest.TestCase):
    def run_batch(self, operation, cancel=False):
        clock=[1000]
        def handle(owner, project, data, progress):
            clock[0]+=1900
            if cancel:next(iter(L._jobs.values()))['cancel']=True
            progress('download step still making progress')
            return {'ok':True,'inserted':20}
        with tempfile.TemporaryDirectory() as folder, patch.dict(L._jobs,{},clear=True), patch.object(L.job_store,'save'), patch.object(L.CE.STATE,'capture',side_effect=lambda f:f), patch.object(L.threading,'Thread',InlineThread), patch.object(L.time,'time',side_effect=lambda:clock[0]), patch.object(L,'handle',side_effect=handle):
            token=L.start_job('fixture-owner',folder,{'operation':operation})['job_id']
            return dict(L._jobs[token])

    def test_broll_batch_can_finish_after_thirty_minutes(self):
        job=self.run_batch('broll_only')
        self.assertEqual(job['state'],'done')
        self.assertEqual(job['result']['inserted'],20)

    def test_other_operations_keep_existing_total_guard(self):
        job=self.run_batch('plan')
        self.assertEqual(job['state'],'failed')
        self.assertIn('30',job['error'])

    def test_cancellation_still_wins_after_thirty_minutes(self):
        job=self.run_batch('broll_only',cancel=True)
        self.assertEqual(job['state'],'failed')
        self.assertIn('ยกเลิก',job['error'])

    def test_parent_stop_releases_stock_job_and_rejects_late_result(self):
        job=dict(owner='fixture-owner',provider='artlist',state='running',created=1000,request={'query':'office desk'},message='downloading')
        def stop(message):raise InterruptedError('cancelled')
        with patch.dict(A._jobs,{'fixture':job},clear=True), patch.object(A,'cached_download',return_value=None), patch.object(A,'submit',return_value='fixture'), patch.object(A.time,'time',return_value=1001), patch.object(A.job_store,'save'):
            with self.assertRaises(InterruptedError):A.wait_download('fixture-owner','artlist',{'query':'office desk'},stop)
            self.assertEqual(job['state'],'failed')
            self.assertEqual(job['error_code'],'cancelled')
            self.assertFalse(any(j['state'] in ('queued','running') for j in A._jobs.values()))

    def test_download_step_timeout_is_not_removed(self):
        job=dict(owner='fixture-owner',provider='artlist',state='running',created=1000,request={'query':'office desk'},message='downloading')
        with patch.dict(A._jobs,{'fixture':job},clear=True), patch.object(A,'cached_download',return_value=None), patch.object(A,'submit',return_value='fixture'), patch.object(A.time,'monotonic',side_effect=[0,A.JOB_TIMEOUT+1]), patch.object(A.job_store,'save'):
            with self.assertRaises(A.StockDownloadError) as caught:A.wait_download('fixture-owner','artlist',{'query':'office desk'},lambda m:None)
            self.assertEqual(caught.exception.code,'timeout')
            self.assertEqual(job['state'],'failed')

    def test_failed_broll_receipt_keeps_operation_and_structured_reasons(self):
        from ks.broll_auto import PreparationError
        summary={'attempted':0,'prepared':0,'skipped':18,'skip_reasons':{'occupied':18}}
        def failure(*args):raise PreparationError('blocked fixture',summary)
        with tempfile.TemporaryDirectory() as folder,patch.dict(L._jobs,{},clear=True),patch.object(L.job_store,'save'),patch.object(L.CE.STATE,'capture',side_effect=lambda f:f),patch.object(L.threading,'Thread',InlineThread),patch.object(L,'handle',side_effect=failure):
            token=L.start_job('fixture-owner',folder,{'operation':'broll_only'})['job_id'];job=L._jobs[token]
            self.assertEqual(job['operation'],'broll_only');self.assertEqual(job['state'],'failed');self.assertEqual(job['broll_summary'],summary)
            summary['skipped']=99;self.assertEqual(job['broll_summary']['skipped'],18)
