"""项目发送全部使用隔离 SQLite；通知、SMTP、实时推送均模拟。"""
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, Uuid, inspect
from tests.test_chat_participant_access import environment


@pytest.fixture
def delivery(environment,monkeypatch):
    import project_delivery as service
    import business_mail_service as mail
    from business_mail_service import PROJECT_MODELS
    from models import Client
    db,users=environment
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None and isinstance(row.__table__.c.id.type,Uuid):row.id=uuid4()
    event.listen(db,'before_flush',ids)
    client=Client(id=uuid4(),client_name='测试客户',client_short_name='客户',client_code='C-TEST',manager_contact='13800001234');db.add(client)
    projects={}
    for module,prefix in [('interpretation','IP'),('annotation','AP'),('recruitment','HP')]:
        project=PROJECT_MODELS[module](id=uuid4(),order_no=prefix+'-261110-999',project_name='测试项目',client_id=client.id,created_by=users[0].id,
                                       **({'client_manager_id':users[1].id} if module!='interpretation' else {}))
        db.add(project);projects[module]=project
    db.commit()
    monkeypatch.setattr(mail,'build_preview',lambda _db,module,**kw:dict(subject=projects[module].order_no+' · 测试'+('（紧急）项目预告知：' if kw.get('emergency_notice') else ''),body='项目内容 13800001234',missing_fields=[]))
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:([users[1]],[]))
    monkeypatch.setattr('project_chat_crud._push_notifications',lambda *_:None)
    monkeypatch.setattr('discussion_chat_service.publish',lambda *_:None)
    return db,users,projects,service


@pytest.mark.parametrize('module',['interpretation','annotation','recruitment'])
def test_send_idempotent_own_folder_all_members_policy_mentions_and_private_contact(delivery,module):
    from discussion_chat_models import DiscussionMessage,DiscussionMember,DiscussionMention
    from chat_session_category_models import ChatSessionCategoryFolder
    db,users,projects,service=delivery
    key=uuid4();project=projects[module]
    first=service.send(db,users[0],module,project.id,key)
    again=service.send(db,users[0],module,project.id,key)
    assert first==again
    assert db.query(DiscussionMessage).count()==1
    message=db.query(DiscussionMessage).one()
    assert '13800001234' not in message.content and '[联系方式受限]' in message.content
    assert db.query(DiscussionMember).filter_by(room_id=message.room_id).count()==3
    assert db.query(DiscussionMention).one().user_id==users[1].id
    folder=db.get(ChatSessionCategoryFolder,message.room_id)
    assert db.get(ChatSessionCategoryFolder,UUID(folder.parent_key)).parent_key==service.ROOTS[module]
    service.send(db,users[0],module,project.id,uuid4())
    assert db.query(DiscussionMessage).count()==2
    assert len({row.room_id for row in db.query(DiscussionMessage)})==1
    with pytest.raises(HTTPException,match='发送请求标识'):
        service.send(db,users[1],module,project.id,key)


def test_missing_core_fields_block_and_emergency_keeps_validation(delivery,monkeypatch):
    import business_mail_service as mail
    from discussion_chat_models import DiscussionMessage
    db,users,projects,service=delivery
    monkeypatch.setattr(mail,'build_preview',lambda *_a,**_kw:dict(missing_fields=['项目名称']))
    for emergency in (False,True):
        with pytest.raises(HTTPException,match='项目核心信息'):
            service.send(db,users[0],'interpretation',projects['interpretation'].id,uuid4(),emergency=emergency)
    assert db.query(DiscussionMessage).count()==0


@pytest.mark.parametrize('module',['interpretation','annotation','recruitment'])
@pytest.mark.parametrize('selection',['person','all'])
def test_supplementary_audience_creates_real_mentions(delivery,module,selection):
    from discussion_chat_models import DiscussionMention
    db,users,projects,service=delivery
    audience=['all' if selection=='all' else 'user:'+str(users[2].id)]
    service.send(db,users[0],module,projects[module].id,uuid4(),audience=audience)
    assert {row.user_id for row in db.query(DiscussionMention)}=={users[1].id,users[2].id}


@pytest.mark.parametrize('module',['annotation','recruitment'])
def test_chat_does_not_require_mail_policy_or_recipients_email(delivery,module,monkeypatch):
    import business_mail_service as mail
    db,users,projects,service=delivery
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:(_ for _ in ()).throw(ValueError('邮件组未配置')))
    assert service.send(db,users[0],module,projects[module].id,uuid4())['sent']


@pytest.mark.parametrize('module',['interpretation','annotation','recruitment'])
def test_mail_link_only_after_smtp_success_full_body_and_idempotent_retry(delivery,module):
    from business_mail_models import BusinessMail
    from business_mail_service import PROJECT_FK_FIELDS
    from discussion_chat_models import DiscussionMessage
    db,users,projects,service=delivery
    body='完整邮件正文\n'*3000
    mail=BusinessMail(id=uuid4(),source_kind='project_manual',project_type=module,subject='项目邮件',body=body,status='failed',idempotency_key=str(uuid4()),created_by=users[0].id)
    setattr(mail,PROJECT_FK_FIELDS[module],projects[module].id)
    db.add(mail);db.flush();db.add(service.ProjectMailChatIntent(mail_id=mail.id));db.commit()
    service.complete_mail_intent(db,mail,users[0]);assert db.query(DiscussionMessage).count()==0
    mail.status='sent';db.commit()
    service.complete_mail_intent(db,mail,users[0]);service.complete_mail_intent(db,mail,users[0])
    assert db.query(DiscussionMessage).count()==1
    assert db.query(DiscussionMessage).one().content=='项目邮件\n\n'+body
    assert db.get(service.ProjectMailChatIntent,mail.id).error is None


