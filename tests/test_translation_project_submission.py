"""保存前填写和紧急预告知：仅内存 SQLite，不发送实际邮件。"""
import pytest
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case


def payload(case, **kw):
    from schemas import TranslationProjectCreate
    return TranslationProjectCreate(project_name='母项目',initial_sub_order_names=['a.pdf','b.docx'],created_by=case[1].id,service_content='翻译',language_pair='中文→英语',**kw)


def test_normal_creation_requires_review_and_each_file_statistics_and_rolls_back(case):
    from models import TranslationProject
    db,user,crud=case
    with pytest.raises(ValueError,match='先打开子订单管理'):
        crud.create_translation_project(db,payload(case,submission_mode='normal'),order_no='TP-261108-981')
    db.rollback()
    assert db.query(TranslationProject).count()==0
    with pytest.raises(ValueError,match='我司统计或客户统计'):
        crud.create_translation_project(db,payload(case,submission_mode='normal',sub_orders_reviewed=True),order_no='TP-261108-981')
    db.rollback()
    assert db.query(TranslationProject).count()==0
    root=crud.create_translation_project(db,payload(case,submission_mode='normal',sub_orders_reviewed=True,initial_sub_order_details={
        '001':{'word_count_matrix':{'company':{'words':100}}},
        '002':{'word_count_matrix':{'customer':{'pages':2}}},
    }),order_no='TP-261108-981')
    assert len(root.sub_orders)==2
    assert root.word_count_matrix['company']['words']==100 and root.word_count_matrix['customer']['pages']==2


def test_emergency_can_save_without_child_statistics_and_normal_clears_notice(case,monkeypatch):
    from schemas import TranslationProjectUpdate,TranslationSubOrderUpdate
    from translation_project_submission import mail_policy,TranslationProjectSubmission
    from tests.test_business_mail import _settings
    import business_mail_service as mail
    db,user,crud=case
    root=crud.create_translation_project(db,payload(case,submission_mode='emergency_notice'),order_no='TP-261108-982')
    assert mail_policy(db,root)==(True,'')
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:([],[]))
    monkeypatch.setattr(mail.SmtpSettings,'from_env',lambda:_settings())
    preview=mail.build_preview(db,'translation',project_id=root.id)
    assert preview['subject'].startswith('（紧急）项目预告知：')
    assert '子订单字数及相关资料可能尚未完善' in preview['body']
    for child in root.sub_orders:
        crud.update_sub_order(db,child.id,TranslationSubOrderUpdate(word_count_matrix={'company':{'words':10}}))
    crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='normal',sub_orders_reviewed=True),actor_user_id=user.id)
    assert mail_policy(db,root)==(False,'')
    assert not db.get(TranslationProjectSubmission,root.id).emergency_notice


def test_multidirection_creation_uses_each_leaf_statistics(case):
    from schemas import TranslationProjectCreate
    db,user,crud=case
    root=crud.create_translation_project(db,TranslationProjectCreate(project_name='a.docx',language_pair='中文→英语；中文→法语',created_by=user.id,submission_mode='normal',sub_orders_reviewed=True,initial_sub_order_details={
        '001':{'word_count_matrix':{'company':{'words':12}}},
        '002':{'word_count_matrix':{'company':{'words':15}}},
    }),order_no='TP-261108-983')
    assert root.word_count_matrix['company']['words'] is None
    assert root.word_count_matrix_source=='project'


def test_direction_copies_keep_manual_edit_and_original_project_counts(case):
    from schemas import TranslationProjectCreate
    db,user,crud=case
    root=crud.create_translation_project(db,TranslationProjectCreate(project_name='原文.docx',language_pair='中文→英语；中文→法语',created_by=user.id,submission_mode='normal',sub_orders_reviewed=True,word_count_matrix={'company':{'words':100}},initial_sub_order_details={
        '001':{'word_count_matrix':{'company':{'words':80}}},
        '002':{'word_count_matrix':{'company':{'words':100}}},
    }),order_no='TP-261110-983')
    assert sorted(row.word_count_matrix['company']['words'] for row in root.sub_orders)==[80,100]
    assert root.word_count_matrix['company']['words']==100
    assert root.word_count_matrix_source=='project'


def test_preliminary_only_does_not_pass_and_zero_is_valid(case):
    db,user,crud=case
    with pytest.raises(ValueError,match='我司统计或客户统计'):
        crud.create_translation_project(db,payload(case,submission_mode='normal',sub_orders_reviewed=True,initial_sub_order_details={
            '001':{'word_count_matrix':{'preliminary':{'words':1}}},'002':{'word_count_matrix':{'company':{'words':0}}}
        }),order_no='TP-261108-984')
    db.rollback()


