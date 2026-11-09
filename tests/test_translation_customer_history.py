"""同客户历史方向：客户隔离、时间边界及轻量分页，全部使用隔离 SQLite。"""
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import Client,SubClient,TranslationProject
from translation_customer_history import history


def test_exact_client_and_parent_client_history_date_ranges_search_exclusion(environment):
 db,users=environment
 first=Client(id=uuid4(),client_name='相同名称',client_short_name='同名');other=Client(id=uuid4(),client_name='相同名称',client_short_name='同名');db.add_all([first,other]);db.flush()
 sub=SubClient(id=uuid4(),parent_client_id=first.id,client_name='子客户',sub_client_code='SC-test');db.add(sub);db.flush()
 at=datetime(2026,11,9,12,tzinfo=timezone(timedelta(hours=8)))
 dates=[datetime(2026,11,3),datetime(2026,11,2,23,59),datetime(2026,10,11),datetime(2026,10,10),datetime(2025,11,10),datetime(2025,11,9),datetime(2026,11,10)]
 rows=[]
 for i,day in enumerate(dates):
  row=TranslationProject(id=uuid4(),order_no=f'TP-261109-{i+1:03}',project_name='测试合同.pdf',source_file_name='测试合同.pdf',client_id=first.id,language_pair='中文→英语；中文→法语',created_at=day,created_by=users[0].id);db.add(row);rows.append(row)
 # 同名的其他客户不能混入；仅通过子客户挂接的旧项目也属于该母客户。
 db.add(TranslationProject(id=uuid4(),order_no='TP-261109-990',project_name='不能混入.pdf',client_id=other.id,created_at=at.replace(tzinfo=None)))
 db.add(TranslationProject(id=uuid4(),order_no='TP-261109-991',project_name='子客户.pdf',sub_client_id=sub.id,language_pair='英语→中文',created_at=at.replace(tzinfo=None)))
 db.commit()
 assert history(db,first.id,at=at)['total']==2
 assert history(db,first.id,'month',at=at)['total']==4
 assert history(db,first.id,'year',at=at)['total']==6
 assert history(db,first.id,'all',at=at)['total']==8
 exact=history(db,first.id,keyword='pdf 法语',at=at)
 assert exact['total']==1 and exact['items'][0]['id']==str(rows[0].id)
 assert history(db,first.id,exclude_project_id=rows[0].id,at=at)['total']==1
 paged=history(db,first.id,'all',limit=2,skip=2,at=at)
 assert paged['total']==8 and len(paged['items'])==2
 assert all(row['created_at'].endswith('+08:00') for row in paged['items'])
 assert 'customer_charge_items' not in paged['items'][0]


def test_history_route_before_uuid_route():
 from routers.translation_projects import router
 paths=[route.path for route in router.routes]
 assert paths.index('/projects/translation/customer-history')<paths.index('/projects/translation/{project_id}')
