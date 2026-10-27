"""安排页排除状态与日期组合；隔离 SQLite，不访问业务数据库。"""
from datetime import datetime
from uuid import uuid4
import json
from test_chat_participant_access import environment
from models import TranslationProject,Client,SubClient
from crud import _apply_translation_project_filters
from routers.translation_projects import _field_filters

def test_exclusions_parent_status_aliases_and_both_date_ranges(environment):
    db,_=environment
    statuses=['confirmed','arranged','pending_confirmation','pending','completed','feedback_sent_to_client','paused','cancelled',' ARRANGED ','已安排',None]
    for index,status in enumerate(statuses):
        db.add(TranslationProject(id=uuid4(),order_no=f'TP-QA-{index}',project_name='筛选',project_status=status,
            customer_reception_time=datetime(2026,10,20,10),customer_deadline_time=datetime(2026,10,25,23,59,59)))
    db.add(TranslationProject(id=uuid4(),order_no='old',project_name='旧稿',project_status='confirmed',customer_reception_time=datetime(2026,10,1),customer_deadline_time=datetime(2026,10,24)))
    db.commit()
    filters={'excluded_project_status':{'op':'in','value':['pending_confirmation','sent_to_client','feedback_sent_to_client','paused','cancelled']},
             'customer_reception_time':{'op':'between','from':'2026-10-20','to':'2026-10-20'},
             'customer_deadline_time':{'op':'between','from':'2026-10-25','to':'2026-10-25'}}
    def query(values):
        parsed=_field_filters(json.dumps(values))
        base=db.query(TranslationProject).outerjoin(Client,TranslationProject.client_id==Client.id).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id)
        return _apply_translation_project_filters(base,field_filters=parsed)
    assert query(filters).count()==5
    filters['excluded_project_status']['value'].append('arranged')
    assert query(filters).count()==2
    del filters['excluded_project_status']
    assert query(filters).count()==11
    # 明日及以前是单边上限，不带入旧的日期下限，包含逾期项目。
    assert query({'customer_deadline_time':{'op':'between','to':'2026-10-26'}}).count()==12
