"""Wait for long editorial plans without blocking progress or duplicating POSTs."""
import queue
import threading
import time

PLAN_TIMEOUT = 300
POLL_SECONDS = 2


def request(prompt, *, progress=lambda message:None, feature='autoclip', **options):
    from . import core_engine as CE
    options.update(timeout=PLAN_TIMEOUT,max_retries=1,diagnostic_feature=feature)
    result=queue.Queue(maxsize=1)
    started=time.monotonic()
    progress('รอแผนจาก AI / Webhook · รอได้สูงสุด 5 นาที')
    def work():
        try:result.put((True,CE.call_webhook(prompt,**options)))
        except Exception as exc:result.put((False,exc))
    threading.Thread(target=CE.STATE.capture(work),name='editorial-webhook',daemon=True).start()
    while True:
        elapsed=time.monotonic()-started
        if elapsed>=PLAN_TIMEOUT:
            raise TimeoutError('Webhook ยังไม่ส่งคำตอบภายใน 5 นาที · ยังไม่ได้สร้างหรือแก้โปรเจกต์จากคำขอนี้ ไม่ส่งซ้ำอัตโนมัติ เพราะเซิร์ฟเวอร์อาจยังทำงานอยู่ กรุณาตรวจ Execution Monitor ของ UTCC ก่อนลองใหม่')
        try:ok,value=result.get(timeout=min(POLL_SECONDS,PLAN_TIMEOUT-elapsed))
        except queue.Empty:
            progress(f'รอแผนจาก AI / Webhook · ผ่านไป {int(time.monotonic()-started)} วินาที · ยังรอคำตอบจากเซิร์ฟเวอร์')
            continue
        # Cancellation is checked before a late response is accepted or stored.
        progress('ได้รับคำตอบ AI กำลังตรวจแผน')
        if not ok:raise value
        return value
