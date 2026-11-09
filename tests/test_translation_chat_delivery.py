"""笔译会话发送：隔离 SQLite，禁用真实推送和邮件。"""
from datetime import datetime,date
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import event,Uuid
from tests.test_chat_participant_access import environment


@pytest.fixture
def chat_case(environment,monkeypatch):
    import translation_chat_delivery as service
    import business_mail_service as mail
    from tests.test_business_mail import _settings
    from models import AppUser,TranslationProject
    db,users=environment
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None and isinstance(row.__table__.c.id.type,Uuid):row.id=uuid4()
    event.listen(db,'before_flush',ids)
    staff=[AppUser(id=uuid4(),username=name,full_name=label,password_hash='disabled',is_active=True,is_deleted=False) for name,label in [('shaofei','少妃'),('thomas','Thomas'),('menghua','孟花'),('lixian','李娴')]]
    db.add_all(staff)
    root=TranslationProject(id=uuid4(),order_no='TP-261108-997',project_name='测试.docx',source_file_name='测试.docx',service_content='翻译',language_pair='中文→英语',created_by=users[0].id)
    db.add(root);db.commit()
    monkeypatch.setattr(service,'business_now',lambda:datetime(2026,11,9,11,tzinfo=ZoneInfo('Asia/Shanghai')))
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:([],[]))
    monkeypatch.setattr(mail.SmtpSettings,'from_env',lambda:_settings())
    monkeypatch.setattr('project_chat_crud._push_notifications',lambda *_:None)
    monkeypatch.setattr('discussion_chat_service.publish',lambda *_:None)
    return db,users[0],staff,root,service


def test_date_folder_full_title_all_members_idempotency_and_resending(chat_case):
    from discussion_chat_models import DiscussionMember,DiscussionMessage,DiscussionMention
    from chat_session_category_models import ChatSessionCategoryFolder
    db,actor,staff,root,service=chat_case
    first_key=uuid4()
    result=service.send(db,actor,root.id,first_key)
    room=db.get(service.TranslationProjectConversation,(root.id,date(2026,11,9)))
    assert room.title=='TP-261108-997 · 未填写客户 · 测试.docx'
    assert db.get(ChatSessionCategoryFolder,room.folder_id).parent_key==service.ROOT
    assert service.aliases(db)[str(room.folder_id)]=='261109'
    assert db.query(DiscussionMember).filter_by(room_id=room.room_id).count()==7
    mentions=db.query(DiscussionMention).all()
    assert [row.user_id for row in mentions]==[staff[0].id]
    assert db.query(DiscussionMessage).count()==1 and result['chat_count']==1
    again=service.send(db,actor,root.id,first_key)
    assert again['chat_count']==1
    new=service.send(db,actor,root.id,uuid4(),['all'])
    assert new['chat_count']==2 and db.query(DiscussionMessage).count()==2
    assert db.query(DiscussionMention).filter_by(is_all=True).count()==6
    assert db.query(service.TranslationProjectConversation).count()==1


def test_draft_without_aggregate_blocks_chat_and_mail_but_emergency_can_preview(chat_case):
    from fastapi import HTTPException
    from translation_project_submission import apply
    from discussion_chat_models import DiscussionMessage
    import business_mail_service as mail
    db,actor,staff,root,service=chat_case
    apply(db,root,'draft',True)
    db.commit()
    with pytest.raises(HTTPException,match='汇总至母订单'):
        service.send(db,actor,root.id,uuid4())
    assert db.query(DiscussionMessage).count()==0
    preview=mail.build_preview(db,'translation',project_id=root.id)
    assert any('汇总至母订单' in message for message in preview['blocking_reasons'])
    apply(db,root,'emergency_notice')
    db.commit()
    preview=mail.build_preview(db,'translation',project_id=root.id)
    assert preview['subject'].startswith('（紧急）项目预告知：')


def test_leave_backup_and_published_sunday_duty(chat_case,monkeypatch):
    from weekend_duty_management import WeekendDutyPublication
    db,actor,staff,root,service=chat_case
    config=service.defaults(db)
    monkeypatch.setattr('leave_service.get_active_leave',lambda db,uid,at=None:object() if uid==staff[0].id else None)
    people,warnings=service.recipients(db,config,datetime(2026,11,9,11,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert [person.id for person in people]==[staff[1].id] and not warnings
    db.add(WeekendDutyPublication(month=date(2026,11,1),assignments=[{'user_id':str(staff[3].id),'date':'2026-11-08','department':'project'}],revision=1,draft_revision=1,published_by=actor.id))
    db.commit()
    people,warnings=service.recipients(db,config,datetime(2026,11,8,11,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert [person.id for person in people]==[staff[3].id] and not warnings
    people,warnings=service.recipients(db,config,datetime(2026,11,15,11,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert not people and warnings


def test_full_email_body_is_preserved_and_failed_mail_never_dispatches(chat_case):
    from business_mail_models import BusinessMail
    from discussion_chat_models import DiscussionMessage
    db,actor,staff,root,service=chat_case
    body='长邮件内容\n'*3000
    mail=BusinessMail(id=uuid4(),source_kind='project_manual',project_type='translation',translation_project_id=root.id,subject='测试主题',body=body,status='sent',idempotency_key=str(uuid4()),created_by=actor.id)
    db.add(mail);db.flush()
    db.add(service.TranslationMailChatIntent(mail_id=mail.id,audience=[]));db.commit()
    service.complete_mail_intent(db,mail,actor)
    assert db.query(DiscussionMessage).one().content=='测试主题\n\n'+body
    service.complete_mail_intent(db,mail,actor)
    assert db.query(DiscussionMessage).count()==1
    mail.status='failed';db.commit()
    service.complete_mail_intent(db,mail,actor)
    assert db.query(DiscussionMessage).count()==1


def test_settings_validation_permission_and_department_order(chat_case,monkeypatch):
    from department_models import Department
    from routers.translation_delivery import SettingsWrite
    db,actor,staff,root,service=chat_case
    db.add_all([Department(id=uuid4(),name='HR部',aliases=[]),Department(id=uuid4(),name='笔译项目部',aliases=[])]);db.commit()
    monkeypatch.setattr(service,'can_manage',lambda *_:True)
    catalog=service.catalog(db,actor)
    assert [item['label'] for item in catalog['audience'][:2]]==['全体','笔译项目部']
    updated=service.save_settings(db,actor,SettingsWrite(revision=0,**catalog['settings']))
    assert updated['revision']==1
    from fastapi import HTTPException
    with pytest.raises(HTTPException):service.save_settings(db,actor,SettingsWrite(revision=0,**catalog['settings']))


def test_migration_only_adds_new_tables_and_is_repeatable():
    from sqlalchemy import create_engine,inspect
    from tools.apply_translation_chat_delivery_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'translation_chat_config','translation_project_conversation','translation_chat_dispatch','translation_mail_chat_intent'}
