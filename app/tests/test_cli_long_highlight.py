import json
import unittest
from ks.cli_long_highlight import select_context, validate_selected_cuts, clear_cache, repair_context

class LongHighlightTests(unittest.TestCase):
    def setUp(self): clear_cache()
    def rows(self):
        return [{'id':i,'start':i*5,'end':i*5+4,'text':'ประเด็น'+str(i)+' '+('ก'*1100),'sources':['fixture']} for i in range(50)]
    def test_all_chunks_are_read_and_original_ids_are_retained(self):
        calls=[]
        def ask(prompt):
            rows=json.loads(prompt.split('SOURCE_ROWS:')[1]);calls.append([r['id'] for r in rows]);return {'spans':[{'first_id':rows[min(1,len(rows)-1)]['id'],'last_id':rows[min(2,len(rows)-1)]['id']}]}
        selected=select_context(self.rows(),ask,lambda _:None,limit=10000)
        self.assertEqual([i for batch in calls for i in batch],list(range(50)))
        self.assertEqual(selected[0]['id'],0)
        self.assertLess(len(selected),50)
        self.assertTrue(all(row['text']==self.rows()[row['id']]['text'] for row in selected))
    def test_rejects_unknown_or_fabricated_ranges(self):
        with self.assertRaises(ValueError):select_context(self.rows(),lambda _: {'spans':[{'first_id':999,'last_id':1000}]},lambda _:None,limit=10000)
    def test_valid_longer_passage_keeps_entire_context(self):
        rows=self.rows()[:24]
        selected=select_context(rows,lambda _: {'spans':[{'first_id':0,'last_id':20}]},lambda _:None,limit=100000)
        self.assertEqual([r['id'] for r in selected],list(range(22)))
    def test_overlong_model_suggestion_inside_batch_is_retained_not_truncated(self):
        rows=self.rows()[:30]
        selected=select_context(rows,lambda _: {'spans':[{'first_id':2,'last_id':27}]},lambda _:None,limit=100000)
        self.assertEqual([r['id'] for r in selected],list(range(1,29)))
    def test_plan_must_not_cross_omitted_captions(self):
        validate_selected_cuts({'cuts':[{'first_id':1,'last_id':2}]},{1,2,5})
        with self.assertRaises(ValueError):validate_selected_cuts({'cuts':[{'first_id':1,'last_id':5}]},{1,2,5})
    def test_cancellation_stops_before_next_request(self):
        calls=[]
        def ask(prompt):
            rows=json.loads(prompt.split('SOURCE_ROWS:')[1]);calls.append(rows)
            return {'spans':[{'first_id':rows[0]['id'],'last_id':rows[0]['id']}]}
        def progress(message):
            if calls: raise RuntimeError('cancelled')
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            select_context(self.rows(),ask,progress,limit=10000)
        self.assertEqual(len(calls),1)
    def test_retry_reuses_only_validated_chunks_and_isolates_scope(self):
        calls=[]
        def ask(prompt):
            rows=json.loads(prompt.split('SOURCE_ROWS:')[1]);calls.append(rows[0]['id'])
            if len(calls)==2: raise TimeoutError('pending')
            return {'spans':[{'first_id':rows[0]['id'],'last_id':rows[0]['id']}]}
        with self.assertRaises(TimeoutError):
            select_context(self.rows(),ask,lambda _:None,limit=10000,cache_scope='owner-a')
        first=calls[0]
        select_context(self.rows(),ask,lambda _:None,limit=10000,cache_scope='owner-a')
        self.assertEqual(calls.count(first),1)
        select_context(self.rows(),ask,lambda _:None,limit=10000,cache_scope='owner-b')
        self.assertEqual(calls.count(first),2)
    def test_changed_brief_and_caption_never_reuse_result(self):
        calls=[]
        def ask(prompt):
            rows=json.loads(prompt.split('SOURCE_ROWS:')[1]);calls.append(rows[0]['text'])
            return {'spans':[{'first_id':rows[0]['id'],'last_id':rows[0]['id']}]}
        rows=self.rows()[:2]
        select_context(rows,ask,lambda _:None,cache_scope='owner-a',instruction='first')
        select_context(rows,ask,lambda _:None,cache_scope='owner-a',instruction='first')
        self.assertEqual(len(calls),1)
        select_context(rows,ask,lambda _:None,cache_scope='owner-a',instruction='other')
        rows[0]['text']='changed'
        select_context(rows,ask,lambda _:None,cache_scope='owner-a',instruction='first')
        self.assertEqual(len(calls),3)
    def test_cancel_at_cache_commit_does_not_save_result(self):
        calls=[]
        def ask(prompt):
            calls.append(1)
            return {'spans':[{'first_id':0,'last_id':0}]}
        def progress(message): pass
        def reject(write): raise InterruptedError('cancelled at commit')
        progress.commit_cache=reject
        with self.assertRaises(InterruptedError):
            select_context(self.rows()[:2],ask,progress,cache_scope='owner-a')
        select_context(self.rows()[:2],ask,lambda _:None,cache_scope='owner-a')
        self.assertEqual(len(calls),2)
    def test_repair_context_is_bounded_and_never_adds_unseen_captions(self):
        rows=self.rows();allowed=set(range(0,20))|set(range(30,50))
        result=repair_context({'cuts':[{'first_id':8,'last_id':10},{'first_id':32,'last_id':33}]},rows,allowed,margin=2)
        ids=[x['id'] for x in result]
        self.assertEqual(ids,[6,7,8,9,10,11,12,30,31,32,33,34,35])
        self.assertTrue(set(ids)<=allowed)
    def test_repair_context_invalid_response_falls_back(self):
        rows=self.rows()[:5];self.assertEqual(repair_context({'cuts':[{'first_id':False,'last_id':99}]},rows,set(range(5))),[])

