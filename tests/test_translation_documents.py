from uuid import uuid4
import pytest
from fastapi import HTTPException
from models import TranslationProject
from schemas import TranslationProjectUpdate
from tests.test_chat_participant_access import environment
from routers.translation_quotations import read, write, QuotationWrite
import translation_document_requirements as documents
import crud


def setup(db, actor):
    row=TranslationProject(id=uuid4(),order_no='TP-261104-998',project_name='报价测试.docx',source_file_name='报价测试.docx',created_by=actor.id)
    db.add(row);db.commit()
    return row


def draft():
    return documents.QuotationDraft(items=[dict(description='翻译服务',quantity='123.5',unit_price='.25',currency='CNY')])


def test_defaults_and_explicit_document_requirements(environment):
    db,(actor,_,_)=environment;project=setup(db,actor)
    project.customer_type='个人客户';documents.attach(db,[project]);assert project.statement_required is False
    project.customer_type='企业客户';documents.attach(db,[project]);assert project.statement_required is True
    documents.save(db,project,statement_required=False,actor_id=actor.id);db.commit()
    documents.attach(db,[project]);assert project.statement_required is False
    saved=crud.update_translation_project(db,project.id,TranslationProjectUpdate(quotation_required=True,statement_required=True,quotation_draft=draft()),actor.id)
    assert saved.quotation_required and saved.statement_required
    assert saved.quotation_draft['items'][0]['quantity']=='123.5'


def test_same_quotation_from_both_entries_and_revision_protection(environment):
    db,(actor,_,_)=environment;project=setup(db,actor)
    assert read(project.id,db,actor)['revision']==0
    result=write(project.id,QuotationWrite(revision=0,document=draft()),db,actor)
    assert result['revision']==1
    assert crud.get_translation_project(db,project.id).quotation_draft==result['document']
    changed=draft();changed.notes='财务窗口修改'
    result=write(project.id,QuotationWrite(revision=1,document=changed),db,actor)
    assert result['revision']==2
    with pytest.raises(HTTPException) as error:write(project.id,QuotationWrite(revision=1,document=draft()),db,actor)
    assert error.value.status_code==409
    assert read(project.id,db,actor)['document']['notes']=='财务窗口修改'


def test_migration_repeatable_and_no_old_table_changes(environment):
    db,_=environment
    from tools.apply_translation_documents_migration import apply_migration
    documents.TranslationProjectDocuments.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert documents.ready(db)
