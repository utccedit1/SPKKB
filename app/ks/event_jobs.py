"""Owned, bounded background event jobs with progress and cancellation."""
import copy
import threading
import time
import uuid
import os
from . import event_clip as E, job_store
from . import event_timeline, caption_resegment, feature_tasks
MUTATIONS = {"apply", "restore", "resegment", "proofread_apply"} | feature_tasks.WRITES
TASKS = feature_tasks.READ_TASKS | feature_tasks.WRITES | {"chatbot", "silence", "render", "sfx_listen"}

_jobs = {}
_lock = threading.Lock()


from .job_admission import admit

@admit
def start(owner, proj, action, cfg):
    if action not in TASKS | {'analyze','plan','apply','restore','resegment','proofread','proofread_apply'}: raise ValueError('งานไม่ถูกต้อง')
    # Reject unsafe writes synchronously, before a worker or any AI request starts.
    draft_writes={'apply','restore','resegment','proofread_apply','generate','align','silence_apply','history_restore','history_checkpoint'}
    if action in draft_writes:
        event_timeline.ensure_closed(home_confirmed=cfg.get('style_only') is True and cfg.get('capcut_home_confirmed') is True)
    conf, label = ({}, 'ไม่ใช้ AI — บันทึก backup และจัดการไทม์ไลน์') if action in MUTATIONS | TASKS else E.provider_config(cfg.get('backend', 'utcc'))
    if action == 'resegment' and not cfg.get('style_only'):
        with E.CE.ai_feature('resegment'):
            conf=E.CE.load_config()
            label=E.CE.effective_ai_label('resegment')['label']
        if cfg.get('english_loanwords'):
            E.provider_config('utcc')  # Fail before starting if UTCC is not configured.
            label+=' + UTCC (คำทับศัพท์)'
    if action in TASKS:
        feature = feature_tasks.FEATURES.get(action)
        uses_ai = action in feature_tasks.READ_TASKS | {'chatbot','align','sfx_listen'} or (action == 'generate' and cfg.get('sfx_on') and cfg.get('sfx_mode') == 'ai')
        if uses_ai and feature:
            with E.CE.ai_feature(feature):
                conf = E.CE.load_config()
                label = E.CE.effective_ai_label(feature)['label']
                if action in ('align','sfx_listen'): label = 'Webhook งานเสียง' if (conf.get('audio_backend') == 'webhook' or (not (cfg.get('api_key') or conf.get('audio_api_key') or conf.get('gemini_api_key')) and conf.get('webhook_audio') and conf.get('webhook_url'))) else 'Gemini งานเสียง'
        else: label = 'ไม่ใช้ AI'
    with _lock:
        from .updater import update_manager
        if update_manager.get_status()['state'] in ('downloading','applying'): raise ValueError('กำลังอัปเดตโปรแกรม กรุณารอให้เปิดรุ่นใหม่ก่อนเริ่มงาน')
        now = time.time()
        for key in list(_jobs):
            if _jobs[key]['state'] in ('done', 'failed', 'cancelled') and now - _jobs[key]['updated'] > 3600:
                del _jobs[key]
        if any(j['owner'] == owner and j['state'] in ('queued', 'running') for j in _jobs.values()):
            raise ValueError('มีงานกำลังทำอยู่ กรุณารอหรือยกเลิกก่อน')
        if any(j.get('project') == os.path.realpath(proj) and j['state'] in ('queued', 'running') and (action in MUTATIONS or j.get('action') in MUTATIONS) for j in _jobs.values()):
            raise ValueError('โปรเจกต์นี้มีงานกำลังทำอยู่ กรุณารอจนเสร็จก่อนตัด/กู้คืน')
        if sum(j['state'] in ('queued', 'running') for j in _jobs.values()) >= 2:
            raise ValueError('ระบบกำลังทำงานเต็ม กรุณาลองภายหลัง')
        job_id = uuid.uuid4().hex
        _jobs[job_id] = dict(owner=owner, state='queued', created=now, updated=now,
                             backend=label, action=action, project=os.path.realpath(proj), completed=0, total=0, message='กำลังอ่านซับ', cancel=False)

    try:job_store.save('event',job_id,_jobs[job_id])
    except Exception:
        with _lock:_jobs.pop(job_id,None)
        raise

    def update(**values):
        with _lock:
            job = _jobs[job_id]
            if job['cancel']:
                raise InterruptedError('ยกเลิกงานแล้ว')
            if time.time() - job['created'] > 1800:
                raise TimeoutError('งานใช้เวลาเกิน 30 นาที กรุณาแบ่งโปรเจกต์เป็นช่วงสั้นลง')
            job.update(values, updated=time.time())
            job_store.save('event',job_id,job)

    def run():
        E._CONTEXT.conf = copy.deepcopy(conf)
        E._CONTEXT.progress = update
        try:
            update(state='running')
            if action in TASKS:
                from contextlib import nullcontext
                from .apply_guard import project_lock
                feature = feature_tasks.FEATURES.get(action)
                with E.CE.ai_feature(feature) if feature else nullcontext():
                    with project_lock(proj) if action in MUTATIONS else nullcontext():
                        result = feature_tasks.run(proj, action, cfg)
            else:
                from contextlib import nullcontext
                from .apply_guard import project_lock
                with project_lock(proj) if action in MUTATIONS else nullcontext():
                    from . import proofread
                    result = {'analyze': E.analyze, 'plan': E.make_plan, 'apply': event_timeline.apply, 'restore': event_timeline.restore, 'resegment': caption_resegment.run, 'proofread': proofread.scan, 'proofread_apply': proofread.apply}[action](proj, cfg)
            if isinstance(result,dict) and (result.get('error') or result.get('ok') is False): raise ValueError(result.get('error','งานไม่สำเร็จ'))
            update(state='done', result=result, message='เสร็จแล้ว')
        except Exception as exc:
            with _lock:
                job = _jobs[job_id]
                job.update(state='cancelled' if job['cancel'] else 'failed',
                           error=str(exc), updated=time.time(), message='ยกเลิกแล้ว' if job['cancel'] else 'ทำงานไม่สำเร็จ')
        finally:
            job_store.save('event',job_id,_jobs[job_id])
            E._CONTEXT.__dict__.clear()
    threading.Thread(target=E.CE.STATE.capture(run), daemon=True, name='event-'+job_id[:8]).start()
    return {'ok': True, 'job_id': job_id, 'backend': label}


def status(owner, job_id, cancel=False):
    with _lock:
        job = _jobs.get(job_id) or job_store.load(owner,'event',job_id)
        if not job or job['owner'] != owner:
            return {'ok': False, 'code':'job_not_found', 'error': 'ไม่พบงานนี้ กรุณาตรวจโปรเจกต์หรือเริ่มงานใหม่'}
        if cancel and (job.get('action') in ('apply', 'restore') or job.get('commit_started')):
            return {'ok': False, 'error': 'กำลังบันทึกไทม์ไลน์ กรุณารอจนเสร็จเพื่อไม่ให้โปรเจกต์บันทึกไม่ครบ'}
        if cancel and job['state'] in ('queued', 'running'):
            job['cancel'] = True
            job['message'] = 'กำลังยกเลิก จะหยุดก่อนนำผล AI มาใช้'
        return {'ok': True, **copy.deepcopy({k:v for k,v in job.items() if k not in ('owner', 'cancel')})}
