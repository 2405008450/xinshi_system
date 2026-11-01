from datetime import date,datetime
from uuid import uuid4
import pytest
from pydantic import ValidationError
from test_chat_participant_access import environment
import editor_drafts as drafts


def write(key='2026-10-30',revision=0,payload=None):
    return drafts.DraftWrite(namespace='work-report',key=key,revision=revision,payload=payload)


def test_cloud_draft_preserves_incomplete_fields_and_rejects_old_windows(environment):
    db,(owner,other,_)=environment
    payload={'items':[{'task_name':'尚未完成','duration_minutes':0,'display_metadata':{}}],'idle_declaration_confirmed':False}
    first=drafts.save_batch(db,owner,[write(payload=payload)])[0]
    assert first['revision']==1
    assert drafts.read(db,owner,'work-report','2026-10-30')['payload']==payload
    assert drafts.read(db,other,'work-report','2026-10-30')['payload'] is None
    assert drafts.save_batch(db,owner,[write(revision=1,payload=payload)])[0]['revision']==1
    assert drafts.save_batch(db,owner,[write(revision=0,payload=payload)])[0]['revision']==1
    assert drafts.save_batch(db,owner,[write(payload={'items':[]})])[0]['conflict'] is True
    assert drafts.read(db,owner,'work-report','2026-10-30')['payload']==payload
    assert drafts.save_batch(db,owner,[write(revision=1,payload=None)])[0]['revision']==2
    assert drafts.save_batch(db,owner,[write(revision=1,payload=payload)])[0]['conflict'] is True


def test_formal_report_save_clears_draft_in_same_transaction(environment,monkeypatch):
    import task_service
    from task_models import DailyReport
    from task_schemas import ManualDailyReportSaveRequest
    db,(owner,_,_)=environment
    stamp=datetime(2026,10,30,8)
    report=DailyReport(id=uuid4(),user_id=owner.id,report_date=date(2026,10,30),status='draft',generated_at=stamp,created_at=stamp,updated_at=stamp)
    db.add(report);db.commit()
    drafts.save_batch(db,owner,[write(payload={'items':[]})])
    monkeypatch.setattr(task_service,'derive_daily_report_items',lambda *_:[])
    task_service.save_daily_report(db,owner,report.report_date,ManualDailyReportSaveRequest(items=[],idle_minutes=0,idle_declaration_confirmed=True))
    current=drafts.read(db,owner,'work-report','2026-10-30')
    assert current['payload'] is None and current['revision']==2
    assert task_service.serialize_report(report)['edit_draft_revision']==2


def test_migration_is_repeatable_and_payload_limits(environment):
    from tools.apply_editor_drafts_migration import apply_migration
    db,_=environment
    drafts.EditorDraft.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert db.query(drafts.EditorDraft).count()==0
    with pytest.raises(ValidationError):write(payload='x'*(256*1024))
    with pytest.raises(ValidationError):write(payload={'note':'data:image/png;xx'})
    assert drafts.DraftWrite(namespace='global',key='form',revision=0,payload={'name':'保留','password':'禁止','nested':{'api_token':'禁止','notes':'保留'}}).payload=={'name':'保留','nested':{'notes':'保留'}}