def test_invalid_initial_detail_returns_safe_field_errors_before_any_write(case):
    from fastapi import HTTPException
    from models import TranslationProject
    db,user,crud=case
    with pytest.raises(HTTPException) as error:
        crud.create_translation_project(db,payload(case,initial_sub_order_details={
            '001':{'translator_id':'','customer_deadline_time':'','review1_progress':0},
        }),order_no='TP-261110-981')
    assert error.value.status_code==422
    errors=error.value.detail
    assert {item['loc'][-1] for item in errors}=={'translator_id','customer_deadline_time','review1_progress'}
    assert all(item['loc'][:3]==['body','initial_sub_order_details','001'] for item in errors)
    assert all('input' not in item and 'url' not in item and 'ctx' not in item for item in errors)
    assert db.query(TranslationProject).count()==0


def test_normalized_initial_detail_can_save_zero_counts_and_unassigned_translator(case):
    from translation_project_submission import mail_policy
    db,user,crud=case
    root=crud.create_translation_project(db,payload(case,submission_mode='normal_children',sub_orders_reviewed=True,initial_sub_order_details={
        '001':{'translator_id':None,'translator_assignment_time':None,'sent_to_client_time':None,'customer_deadline_time':None,'translator_delivery_progress':'0','review1_progress':'35','word_count_matrix':{'company':{'words':0}}},
        '002':{'word_count_matrix':{'company':{'words':123}}},
    }),order_no='TP-261110-982')
    first=next(row for row in root.sub_orders if row.sub_order_no.endswith('.001'))
    assert first.translator_id is None and first.customer_deadline_time is None
    assert first.translator_delivery_progress=='0%' and first.review1_progress=='35%'
    assert root.word_count_matrix['company']['words']==123
    assert mail_policy(db,root)==(False,'')


def test_mail_policy_blocks_unreviewed_existing_children(case):
    from translation_project_submission import mail_policy
    db,user,crud=case
    root=crud.create_translation_project(db,payload(case),order_no='TP-261108-985')
    notice,error=mail_policy(db,root)
    assert not notice and '子订单管理' in error


def test_new_child_editor_preserves_details_and_independent_directions(case):
    from schemas import TranslationProjectCreate
    db,user,crud=case
    root=crud.create_translation_project(db,TranslationProjectCreate(
        project_name='母项目',created_by=user.id,language_pair='中文→英语',
        initial_sub_order_names=['a.pdf','b.docx'],
        initial_sub_order_details={
            '001':{'language_pair':'中文→法语','priority':'高','client_feedback':'待反馈',
                   'sent_to_client_time':'2026-11-08T16:00:00+08:00','network_file_path':r'D:\资料\a.pdf',
                   'review1_progress':'35','word_count_matrix':{'company':{'words':123}}},
            '002':{'customer_requirement_professional':'子专业要求','word_count_matrix':{'customer':{'pages':2}}},
        }),order_no='TP-261108-987')
    first=next(row for row in root.sub_orders if row.sub_order_no.endswith('.001'))
    assert '法语' in first.language_pair and first.priority=='高' and first.client_feedback=='待反馈'
    assert first.network_file_path==r'D:\资料\a.pdf' and first.review1_progress=='35%'
    assert first.word_count_matrix['company']['words']==123


def test_child_tab_draft_saves_without_counts_but_cannot_deliver_until_aggregate(case):
    from schemas import TranslationProjectUpdate, TranslationSubOrderUpdate
    from translation_project_submission import mail_policy
    db,user,crud=case
    root=crud.create_translation_project(db,payload(case,submission_mode='draft',sub_orders_reviewed=True),order_no='TP-261108-988')
    assert '汇总至母订单' in mail_policy(db,root)[1]
    with pytest.raises(ValueError,match='我司统计或客户统计'):
        crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='normal_children',sub_orders_reviewed=True),actor_user_id=user.id)
    db.rollback()
    for child in root.sub_orders:
        crud.update_sub_order(db,child.id,TranslationSubOrderUpdate(word_count_matrix={'company':{'words':25}}))
    # 填写完成仍须正式确认；母订单统计由子订单计算。
    assert mail_policy(db,root)[1]
    root=crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='normal_children',sub_orders_reviewed=True),actor_user_id=user.id)
    assert root.word_count_matrix['company']['words']==50
    assert mail_policy(db,root)==(False,'')


def test_child_tab_cannot_deliver_without_children_but_other_tab_keeps_existing_rule(case):
    from schemas import TranslationProjectCreate, TranslationProjectUpdate
    from translation_project_submission import mail_policy
    db,user,crud=case
    root=crud.create_translation_project(db,TranslationProjectCreate(project_name='母项目.docx',created_by=user.id,submission_mode='draft'),order_no='TP-261108-989')
    assert mail_policy(db,root)[1]
    with pytest.raises(ValueError,match='先创建子订单'):
        crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='normal_children',sub_orders_reviewed=True),actor_user_id=user.id)
    db.rollback()
    crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='emergency_notice'),actor_user_id=user.id)
    assert mail_policy(db,root)==(True,'')
    crud.update_translation_project(db,root.id,TranslationProjectUpdate(submission_mode='normal',sub_orders_reviewed=True),actor_user_id=user.id)
    assert mail_policy(db,root)==(False,'')
