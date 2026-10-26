"""工作报告设置和共享权限：只使用隔离内存 SQLite。"""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_chat_participant_access import environment
import work_report_access as access


def configure_user(db, user):
    user.username='williamzhao';user.full_name='赵震锋';db.commit()


def test_personal_scope_overrides_shared_rule_for_each_viewer(environment):
    db,(owner,viewer,sender)=environment
    configure_user(db,owner)
    shared=access.save_rule(db,owner,access.AccessRuleWrite(name='原共享范围',viewer_ids=[viewer.id,sender.id],senders_all=True))
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={owner.id,viewer.id,sender.id}
    personal=access.save_rule(db,owner,access.AccessRuleWrite(name='个人范围',viewer_ids=[viewer.id],sender_ids=[sender.id]))
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={sender.id}
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,sender))=={owner.id,viewer.id,sender.id}
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,owner))=={owner.id,viewer.id,sender.id}
    # 赵震锋也可以单独选择报告范围；全部沟通监督权仍由独立权限控制。
    access.save_rule(db,owner,access.AccessRuleWrite(name='赵震锋个人范围',viewer_ids=[owner.id],sender_ids=[sender.id]))
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,owner))=={sender.id}
    restricted=report(db,owner,date(2026,10,23))
    permitted=report(db,sender,date(2026,10,23))
    with pytest.raises(HTTPException):access.received_report(db,viewer,restricted.id)
    assert access.received_report(db,viewer,permitted.id)['id']==permitted.id
    # 停用专属规则后恢复共享规则，且普通人不能修改设置。
    access.save_rule(db,owner,access.AccessRuleWrite(name=personal['name'],viewer_ids=[viewer.id],sender_ids=[sender.id],revision=personal['revision'],enabled=False),personal['id'])
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={owner.id,viewer.id,sender.id}
    with pytest.raises(HTTPException):access.save_rule(db,viewer,access.AccessRuleWrite(name='非法',viewer_ids=[viewer.id],senders_all=True))


def payload(viewer, **kwargs):
    return access.AccessRuleWrite(name='测试匹配规则',viewer_ids=[viewer.id],senders_all=True,**kwargs)


def report(db, user, day, status='finalized'):
    from task_models import DailyReport, DailyReportItem
    row=DailyReport(id=uuid4(),user_id=user.id,report_date=day,status=status,finalized_at=access.now())
    row.items=[DailyReportItem(id=uuid4(),source_type='manual',task_type='非项目工作',task_name='',progress_content='隔离工作报告',duration_minutes=10,sort_order=0)]
    db.add(row);db.commit();return row


def test_only_verified_zhao_account_can_read_and_write_settings(environment):
    db,(owner,other,third)=environment
    configure_user(db,owner)
    other.username='admin';other.full_name='赵震锋';db.commit()
    assert access.can_configure(owner)
    assert not access.can_configure(other)
    for user in [other,third]:
        with pytest.raises(HTTPException) as error:access.settings(db,user)
        assert error.value.status_code==403
        with pytest.raises(HTTPException) as error:access.save_rule(db,user,payload(user))
        assert error.value.status_code==403
    data=access.settings(db,owner)
    assert data['ready'] and str(owner.id) in data['suggested_viewer_ids']
    rule=access.save_rule(db,owner,payload(third))
    assert str(owner.id) in rule['viewer_ids']
    assert access.access_context(db,third)=={'can_configure':False,'can_receive':True,'can_statistics':False,'can_supervise':False}


def test_departments_aliases_cross_membership_and_explicit_people_union(environment):
    db,(owner,viewer,sender)=environment
    from department_models import Department, DepartmentMember
    configure_user(db,owner)
    department=Department(id=uuid4(),name='研发部',aliases=['旧研发部'],revision=1)
    db.add(department);db.commit()
    sender.department='旧研发部';db.commit()
    rule=access.save_rule(db,owner,access.AccessRuleWrite(name='部门及个人',viewer_ids=[viewer.id],department_ids=[department.id],sender_ids=[viewer.id]))
    selected=access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))
    assert selected=={sender.id,viewer.id}
    sender.department=None
    db.add(DepartmentMember(department_id=department.id,user_id=sender.id,position='成员'));db.commit()
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))==selected
    # 更名和成员变动均按当前目录重新解析，不缓存旧权限。
    department.name='开发部';db.commit()
    assert sender.id in access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))
    db.query(DepartmentMember).delete();db.commit()
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={viewer.id}
    assert rule['revision']==1


