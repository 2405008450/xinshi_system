"""后台调度与队列独立运行，长分析不会阻挡工作日入队。"""
import asyncio
from contextlib import asynccontextmanager

from database import SessionLocal
from business_time import business_iso, business_now
from annotation_chat_ai import claim, enqueue_scheduled, logger, process, schedule_enabled, storage_available
from thoughts_ai_service import enabled


def schedule_once():
    with SessionLocal() as db:
        if storage_available(db):
            enqueue_scheduled(db, business_now())


def run_once(stopping):
    with SessionLocal() as db:
        if not storage_available(db):
            return False
        job_id = claim(db, business_now(), allow_scheduled=schedule_enabled())
    if job_id is not None:
        process(SessionLocal, job_id, stopping)
    return job_id is not None


@asynccontextmanager
async def chat_ai_lifespan():
    if not enabled():
        yield
        return
    stop = asyncio.Event()

    async def loop(callback, interval):
        while not stop.is_set():
            try:
                if await asyncio.to_thread(callback):
                    continue
            except Exception as exc:
                logger.warning('%s 标注聊天 AI 后台任务失败 (%s)', business_iso(business_now()), type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    tasks = [asyncio.create_task(loop(lambda: run_once(stop.is_set), 3))]
    if schedule_enabled():
        tasks.append(asyncio.create_task(loop(schedule_once, 60)))
    try:
        yield
    finally:
        stop.set()
        await asyncio.gather(*tasks)
