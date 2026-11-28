from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_project_delivery import delivery,real_mail_preview
from interpretation_models import InterpretationProjectStatusHistory
from annotation_progress_time import business_now,project_progress_datetime


def test_status_chat_and_email_only_send_saved_status_reason_in_existing_room(delivery,monkeypatch):
    import business_mail_service as mail
    from business_mail_models import BusinessMail
    from discussion_chat_models import DiscussionMessage
    db,users,projects,service=delivery
    project=projects['interpretation'];project.file_path=r'D:\旧项目资料';project.social_post_request='原来的需求文案'
    original=service.send(db,users[0],'interpretation',project.id,uuid4())
    event=InterpretationProjectStatusHistory(id=uuid4(),project_id=project.id,from_status='initial_follow_up',to_status='candidates_provided',change_note='已登记译员：测试译员（1人）',effective_on=project_progress_datetime(business_now()),changed_by=users[0].id)
    db.add(event);project.project_status='candidates_provided';db.commit()
    result=service.send(db,users[0],'interpretation',project.id,uuid4(),status_change_id=event.id)
    assert original['room_id']==result['room_id']
    body='项目状态：已提供人选（1人）\n变更原因：已登记译员：测试译员（1人）\n\n【登记时自动发送】'
    message=db.query(DiscussionMessage).order_by(DiscussionMessage.created_at.desc()).first()
    assert message.content==project.order_no+' · 项目状态更新\n\n'+body
    monkeypatch.setattr(mail,'resolve_project_sender',lambda *_:(None,{}))
    preview=real_mail_preview(db,'interpretation',project_id=project.id,current_user=users[0],source={'status_change_id':str(event.id)})
    assert preview['body']==body and not preview['missing_fields']
    assert '原来的需求文案' not in preview['body'] and '项目路径' not in preview['body']
    assert '变更原因' in preview['body_html']
    sent=BusinessMail(id=uuid4(),source_kind='project_manual',project_type='interpretation',interpretation_project_id=project.id,subject=preview['subject'],body=preview['body'],status='sent',idempotency_key=str(uuid4()),created_by=users[0].id)
    db.add(sent);db.commit()
    service.send(db,users[0],'interpretation',project.id,uuid4(),mail_id=sent.id)
    assert db.query(DiscussionMessage).order_by(DiscussionMessage.created_at.desc()).first().content==preview['subject']+'\n\n'+body
    with pytest.raises(HTTPException):service.send(db,users[0],'interpretation',project.id,uuid4(),status_change_id=uuid4())
    assert db.query(DiscussionMessage).count()==3


def test_manual_status_reason_and_response_event_use_actual_saved_history(delivery):
    import interpretation_service as service
    from interpretation_status_notice import content
    from interpretation_schemas import InterpretationProjectUpdate
    db,users,projects,_=delivery
    project=projects['interpretation']
    project.project_status='initial_follow_up';db.commit()
    # SQLite测试补齐业务表由PostgreSQL生成的UUID。
    from sqlalchemy import event
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',ids)
    updated=service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_status='in_progress',status_change_reason='项目已开始，译员已到场'),users[0].id)
    event_id=updated.status_change_id
    assert event_id
    assert '项目状态：进行中\n变更原因：项目已开始，译员已到场' in content(db,project.id,event_id)
    assert service.get_interpretation_project(db,project.id).status_change_id is None
    updated=service.update_interpretation_project_status(db,project.id,'ended',change_note='工作完成，客户已确认',changed_by=users[0].id)
    assert '变更原因：工作完成，客户已确认' in content(db,project.id,updated.status_change_id)