def test_all_departments_differs_from_all_people_and_excludes_inactive(environment):
    db,(owner,viewer,sender)=environment
    from department_models import Department
    configure_user(db,owner)
    department=Department(id=uuid4(),name='项目部',aliases=[],revision=1);db.add(department)
    sender.department='项目部';db.commit()
    access.save_rule(db,owner,access.AccessRuleWrite(name='全部部门',viewers_all=True,all_departments=True))
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={sender.id}
    access.save_rule(db,owner,payload(viewer))
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={owner.id,viewer.id,sender.id}
    sender.is_active=False;db.commit()
    assert sender.id not in access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))
    viewer.is_deleted=True;db.commit()
    assert access.receiving_rules(db,viewer)==[]


def test_finalized_reports_only_and_revoke_detail_access(environment):
    db,(owner,viewer,sender)=environment
    configure_user(db,owner)
    rule=access.save_rule(db,owner,access.AccessRuleWrite(name='指定发送人',viewer_ids=[viewer.id],sender_ids=[sender.id]))
    shared=report(db,sender,date(2026,10,24))
    draft=report(db,sender,date(2026,10,23),'draft')
    hidden=report(db,owner,date(2026,10,24))
    result=access.received_reports(db,viewer,None,None,None,1,20)
    assert result['total']==1 and result['items'][0]['id']==shared.id
    assert result['items'][0]['finalized_at'].utcoffset().total_seconds()==28800
    assert access.received_report(db,viewer,shared.id)['items'][0]['progress_content']=='隔离工作报告'
    for identifier in [draft.id,hidden.id]:
        with pytest.raises(HTTPException) as error:access.received_report(db,viewer,identifier)
        assert error.value.status_code==404
    assert access.received_reports(db,viewer,None,None,owner.id,1,20)['total']==0
    shared.status='draft';db.commit()
    with pytest.raises(HTTPException):access.received_report(db,viewer,shared.id)
    shared.status='finalized';db.commit()
    access.save_rule(db,owner,access.AccessRuleWrite(name='停用',viewer_ids=[viewer.id],sender_ids=[sender.id],enabled=False,revision=rule['revision']),rule['id'])
    with pytest.raises(HTTPException):access.received_report(db,viewer,shared.id)
    assert access.received_reports(db,viewer,None,None,None,1,20)['total']==0


def test_revision_conflicts_invalid_scopes_and_missing_storage(environment):
    db,(owner,viewer,_)=environment
    configure_user(db,owner)
    rule=access.save_rule(db,owner,payload(viewer))
    with pytest.raises(HTTPException) as error:access.save_rule(db,owner,payload(viewer,revision=99),rule['id'])
    assert error.value.status_code==409
    for change in [{'viewer_ids':[]},{'senders_all':False},{'name':' '}]:
        with pytest.raises(ValidationError):access.AccessRuleWrite(**{**payload(viewer).model_dump(),**change})
    with pytest.raises(HTTPException):access.save_rule(db,owner,access.AccessRuleWrite(name='无效部门',viewer_ids=[viewer.id],department_ids=[uuid4()]))
    access.WorkReportAccessRule.__table__.drop(db.connection());db.commit()
    assert access.settings(db,owner)['ready'] is False
    assert access.access_context(db,viewer)['can_receive'] is False
    with pytest.raises(HTTPException) as error:access.save_rule(db,owner,payload(viewer))
    assert error.value.status_code==503


def test_api_denies_settings_to_other_users_even_if_admin(environment):
    db,(owner,viewer,_)=environment
    from routers.tasks import reports_router
    from routers.auth import get_current_user
    from database import get_db
    configure_user(db,owner)
    viewer.username='admin';db.commit()
    app=FastAPI();app.include_router(reports_router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:viewer
    with TestClient(app) as client:
        assert client.get('/daily-reports/access-settings').status_code==403
        assert client.post('/daily-reports/access-settings',json=payload(viewer).model_dump(mode='json')).status_code==403
        assert client.put(f'/daily-reports/access-settings/{uuid4()}',json=payload(viewer).model_dump(mode='json')).status_code==403
        assert client.get('/daily-reports/received').json()=={'total':0,'items':[]}


def test_migration_can_repeat_without_creating_rules():
    from sqlalchemy import create_engine, select
    from tools.apply_work_report_access_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection);apply_migration(connection)
        assert connection.execute(select(access.WorkReportAccessRule.__table__)).all()==[]
    engine.dispose()
