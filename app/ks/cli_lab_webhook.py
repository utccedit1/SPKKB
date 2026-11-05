"""Wait with cancellation; opt-in retries only follow explicit Gemini HTTP503."""
import copy
import json
import queue
import socket
import threading
import time
import urllib.error

PLAN_TIMEOUT = 300
POLL_SECONDS = 2


def _quota_guidance(error):
    """Classify bounded structured quota IDs; never echo provider text/IDs."""
    periods=set()
    try:
        data=json.loads(error.read(32768))
        details=(data.get('error') or {}).get('details',[])
        if isinstance(details,list):
            for detail in details[:64]:
                if not isinstance(detail,dict):continue
                violations=detail.get('violations',[])
                if not isinstance(violations,list):continue
                for violation in violations[:64]:
                    if not isinstance(violation,dict):continue
                    code=str(violation.get('quotaId',''))[:256].lower()
                    if 'perday' in code:periods.add('day')
                    if 'perminute' in code:periods.add('minute')
    except (ValueError,TypeError,AttributeError,OSError):pass
    if 'day' in periods:return 'โควตารายวันของโมเดลนี้หมด กรุณารอรอบใหม่หรือเลือกโมเดลหรือคีย์ที่ยังมีโควตาในหน้า API Key'
    if 'minute' in periods:return 'เกินอัตราคำขอต่อนาที กรุณารอก่อนเริ่มตรวจแผนที่บันทึกไว้อีกครั้ง'
    return 'เกินโควตาหรืออัตราคำขอ กรุณาตรวจโควตาใน Google AI Studio'


def request(prompt, *, progress=lambda message:None, feature='autoclip', retry_unavailable=False, **options):
    from . import core_engine as CE
    options=copy.deepcopy(options)
    conf=options.get('conf')
    gemini=isinstance(conf,dict) and conf.get('ai_backend')=='gemini'
    if gemini and not conf.get('gemini_api_key'):raise ValueError('กรุณาเพิ่ม Gemini API key ในแท็บ API Key ก่อน')
    label='Gemini' if gemini else 'Webhook'
    options.update(timeout=PLAN_TIMEOUT,max_retries=1,diagnostic_feature=feature)
    result=queue.Queue(maxsize=1)
    started=time.monotonic()
    attempts=1
    progress('รอแผนจาก '+label+' · รอได้สูงสุด 5 นาที')
    def work():
        try:
            if gemini:
                selected=dict(conf)
                kwargs={k:v for k,v in options.items() if k in ('system','temperature','json_mode','max_tokens','timeout','max_retries')}
                if selected.get('gemini_model','').startswith('gemini-3'):
                    # Shared output ceiling includes reasoning; reserve JSON space.
                    kwargs.update(thinking_level='low',max_tokens=min(65536,kwargs.get('max_tokens',2048)+2048))
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
            if (isinstance(value,(TimeoutError,socket.timeout)) or
                isinstance(value,urllib.error.URLError) and isinstance(value.reason,(TimeoutError,socket.timeout))):
                raise TimeoutError(label+' หมดเวลารอ · ไม่ส่งคำขอซ้ำ เพราะเซิร์ฟเวอร์อาจยังทำงานอยู่') from value
            if gemini and retry_unavailable is True and isinstance(value,urllib.error.HTTPError) and value.code==503 and attempts<3:
                progress('Gemini ตอบ 503 บริการไม่พร้อม · รอก่อนลองส่งใหม่ '+str(attempts)+'/2')
                time.sleep(min(2**attempts,max(0,PLAN_TIMEOUT-(time.monotonic()-started))))
                # Recheck cancellation and the original deadline before any new POST.
                progress('ตรวจสถานะก่อนลอง Gemini อีกครั้ง · '+str(attempts+1)+'/3')
                if time.monotonic()-started>=PLAN_TIMEOUT:
                    raise TimeoutError('Gemini หมดเวลารวม · ไม่ส่งคำขอเพิ่ม') from value
                attempts+=1
                threading.Thread(target=CE.STATE.capture(work),name='editorial-gemini-retry',daemon=True).start()
                continue
            cause = value.__cause__ if isinstance(value, RuntimeError) else None
            if isinstance(cause, (TimeoutError, socket.timeout)) or (isinstance(cause, urllib.error.URLError) and isinstance(cause.reason, (TimeoutError, socket.timeout))):
                raise TimeoutError(str(value)) from value
            if gemini and isinstance(value, urllib.error.HTTPError):
                guidance = {
                    400: 'คำขอไม่ถูกต้องสำหรับโมเดลนี้ กรุณาตรวจโมเดลและการตั้งค่า',
                    401: 'คีย์ไม่ผ่านการยืนยัน กรุณาตรวจ Gemini API Key ของบัญชี',
                    403: 'บัญชีหรือคีย์ไม่มีสิทธิ์เรียกโมเดลนี้ กรุณาตรวจสิทธิ์ใน Google AI Studio',
                    404: 'ไม่พบโมเดลที่เลือกหรือโมเดลนี้ใช้กับคีย์ไม่ได้ กรุณาเลือกโมเดลอื่นในหน้า API Key',
                    429: 'เกินโควตาหรืออัตราคำขอ กรุณาตรวจโควตาและการเรียกเก็บเงินใน Google AI Studio',
                    503: 'บริการยังไม่พร้อมหรือมีคำขอหนาแน่น กรุณารอหรือเลือกโมเดลอื่นในหน้า API Key',
                }.get(value.code, 'บริการตอบข้อผิดพลาด กรุณาตรวจสถานะบริการก่อนลองใหม่')
                if value.code==429:guidance=_quota_guidance(value)
                raise RuntimeError('Gemini HTTP '+str(value.code)+' · '+guidance+
                    ' · ยังไม่ได้สร้างผล '+('ลองครบ 3 ครั้งแล้ว ไม่ส่งคำขอเพิ่ม' if attempts==3 else 'ไม่ส่งคำขอซ้ำ')+' และไม่สลับไป UTCC อัตโนมัติ') from value
            raise value
        parsed=value
        if isinstance(value,str):
            try:parsed=json.loads(value)
            except (ValueError,TypeError):parsed=None
        if isinstance(parsed,dict) and parsed.get('error') and (set(parsed)<= {'error','message','code','status','success'} or parsed.get('success') is False):
            raise RuntimeError(label+' ส่งสถานะผิดพลาดแทนคำตอบ AI · ยังไม่ได้สร้างผล และไม่ส่งคำขอซ้ำอัตโนมัติ กรุณาตรวจบริการหรือโควตาของบัญชี')
        progress('ได้รับคำตอบ AI กำลังตรวจแผน')
        return value
