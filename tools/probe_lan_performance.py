"""低频只读对照：首页、数据库健康、可选的已授权列表；不保存响应正文。"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import statistics
import time

import httpx

ORIGINS = ('https://oa.xinshify.com.cn', 'https://www.oa.xinshify.com.cn')


def probe(origins, repeats, with_lists):
    token = os.getenv('LAN_PERFORMANCE_TOKEN', '')
    if with_lists and not token:
        raise SystemExit('列表采样需要在当前进程环境中设置 LAN_PERFORMANCE_TOKEN，不接受命令行凭据')
    paths = [('homepage', '/'), ('db_health', '/api/health/db')]
    if with_lists:
        paths += [('translation', '/api/projects/translation/page?limit=20'),
                  ('talents', '/api/talents/page?limit=20')]
    rows = []
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        for origin in origins:
            for name, path in paths:
                samples = []
                for _ in range(repeats):
                    started = time.perf_counter()
                    # 凭据仅发给需要授权的业务列表，不发给首页及健康探针。
                    headers = {'Authorization': 'Bearer ' + token} if name in ('translation', 'talents') else {}
                    try:
                        response = client.get(origin + path, headers=headers)
                        samples.append({'ms': round((time.perf_counter() - started) * 1000, 2),
                                        'status': response.status_code,
                                        'request_id': response.headers.get('x-request-id'),
                                        'server_timing': response.headers.get('server-timing')})
                    except httpx.HTTPError as error:
                        samples.append({'error': type(error).__name__})
                    time.sleep(1)
                successful = sorted(item['ms'] for item in samples if item.get('status') == 200)
                rows.append({'origin': origin, 'case': name, 'samples': samples,
                             'p50_ms': statistics.median(successful) if successful else None,
                             'p95_ms': successful[math.ceil(len(successful) * .95) - 1] if successful else None})
    return {'measured_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'source_host': os.getenv('COMPUTERNAME', ''), 'concurrency': 1, 'results': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origins', nargs='+', choices=ORIGINS, default=ORIGINS)
    parser.add_argument('--repeats', type=int, choices=range(1, 21), default=3)
    parser.add_argument('--with-lists', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(probe(args.origins, args.repeats, args.with_lists), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + '\n', encoding='utf-8')
    print(result)
