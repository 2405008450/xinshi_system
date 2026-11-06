"""客户合作状态隔离验证；不连接业务数据库。"""
from datetime import datetime
import pytest
from uuid import uuid4
from sqlalchemy import update
from tests.test_chat_participant_access import environment
from models import Client,SubClient,TranslationProject,TranslationSubOrder
from client_cooperation_auto import ClientProjectConfirmation
import crud
from schemas import ClientResponse


@pytest.mark.parametrize('status', ['confirmed', 'in_progress', 'translator_assigned'])
def test_new_confirmed_project_inserts_parent_before_confirmation_with_real_fk(environment, status):
    """常规夹具未保留外键；这里启用真实约束，防止父项目尚未落库就插入确认记录。"""
    db, _ = environment
    owner = client(db)
    with db.bind.begin() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        ClientProjectConfirmation.__table__.drop(connection)
        ClientProjectConfirmation.__table__.create(connection)
    root = project(db, owner, 'FK-NEW', datetime(2026, 11, 6, 10, 30), status)
    evidence = db.get(ClientProjectConfirmation, root.id)
    assert evidence is not None
    assert owner.client_status == 'active'
    assert owner.cooperation_start_date == datetime(2026, 11, 6, 10, 30)
    # 后续编辑和取消复用同一条确认依据，不重复创建，也不丢失历史合作状态。
    root.project_status = 'cancelled'
    db.commit()
    assert db.query(ClientProjectConfirmation).filter_by(project_id=root.id).count() == 1
    assert ClientResponse.model_validate(crud.get_client(db, owner.id)).client_status == 'active'


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
