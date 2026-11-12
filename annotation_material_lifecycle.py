"""云端每分钟清理过期暂存和已提交的删除队列；不在启动时迁移数据库。"""
import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from database import engine
from annotation_material_service import cleanup, storage_mode
from performance_monitoring import monitor_event_loop


def cleanup_once():
    with Session(engine) as db:
        if storage_mode()=='local':cleanup(db)
        from editor_screenshot_service import cleanup as cleanup_screenshots
        cleanup_screenshots(db)


@asynccontextmanager
async def material_lifespan(app):
    from annotation_chat_ai_lifecycle import chat_ai_lifespan
    stop = asyncio.Event()

    async def worker():
        while not stop.is_set():
            try:
                await asyncio.to_thread(cleanup_once)
            except Exception:
                logging.getLogger(__name__).exception('项目资料清理失败，下一轮重试')
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(worker())
    monitor = asyncio.create_task(monitor_event_loop(stop))
    try:
        async with chat_ai_lifespan():
            yield
    finally:
        stop.set()
        if task:
            await task
        await monitor