class ParallelLongHighlightTests(unittest.TestCase):
    def setUp(self):
        clear_cache()
        self.rows = [{'id': i, 'text': 'x' * 100} for i in range(6)]

    def test_two_requests_overlap_and_keep_owner_and_original_order(self):
        import threading
        from ks import core_engine as C
        token = C.STATE._context.set(C.STATE._context.get())
        self.addCleanup(C.STATE._context.reset, token)
        C.STATE.bind('parallel-test-session', 'owner-parallel')
        both = threading.Barrier(2)
        seen = []
        def ask(prompt, report):
            rows = json.loads(prompt.split('SOURCE_ROWS:')[1])
            seen.append(C.STATE.get('_current_uid'))
            if rows[0]['id'] < 2:
                both.wait(timeout=3)
            return {'spans': [{'first_id': rows[0]['id'], 'last_id': rows[0]['id']}]}
        parent = threading.get_ident()
        def progress(_):
            self.assertEqual(threading.get_ident(), parent)
        result = select_context(self.rows, ask, progress, limit=150, max_workers=2, worker_wrapper=C.STATE.capture)
        self.assertEqual([r['id'] for r in result], list(range(6)))
        self.assertEqual(seen, ['owner-parallel'] * 6)

    def test_failure_stops_scheduling_and_does_not_wait_for_other_request(self):
        import threading
        import time
        other_started = threading.Event()
        release = threading.Event()
        calls = []
        def ask(prompt, report):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            calls.append(i)
            if i == 0:
                self.assertTrue(other_started.wait(3))
                raise TimeoutError('pending')
            other_started.set()
            release.wait(3)
            return {'spans': [{'first_id': i, 'last_id': i}]}
        start = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                select_context(self.rows, ask, lambda _: None, limit=150, cache_scope='owner', max_workers=2, worker_wrapper=lambda f: f)
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(sorted(calls), [0, 1])
        finally:
            release.set()

    def test_cancel_discards_late_results_without_caching_or_more_requests(self):
        import threading
        release = threading.Event()
        both_started = threading.Event()
        calls = []
        def ask(prompt, report):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            calls.append(i)
            if len(calls) == 2: both_started.set()
            release.wait(3)
            return {'spans': [{'first_id': i, 'last_id': i}]}
        def progress(_):
            if both_started.is_set(): raise InterruptedError('cancelled')
        try:
            with self.assertRaises(InterruptedError):
                select_context(self.rows, ask, progress, limit=150, cache_scope='owner', max_workers=2, worker_wrapper=lambda f: f)
            self.assertEqual(sorted(calls), [0, 1])
        finally:
            release.set()
        def retry(prompt):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            calls.append(i)
            return {'spans': [{'first_id': i, 'last_id': i}]}
        select_context(self.rows, retry, lambda _: None, limit=150, cache_scope='owner')
        self.assertEqual(calls.count(0), 2)
        self.assertEqual(calls.count(1), 2)

    def test_worker_progress_is_checked_before_request_and_delivered_by_parent(self):
        import threading
        calls = []
        main = threading.get_ident()
        def ask(prompt, report):
            report('before sending')
            calls.append('sent')
            return {'spans': []}
        def progress(message):
            self.assertEqual(threading.get_ident(), main)
            if message == 'before sending': raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):
            select_context(self.rows, ask, progress, limit=150, max_workers=2, worker_wrapper=lambda f: f)
        self.assertEqual(calls, [])

    def test_parallel_reuses_only_validated_results_for_same_owner(self):
        calls = []
        def ask(prompt, report):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            calls.append(i)
            return {'spans': [{'first_id': i, 'last_id': i}]}
        for scope in ('owner-a', 'owner-a', 'owner-b'):
            select_context(self.rows, ask, lambda _: None, limit=150, cache_scope=scope, max_workers=2, worker_wrapper=lambda f: f)
        self.assertEqual(sorted(calls), [0,0,1,1,2,2,3,3,4,4,5,5])

    def test_finished_batch_starts_next_without_waiting_for_slower_batch(self):
        import threading
        slow_started = threading.Event()
        next_started = threading.Event()
        release = threading.Event()
        def ask(prompt, report):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            if i == 0:
                slow_started.set()
                release.wait(3)
            elif i == 1:
                self.assertTrue(slow_started.wait(3))
            elif i == 2:
                next_started.set()
                release.set()
            return {'spans': [{'first_id': i, 'last_id': i}]}
        try:
            result = select_context(self.rows, ask, lambda _: None, limit=150, max_workers=2, worker_wrapper=lambda f: f)
            self.assertTrue(next_started.is_set())
            self.assertEqual([r['id'] for r in result], list(range(6)))
        finally:
            release.set()

    def test_progress_counts_completed_batches_when_later_batch_finishes_first(self):
        import threading
        first_started = threading.Event()
        release_first = threading.Event()
        progress_messages = []
        def ask(prompt, report):
            i = json.loads(prompt.split('SOURCE_ROWS:')[1])[0]['id']
            if i == 0:
                first_started.set()
                release_first.wait(3)
            elif i == 1:
                self.assertTrue(first_started.wait(3))
            return {'spans': [{'first_id': i, 'last_id': i}]}
        def progress(message):
            if message.startswith('ตรวจช่วงเด่นแล้ว'):
                progress_messages.append(message)
                release_first.set()
        try:
            select_context(self.rows[:2], ask, progress, limit=150, max_workers=2, worker_wrapper=lambda f: f)
            self.assertEqual(progress_messages, ['ตรวจช่วงเด่นแล้ว 1/2', 'ตรวจช่วงเด่นแล้ว 2/2'])
        finally:
            release_first.set()
