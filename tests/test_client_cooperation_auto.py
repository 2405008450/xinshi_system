"""客户合作状态隔离验证；不连接业务数据库。"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import update
from tests.test_chat_participant_access import environment
from models import Client,SubClient,TranslationProject,TranslationSubOrder
from client_cooperation_auto import ClientProjectConfirmation
import crud
from schemas import ClientResponse


def test_new_confirmed_project_inserts_parent_before_confirmation_with_foreign_keys(environment):
    from sqlalchemy import text
    db,_=environment
    owner=client(db)
    # SQLite 默认未启用外键；显式打开，覆盖 PostgreSQL 上真实失败的写入顺序。
    db.execute(text('PRAGMA foreign_keys=ON'))
    assert db.execute(text('PRAGMA foreign_keys')).scalar()==1
    row=project(db,owner,'NEW',datetime(2026,11,7,12),'confirmed')
    evidence=db.get(ClientProjectConfirmation,row.id)
    assert evidence and evidence.project_id==row.id
    assert owner.client_status=='active'


def client(db):
    row=Client(id=uuid4(),client_code='CL-AUTO',client_name='合作验证客户',client_short_name='合作客户',client_status='pending')
    db.add(row);db.commit();return row


def project(db,owner,number,received,status='pending_confirmation'):
    row=TranslationProject(id=uuid4(),order_no=f'TP-261001-{number}',project_name='合作项目',client_id=owner.id,customer_reception_time=received,project_status=status)
    db.add(row);db.commit();return row


def test_confirmation_survives_later_status_and_uses_earliest_reception(environment):
    db,_=environment;owner=client(db)
    first=project(db,owner,'001',datetime(2026,10,15,9))
    assert owner.client_status=='pending'
    first.project_status='confirmed';db.commit()
    assert owner.client_status=='active' and owner.cooperation_start_date==datetime(2026,10,15,9)
    assert db.get(ClientProjectConfirmation,first.id)
    first.project_status='cancelled';db.commit()
    assert ClientResponse.model_validate(crud.get_client(db,owner.id)).client_status=='active'
    earlier=project(db,owner,'002',datetime(2026,10,3,10),'confirmed')
    assert ClientResponse.model_validate(crud.get_client(db,owner.id)).cooperation_start_date==datetime(2026,10,3,10)
    before=owner.cooperation_start_date
    earlier.customer_reception_time=datetime(2026,10,1,8);db.commit()
    assert ClientResponse.model_validate(crud.get_client(db,owner.id)).cooperation_start_date==datetime(2026,10,1,8)


def test_existing_confirmed_projects_derive_without_read_side_writes_and_filter_consistently(environment):
    db,_=environment;owner=client(db);root=project(db,owner,'001',datetime(2026,9,12,9))
    db.execute(update(TranslationProject).where(TranslationProject.id==root.id).values(project_status='sent_to_client'));db.commit()
    value=ClientResponse.model_validate(crud.get_client(db,owner.id))
    assert value.client_status=='active' and value.cooperation_start_date==datetime(2026,9,12,9)
    assert not db.dirty and db.get(ClientProjectConfirmation,root.id) is None
    assert [row.id for row in crud.get_clients(db,client_status='active')]==[owner.id]
    assert not crud.get_clients(db,client_status='pending')
    db.refresh(owner);assert owner.client_status=='pending' and owner.cooperation_start_date is None


def test_suborder_confirmation_updates_parent_customer_and_subcustomer(environment):
    db,_=environment;owner=client(db)
    sub=SubClient(id=uuid4(),parent_client_id=owner.id,sub_client_code='SUB-AUTO',client_name='合作子客户',client_short_name='子客户',client_status='pending')
    db.add(sub);db.commit()
    root=project(db,owner,'001',datetime(2026,10,4,9));root.sub_client_id=sub.id;root.client_id=None;db.commit()
    row=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.001',sub_project_name='子订单',status='confirmed')
    db.add(row);db.commit()
    response=ClientResponse.model_validate(crud.get_client(db,owner.id))
    assert response.client_status=='active' and response.sub_clients[0].client_status=='active'
    assert response.cooperation_start_date==datetime(2026,10,4,9)


def test_cancelled_without_confirmation_does_not_invent_cooperation(environment):
    db,_=environment;owner=client(db);project(db,owner,'001',datetime(2026,10,4,9),'cancelled')
    assert ClientResponse.model_validate(crud.get_client(db,owner.id)).client_status=='pending'


def test_confirmation_rollback_does_not_leave_history(environment):
    db,_=environment;owner=client(db);root=project(db,owner,'001',datetime(2026,10,4,9))
    root.project_status='confirmed';db.flush();db.rollback()
    db.refresh(owner);assert owner.client_status=='pending'
    assert db.get(ClientProjectConfirmation,root.id) is None