def test_link_failure_is_reported_and_can_resume_without_resending_mail(delivery,monkeypatch):
    from business_mail_models import BusinessMail
    from business_mail_service import serialize_mail
    db,users,projects,service=delivery
    mail=BusinessMail(id=uuid4(),source_kind='project_manual',project_type='recruitment',recruitment_project_id=projects['recruitment'].id,subject='邮件',body='内容',status='sent',idempotency_key=str(uuid4()),created_by=users[0].id)
    db.add(mail);db.flush();db.add(service.ProjectMailChatIntent(mail_id=mail.id));db.commit()
    original=service.send
    monkeypatch.setattr(service,'send',lambda *_a,**_kw:(_ for _ in ()).throw(HTTPException(503,'暂时不可用')))
    service.complete_mail_intent(db,mail,users[0])
    assert serialize_mail(mail)['project_chat_error']=='暂时不可用'
    monkeypatch.setattr(service,'send',original)
    service.complete_mail_intent(db,mail,users[0])
    assert serialize_mail(mail)['project_chat_error'] is None and mail.status=='sent'


def test_new_tables_migration_repeatable_and_does_not_change_old_tables(delivery):
    from tools.apply_project_delivery_migration import apply_migration
    db,_,_,service=delivery
    old=set(inspect(db.connection()).get_table_names())
    for model in reversed(service.TABLES):model.__table__.drop(db.connection(),checkfirst=True)
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==old


@pytest.mark.parametrize('smtp_success',[False,True])
def test_real_mail_pipeline_persists_link_and_emergency_without_real_smtp(delivery,monkeypatch,smtp_success):
    import business_mail_service as mail_service
    from business_mail_schemas import BusinessMailSendRequest
    from discussion_chat_models import DiscussionMessage
    from tests.test_business_mail import _settings
    db,users,projects,service=delivery
    users[1].email='recipient@example.com';db.commit()
    calls=[]
    def smtp(**kwargs):
        calls.append(kwargs)
        if not smtp_success:raise RuntimeError('模拟SMTP失败')
        return SimpleNamespace(delivery_mode='test',delivery_recipient='recipient@example.test')
    monkeypatch.setattr(mail_service,'resolve_project_sender',lambda *_:(_settings(),dict(sender_mode='system',sender_name='测试',sender_email='system@example.test')))
    monkeypatch.setattr(mail_service,'send_text_email',smtp)
    payload=BusinessMailSendRequest(project_type='interpretation',project_id=projects['interpretation'].id,source_kind='project_manual',
        to_user_ids=[users[1].id],subject=projects['interpretation'].order_no+' · 项目',body='保存后发送的正文',idempotency_key=str(uuid4()),
        send_project_chat=True,emergency_notice=True,project_chat_audience=['user:'+str(users[2].id)])
    mail=mail_service.create_and_send(db,payload,users[0])
    assert db.get(service.ProjectMailChatIntent,mail.id)
    assert mail.subject.startswith(service.URGENT) and service.WARNING in mail.body
    assert mail.status==('sent' if smtp_success else 'failed')
    assert db.query(DiscussionMessage).count()==int(smtp_success)
    if smtp_success:
        from discussion_chat_models import DiscussionMention
        assert users[2].id in {row.user_id for row in db.query(DiscussionMention)}
        # 已成功的联动换账号重试，也不重复发消息或邮件。
        assert service.retry_mail_chat(mail.id,db,users[1])=={'sent':True}
        assert db.query(DiscussionMessage).count()==1 and len(calls)==1


@pytest.mark.parametrize('module',['interpretation','annotation','recruitment'])
def test_real_preview_emergency_prefix_is_scoped_to_selected_action(environment,monkeypatch,module):
    import business_mail_service as mail
    from tests.test_business_mail import _settings
    db,_=environment
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:([],[]))
    monkeypatch.setattr(mail.SmtpSettings,'from_env',lambda:_settings())
    source={'project_name':'项目','order_no':'TEST-261110-999','project_types':['translation'],'time_ranges':['2026-11-10'],
            'locations':['广州'],'language_directions':['中英'],'required_interpreter_count':1,'task_description':'任务','language_items':['中文'],
            'position_title':'岗位','headcount_min':1,'employment_start':'2026-11-10','employment_end':'2026-12-10','work_location':'广州'}
    urgent=mail.build_preview(db,module,source=source,emergency_notice=True)
    normal=mail.build_preview(db,module,source=source)
    assert urgent['subject'].startswith('（紧急）项目预告知：') and '相关资料可能尚未完善' in urgent['body']
    assert not normal['subject'].startswith('（紧急）项目预告知：') and '相关资料可能尚未完善' not in normal['body']


def test_routes_require_write_permission():
    from project_delivery import router
    app=FastAPI();app.include_router(router)
    response=TestClient(app).post(f'/project-delivery/recruitment/{uuid4()}/chat',json={'request_key':str(uuid4())})
    assert response.status_code in (401,403)
