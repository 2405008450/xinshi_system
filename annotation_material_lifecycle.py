"""云端每分钟清理过期暂存和已提交的删除队列；不在启动时迁移数据库。"""
import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from database import engine
from annotation_material_service import cleanup, storage_mode


def cleanup_once():
    with Session(engine) as db:
        cleanup(db)


@asynccontextmanager
async def material_lifespan(app):
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

    task = asyncio.create_task(worker()) if storage_mode() == 'local' else None
    try:
        yield
    finally:
        stop.set()
        if task:
            await task
