"""Wait for long editorial plans without blocking progress or duplicating POSTs."""
import copy
import json
import queue
import socket
import threading
import time
import urllib.error

PLAN_TIMEOUT = 300
POLL_SECONDS = 2


def request(prompt, *, progress=lambda message:None, feature='autoclip', **options):
    from . import core_engine as CE
    options=copy.deepcopy(options)
    conf=options.get('conf')
    gemini=isinstance(conf,dict) and conf.get('ai_backend')=='gemini'
    if gemini and not conf.get('gemini_api_key'):raise ValueError('กรุณาเพิ่ม Gemini API key ในแท็บ API Key ก่อน')
    label='Gemini' if gemini else 'Webhook'
    options.update(timeout=PLAN_TIMEOUT,max_retries=1,diagnostic_feature=feature)
    result=queue.Queue(maxsize=1)
    started=time.monotonic()
    progress('รอแผนจาก '+label+' · รอได้สูงสุด 5 นาที')
    def work():
        try:
            if gemini:
                selected=dict(conf)
                kwargs={k:v for k,v in options.items() if k in ('system','temperature','json_mode','max_tokens','timeout','max_retries')}
                answer=CE.call_gemini(selected['gemini_api_key'],selected.get('gemini_model','gemini-flash-latest'),prompt,conf=selected,**kwargs)
            else:answer=CE.call_webhook(prompt,**options)
            result.put((True,answer))
        except Exception as exc:result.put((False,exc))
    threading.Thread(target=CE.STATE.capture(work),name='editorial-webhook',daemon=True).start()
    while True:
        elapsed=time.monotonic()-started
        if elapsed>=PLAN_TIMEOUT:
            raise TimeoutError(label+' ยังไม่ส่งคำตอบภายใน 5 นาที · ยังไม่ได้สร้างหรือแก้โปรเจกต์จากคำขอนี้ ไม่ส่งซ้ำอัตโนมัติ เพราะเซิร์ฟเวอร์อาจยังทำงานอยู่ กรุณาตรวจสถานะผู้ให้บริการก่อนลองใหม่')
        try:ok,value=result.get(timeout=min(POLL_SECONDS,PLAN_TIMEOUT-elapsed))
        except queue.Empty:
            progress(f'รอแผนจาก {label} · ผ่านไป {int(time.monotonic()-started)} วินาที · ยังรอคำตอบจากเซิร์ฟเวอร์')
            continue
        # Cancellation is checked before a late response is accepted or stored.
        progress('ได้รับการตอบกลับจาก '+label+' · กำลังตรวจสถานะ')
        if not ok:
            cause = value.__cause__ if isinstance(value, RuntimeError) else None
            if isinstance(cause, (TimeoutError, socket.timeout)) or (isinstance(cause, urllib.error.URLError) and isinstance(cause.reason, (TimeoutError, socket.timeout))):
                raise TimeoutError(str(value)) from value
            raise value
        parsed=value
        if isinstance(value,str):
            try:parsed=json.loads(value)
            except (ValueError,TypeError):parsed=None
        if isinstance(parsed,dict) and parsed.get('error') and (set(parsed)<= {'error','message','code','status','success'} or parsed.get('success') is False):
            raise RuntimeError(label+' ส่งสถานะผิดพลาดแทนคำตอบ AI · ยังไม่ได้สร้างผล และไม่ส่งคำขอซ้ำอัตโนมัติ กรุณาตรวจบริการหรือโควตาของบัญชี')
        progress('ได้รับคำตอบ AI กำลังตรวจแผน')
        return value
