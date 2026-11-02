"""隔离不可中断的 SMB 调用；超时不会提前归还仍被占用的工作名额。"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import BoundedSemaphore

from fastapi import HTTPException


class BoundedFileIO:
    def __init__(self, workers=2, timeout=8.0):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='shared-file')
        self.slots = BoundedSemaphore(workers)
        self.timeout = timeout

    async def run(self, function, *args):
        if not self.slots.acquire(blocking=False):
            raise HTTPException(503, '共享目录读取繁忙，请稍后重试', headers={'Retry-After': '2'})
        try:
            future = self.executor.submit(copy_context().run, function, *args)
        except BaseException:
            self.slots.release()
            raise
        future.add_done_callback(lambda _: self.slots.release())
        pending = asyncio.wrap_future(future)
        # 超时或客户端取消后仍取走后台异常，避免未读取异常告警。
        pending.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        done, _ = await asyncio.wait({pending}, timeout=self.timeout)
        if not done:
            raise HTTPException(504, '共享目录读取超时，请检查网络或目录权限后重试')
        return pending.result()


shared_file_io = BoundedFileIO()
