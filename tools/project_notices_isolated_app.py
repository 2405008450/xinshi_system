"""项目须知隔离验收入口，复用专用身份和静态构建托管。"""
import os
from pathlib import Path
from fastapi import HTTPException

if os.getenv('PROJECT_NOTICES_QA') != '1':
    raise RuntimeError('仅允许显式隔离验收')

from tools.notices_isolated_app import app, engine
from routers import project_notices

# 基础入口已经核对本机专用库；禁止主应用 startup 和任何业务库连接。
sql = Path('data/migrations/20261018_project_notices.sql').read_text(encoding='utf-8')
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql('TRUNCATE project_notice_attachment, project_notice_section')

static_route = app.routes.pop()
app.include_router(project_notices.router, prefix='/api')


# 列表使用固定验收记录，支持分页及定位；不会访问真实业务项目。
def fixture_project(index=1):
    return {'id': f'40000000-0000-0000-0000-{index:012d}', 'order_no': f'QA-{index:03d}',
            'project_name': f'隔离验收项目{index}', 'source_file_name': '隔离稿件',
            'project_status': 'in_progress', 'client_short_name': '隔离客户', 'sub_order_count': 0,
            'updated_at': '2026-10-09T17:18:43+08:00'}


@app.get('/api/projects/page')
@app.get('/api/projects/{module}/page')
def fixture_page(skip: int = 0, limit: int = 10):
    return {'items': [fixture_project(index + 1) for index in range(skip, min(31, skip + limit))], 'total': 31}


@app.get('/api/projects/interpretation/{project_id}')
@app.get('/api/projects/recruitment/{project_id}')
@app.get('/api/projects/translation/{project_id}')
@app.get('/api/projects/{project_id}')
def fixture_detail(project_id: str):
    suffix = project_id.rsplit('-', 1)[-1]
    return fixture_project(int(suffix)) if suffix.isdigit() else []


@app.get('/api/{path:path}')
def empty_reference_data(path: str):
    if path.startswith(('project-notices/', 'annotation-notices/')):
        raise HTTPException(404, '隔离接口不存在')
    return []


app.routes.append(static_route)
