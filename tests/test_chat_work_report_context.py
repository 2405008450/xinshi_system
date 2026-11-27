"""工作报告入口只读取当前参与会话的项目；使用隔离数据库。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment, project
from test_discussion_search import history


def test_native_project_and_foreign_member(environment):
    from chat_project_views import work_report_context
    from models import AnnotationChatMember
    db,(owner,member,outsider)=environment
    row=project(db,owner)
    db.add(AnnotationChatMember(project_id=row.id,user_id=member.id));db.commit()
    result=work_report_context(db,member,'annotation',row.id)['project']
    assert result == dict(id=str(row.id),type='annotation',name=row.project_name,order_no=row.order_no)
    with pytest.raises(HTTPException): work_report_context(db,outsider,'annotation',row.id)


def test_discussion_context_uses_canonical_project(history):
    from chat_project_views import work_report_context
    from technical_requirement_models import TechnicalRoom
    db,actor,_,outsider,room,_=history
    assert work_report_context(db,actor,'discussion',room)==dict(project=None)
    row=project(db,actor)
    db.add(TechnicalRoom(project_id=row.id,room_id=room,created_by=actor.id,updated_by=actor.id));db.commit()
    assert work_report_context(db,actor,'discussion',room)['project']['order_no']==row.order_no
    with pytest.raises(HTTPException): work_report_context(db,outsider,'discussion',room)


def test_report_permission_is_required(history,monkeypatch):
    from routers import chat_sessions
    db,actor,_,_,room,_=history
    monkeypatch.setattr(chat_sessions,'user_has_permission',lambda *args:False)
    with pytest.raises(HTTPException) as error: chat_sessions.conversation_work_report_context('discussion',room,db,actor)
    assert error.value.status_code==403
