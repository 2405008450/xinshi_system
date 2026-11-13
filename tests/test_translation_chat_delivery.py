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


def test_project_supplementary_notes_after_order_number_before_project_type_in_mail_and_chat(chat_case):
    import business_mail_service as mail
    from discussion_chat_models import DiscussionMessage
    db,actor,staff,root,service=chat_case
    root.customer_requirement_professional='专业要求测试'
    root.customer_requirement_special='特殊要求测试'
    root.remarks='补充说明第一行\n补充说明第二行'
    db.commit()
    preview=mail.build_preview(db,'translation',project_id=root.id,current_user=actor,source={'sub_order_hierarchy':[{'level':1,'orders':2,'files':2}]})
    body=preview['body']
    assert '补充说明：\n补充说明第一行\n补充说明第二行' in body
    assert body.index('订单号：')<body.index('补充说明：')<body.index('项目类型：')
    assert body.count('补充说明：')==1
    assert '补充说明第一行' in preview['body_html'] and '补充说明第二行' in preview['body_html']
    assert '备注：' not in body
    service.send(db,actor,root.id,uuid4())
    message=db.query(DiscussionMessage).one()
    assert '补充说明：\n补充说明第一行\n补充说明第二行' in message.content
    assert message.content.index('订单号：')<message.content.index('补充说明：')<message.content.index('项目类型：')
    root.remarks='  '
    db.commit()
    assert '补充说明：' not in mail.build_preview(db,'translation',project_id=root.id,current_user=actor)['body']


@pytest.mark.parametrize('option,actual,expected', [
    (None, [], 'CNY 0.00'),
    ('full', [50], 'CNY 150.00'),
    ('deposit', [20.10, 30.20], 'CNY 50.30'),
    ('deposit', [None], '待完善'),
    ('deposit', [20, None], 'CNY 20.00（部分付款明细待完善）'),
])
def test_saved_path_and_finance_are_shared_by_mail_and_chat(chat_case, option, actual, expected):
    import json
    import business_mail_service as mail
    from models import ProjectFile, TranslationSubOrderChargeItem, FinanceRecord, FinancePayment
    from translation_payment_confirmation import TranslationPaymentConfirmation
    from discussion_chat_models import DiscussionMessage
    db, actor, staff, root, service = chat_case
    path = r'\\Win-server\项目\中文合同<&>\原文.docx'
    db.add(ProjectFile(translation_project_id=root.id, file_name='路径组', storage_path=path))
    db.add(TranslationSubOrderChargeItem(translation_project_id=root.id, sequence_no=1,
        item_name='翻译费', pricing_mode='fixed', currency='CNY', total_excl_tax=150))
    if option:
        db.add(TranslationPaymentConfirmation(project_id=root.id, is_paid=True,
            payment_option=json.dumps({'type': option, 'full_payment': {'amount': '150.00', 'currency': 'CNY'}})))
    if actual:
        record = FinanceRecord(project_id=root.id)
        db.add(record); db.flush()
        for index, value in enumerate(actual):
            db.add(FinancePayment(finance_id=record.id, stage_type='deposit' if index == 0 else 'mid',
                stage_no=index+1, planned_amount=999, actual_amount=value))
    db.commit()
    preview = mail.build_preview(db, 'translation', project_id=root.id, current_user=actor)
    expected_lines = [f'母订单原文路径：{path}', '项目金额：CNY 150.00（不含税）', f'已付款金额：{expected}']
    for line in expected_lines:
        assert line in preview['body']
    assert '中文合同&lt;&amp;&gt;' in preview['body_html']
    service.send(db, actor, root.id, uuid4())
    message = db.query(DiscussionMessage).one()
    for line in expected_lines:
        assert line in message.content


def test_missing_path_and_price_do_not_add_send_requirements(chat_case):
    import business_mail_service as mail
    db, actor, staff, root, service = chat_case
    preview = mail.build_preview(db, 'translation', project_id=root.id, current_user=actor)
    assert '母订单原文路径：-' in preview['body']
    assert '项目金额：待完善' in preview['body']
    assert not preview['missing_fields']


def test_notification_uses_child_rollup_and_separates_currencies(chat_case):
    import business_mail_service as mail
    from models import TranslationSubOrder, TranslationSubOrderChargeItem
    from translation_project_submission import apply
    db, actor, staff, root, service = chat_case
    for index, currency, excl, incl in [(1, 'CNY', 150, None), (2, 'USD', None, 25)]:
        child = TranslationSubOrder(parent_project_id=root.id,
            sub_order_no=f'{root.order_no}.{index:03}', sub_project_name=f'文件{index}.docx',
            language_pair=root.language_pair)
        db.add(child); db.flush()
        db.add(TranslationSubOrderChargeItem(sub_order_id=child.id, sequence_no=1,
            item_name='翻译费', pricing_mode='fixed', currency=currency,
            total_excl_tax=excl, total_incl_tax=incl))
    db.flush()
    apply(db, root, 'emergency_notice')
    db.commit()
    preview = mail.build_preview(db, 'translation', project_id=root.id, current_user=actor)
    line = '项目金额：CNY 150.00；USD 25.00（混合税口径）'
    assert line in preview['body']
    assert '（紧急）项目预告知' in preview['body']
    service.send(db, actor, root.id, uuid4())
    from discussion_chat_models import DiscussionMessage
    assert line in db.query(DiscussionMessage).one().content


def test_generated_conversation_and_date_folder_cannot_be_disabled(chat_case,monkeypatch):
    from fastapi import HTTPException
    from routers import chat_session_categories as api
    from chat_session_category_models import ChatSessionCategory
    import chat_session_category_service as categories
    import discussion_chat_service as discussions
    db,actor,staff,root,service=chat_case
    result=service.send(db,actor,root.id,uuid4())
    room=db.get(service.TranslationProjectConversation,(root.id,date(2026,11,9)))
    monkeypatch.setattr(categories,'require_manager',lambda *_:None)
    monkeypatch.setattr(categories,'changed',lambda *_:None)
    catalog=categories.catalog(db,actor)
    assert all(item['deletion_protected'] for item in catalog['items'] if item['id'] in (str(room.room_id),str(room.folder_id)))
    assert next(item for item in discussions.catalog(db,actor) if item['project_id']==result['room_id'])['deletion_protected'] is True
    for identifier in (room.room_id,room.folder_id):
        item=db.get(ChatSessionCategory,identifier)
        with pytest.raises(HTTPException,match='不能删除或停用') as error:
            api.update(identifier,api.CategoryUpdate(active=False,revision=item.revision),db,actor)
        assert error.value.status_code==422
        assert db.get(ChatSessionCategory,identifier).active is True


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
    mail=BusinessMail(id=uuid4(),source_kind='project_manual',project_type='translation',translation_project_id=root.id,subject='测试主题，33批',body=body,status='sent',idempotency_key=str(uuid4()),created_by=actor.id)
    db.add(mail);db.flush()
    db.add(service.TranslationMailChatIntent(mail_id=mail.id,audience=[]));db.commit()
    service.complete_mail_intent(db,mail,actor)
    assert db.query(DiscussionMessage).one().content=='测试主题\n\n'+body
    assert mail.subject=='测试主题，33批'
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
