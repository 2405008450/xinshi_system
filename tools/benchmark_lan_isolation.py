"""本机受控并发基准：比较同步阻塞与实际截图路由的线程隔离，不连接业务库。"""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# 本工具只模拟等待；即使机器配置了真实 DATABASE_URL，也禁止使用它。
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['LOCAL_SCHEMA_MIGRATIONS_ENABLED'] = 'false'
from routers import editor_screenshots as routes


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


async def measure(concurrency, repeats, offloaded):
    completed, probes = [], []
    def slow_save(*args):
        time.sleep(.03)
        return {'id': 'synthetic-only'}
    async def read(_):
        return b'synthetic'
    async def request(arrival):
        upload = SimpleNamespace(read=read, content_type='image/png')
        if offloaded:
            await routes.upload(upload, 'business', object(), SimpleNamespace(id='test'))
        else:
            # 修改前的实际顺序：读取后直接在异步路由执行同步 save_image。
            content = await upload.read(1024)
            slow_save(None, 'test', content, upload.content_type, 'business')
        completed.append((time.perf_counter() - arrival) * 1000)
    async def probe(arrival):
        probes.append((time.perf_counter() - arrival) * 1000)
    with patch.object(routes.service, 'save_image', slow_save):
        for _ in range(repeats):
            arrival = time.perf_counter()
            tasks = [asyncio.create_task(request(arrival)) for _ in range(concurrency)]
            tasks.append(asyncio.create_task(probe(arrival)))
            await asyncio.gather(*tasks)
    return {'request_p50_ms': round(statistics.median(completed), 2),
            'request_p95_ms': round(percentile(completed, .95), 2),
            'probe_p95_ms': round(percentile(probes, .95), 2)}


async def benchmark(repeats):
    results = []
    for concurrency in (1, 10, 30):
        results.append({'concurrency': concurrency,
                        'before': await measure(concurrency, repeats, False),
                        'after': await measure(concurrency, repeats, True)})
    return {'measured_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'kind': 'synthetic; 30ms simulated database wait; not live site acceptance',
            'repeats': repeats, 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=5, choices=range(1, 11))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = json.dumps(asyncio.run(benchmark(args.repeats)), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + '\n', encoding='utf-8')
    print(output)
