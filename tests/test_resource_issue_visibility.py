"""总结查看范围：内存隔离数据库，不连接业务库。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment


def issue(db, owner, **summary):
    from resource_issue_models import DevelopmentIssue
    row=DevelopmentIssue(id=uuid4(),category='problem',content='权限测试',remarks='',summary_data=summary,
        source_type='manual',source_title='测试',source_content='',proposer_id=owner.id,proposer_name=owner.username,
        collected_by=owner.id,collected_by_name=owner.username,updated_by=owner.id)
    db.add(row);db.flush()
    return row


def test_all_selected_departments_legacy_and_management(environment,monkeypatch):
    db,(owner,member,other)=environment
    import resource_issue_service as service
    from department_models import Department,DepartmentMember
    monkeypatch.setattr(service,'can_delegate',lambda db,u:False)
    legacy=issue(db,owner)
    public=issue(db,owner,view_all=True)
    selected=issue(db,owner,view_all=False,view_user_ids=[str(member.id)])
    private=issue(db,owner,view_all=False,view_user_ids=[])
    dept=Department(id=uuid4(),name='测试多部门',aliases=['旧测试部门'],revision=1)
    db.add(dept);db.flush()
    grouped=issue(db,owner,view_all=False,view_department_ids=[str(dept.id)])
    assert {r.id for r in service.visible_query(db,other)}=={public.id}
    assert {r.id for r in service.visible_query(db,member)}=={public.id,selected.id}
    db.add(DepartmentMember(department_id=dept.id,user_id=member.id));db.flush()
    assert grouped.id in {r.id for r in service.visible_query(db,member)}
    other.department='旧测试部门';db.flush()
    assert grouped.id in {r.id for r in service.visible_query(db,other)}
    db.query(DepartmentMember).delete();db.flush()
    assert grouped.id not in {r.id for r in service.visible_query(db,member)}
    assert {r.id for r in service.visible_query(db,owner)}=={legacy.id,public.id,selected.id,private.id,grouped.id}
    with pytest.raises(HTTPException) as denied:service.get_issue(db,other,selected.id)
    assert denied.value.status_code==404
    monkeypatch.setattr(service,'can_delegate',lambda db,u:True)
    assert service.get_issue(db,other,private.id).id==private.id


def test_notification_must_be_visible_and_old_clients_preserve_scope(environment,monkeypatch):
    db,(owner,member,other)=environment
    import resource_summary_service as summary
    from resource_issue_schemas import SummaryFields
    row=issue(db,owner,view_all=False,view_user_ids=[str(member.id)],view_department_ids=[])
    summary.write_summary(db,row,SummaryFields(specific_classification='兼容旧客户端'))
    assert row.summary_data['view_all'] is False
    assert row.summary_data['view_user_ids']==[str(member.id)]
    with pytest.raises(HTTPException) as denied:
        summary.write_summary(db,row,SummaryFields(view_all=False,view_user_ids=[member.id],notify_user_ids=[other.id]))
    assert denied.value.status_code==422
    assert row.summary_data['view_user_ids']==[str(member.id)]
    calls=[]
    import crud
    monkeypatch.setattr(crud,'create_notifications_for_users',lambda db,ids,*args,**kw:calls.append(set(ids)) or [])
    summary.write_summary(db,row,SummaryFields(view_all=False,view_user_ids=[member.id],notify_user_ids=[member.id]))
    assert calls==[{member.id}]
    with pytest.raises(HTTPException):summary.write_summary(db,row,SummaryFields(view_all=False,view_user_ids=[uuid4()]))
