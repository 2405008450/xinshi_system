"""笔译新增工作报告仅用隔离 SQLite，不发送真实通知。"""
from datetime import datetime, date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from models import TranslationProject
from project_audit_models import ProjectOperationAudit
from task_models import DailyReport, DailyReportItem
from chat_time import BUSINESS_TIMEZONE
import translation_project_work_report as capture


def project(db, actor, required=True, project_type='translation'):
    fields = {'source_file_name': '合同.docx'} if project_type == 'translation' else {}
    row = capture.model(project_type)(id=uuid4(), order_no='TEST-' + uuid4().hex[:12],
        project_name='合同.docx', created_by=actor.id, **fields)
    db.add(row)
    db.flush()
    db.add(ProjectOperationAudit(id=uuid4(), project_type=project_type, project_id=row.id,
        order_no=row.order_no, project_name=row.project_name, operation_type='create',
        operation_source='project_form', actor_user_id=actor.id,
        project_snapshot={'work_report_required': True} if required else {},
        occurred_at=datetime(2026, 11, 24, 9, tzinfo=BUSINESS_TIMEZONE)))
    db.commit()
    return row


def payload(row):
    return capture.ConsultationReportWrite(order_no=row.order_no, task_name=row.project_name,
        progress_content='客户来稿，已核对文件', quantity='1', quantity_unit='项', duration_minutes=20)


@pytest.mark.parametrize('project_type', ['translation','interpretation','recruitment','annotation'])
def test_pending_owner_defaults_and_historical_projects(environment, project_type):
    db, (actor, other, _) = environment
    row = project(db, actor, project_type=project_type)
    project(db, actor, required=False, project_type=project_type)
    assert capture.pending(db, actor, project_type) == [{'id': row.id, 'order_no': row.order_no}]
    assert capture.pending(db, other, project_type) == []
    context = capture.capture_context(db, actor, row.id, project_type)
    assert context['progress_content'] == '客户来稿'
    assert context['task_name'] == '合同.docx' and context['order_no'] == row.order_no
    with pytest.raises(HTTPException):
        capture.capture_context(db, other, row.id, project_type)


@pytest.mark.parametrize('project_type', ['translation','interpretation','recruitment','annotation'])
def test_append_idempotency_authoritative_identity_and_seven_am(environment, monkeypatch, project_type):
    db, (actor, _, _) = environment
    row = project(db, actor, project_type=project_type)
    monkeypatch.setattr(capture, 'now', lambda: datetime(2026, 11, 24, 6, 59, tzinfo=BUSINESS_TIMEZONE))
    monkeypatch.setattr(capture, 'publish_report_update', lambda *_: None)
    data = payload(row).model_copy(update={'order_no': '错误编号', 'task_name': '错误名称'})
    first = capture.submit(db, actor, row.id, data, project_type)
    assert first['report_date'] == date(2026, 11, 23)
    assert capture.submit(db, actor, row.id, data, project_type)['already_saved'] is True
    assert capture.pending(db, actor, project_type) == []
    item = db.query(DailyReportItem).one()
    assert item.task_name == row.project_name
    assert item.progress_content == '客户来稿，已核对文件'
    assert item.display_metadata['order_no'] == row.order_no
    assert item.display_metadata['report_types'] == [capture.LABELS[project_type] + '项目']
    assert item.display_metadata['source'] == capture.source(project_type)
    assert item.display_metadata['added_at'].endswith('+08:00')
    assert capture.capture_context(db, actor, row.id, project_type)['completed'] is True


@pytest.mark.parametrize('project_type', ['translation','interpretation','recruitment','annotation'])
def test_preserves_finalized_report_and_stale_editor(environment, monkeypatch, project_type):
    db, (actor, _, _) = environment
    row = project(db, actor, project_type=project_type)
    instant = datetime(2026, 11, 24, 10, tzinfo=BUSINESS_TIMEZONE)
    existing = DailyReport(id=uuid4(), user_id=actor.id, report_date=instant.date(), status='finalized',
        finalized_at=instant.replace(tzinfo=None))
    old = DailyReportItem(id=uuid4(), report_id=existing.id, source_type='manual', task_type='非项目工作',
        task_name='已有工作', progress_content='原内容', duration_minutes=10, sort_order=0, display_metadata={})
    existing.items.append(old)
    db.add(existing)
    db.commit()
    monkeypatch.setattr(capture, 'now', lambda: instant)
    monkeypatch.setattr(capture, 'publish_report_update', lambda *_: None)
    result = capture.submit(db, actor, row.id, payload(row), project_type)
    assert result['report_id'] == existing.id and existing.status == 'finalized'
    assert len(existing.items) == 2 and existing.items[0].id == old.id
    import task_service
    from task_schemas import DailyReportSaveRequest
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *_: [])
    original = task_service.DailyReportItem
    monkeypatch.setattr(task_service, 'DailyReportItem', lambda **kw: original(id=uuid4(), **kw))
    # 保存前已经打开的草稿不能删除后来追加的笔译记录。
    existing.status = 'draft'
    db.commit()
    task_service.save_daily_report(db, actor, instant.date(), DailyReportSaveRequest(items=[]))
    assert any((item.display_metadata or {}).get('source') == capture.source(project_type) for item in existing.items)


def test_recruitment_blank_project_name_falls_back_to_client_position_or_order_no(environment, monkeypatch):
    from models import Client
    db, (actor, _, _) = environment
    monkeypatch.setattr(capture, 'now', lambda: datetime(2026, 11, 25, 10, tzinfo=BUSINESS_TIMEZONE))
    monkeypatch.setattr(capture, 'publish_report_update', lambda *_: None)

    client = Client(id=uuid4(), client_name='山东康迈机械有限公司', client_short_name='山东康迈机械')
    db.add(client)
    db.flush()

    row_with_position = capture.model('recruitment')(
        id=uuid4(), order_no='HP-261125-001', project_name=None,
        client_id=client.id, position_title='西班牙语翻译', created_by=actor.id,
    )
    row_only_order = capture.model('recruitment')(
        id=uuid4(), order_no='HP-261125-002', project_name='   ',
        position_title=None, created_by=actor.id,
    )
    for row in (row_with_position, row_only_order):
        db.add(row)
        db.flush()
        db.add(ProjectOperationAudit(
            id=uuid4(), project_type='recruitment', project_id=row.id,
            order_no=row.order_no, project_name=None, operation_type='create',
            operation_source='project_form', actor_user_id=actor.id,
            project_snapshot={'work_report_required': True, 'project_name': None},
            occurred_at=datetime(2026, 11, 25, 10, tzinfo=BUSINESS_TIMEZONE),
        ))
    db.commit()

    ctx1 = capture.capture_context(db, actor, row_with_position.id, 'recruitment')
    assert ctx1['task_name'] == '山东康迈机械-西班牙语翻译'
    ctx2 = capture.capture_context(db, actor, row_only_order.id, 'recruitment')
    assert ctx2['task_name'] == 'HP-261125-002'

    data1 = capture.ConsultationReportWrite(
        order_no=row_with_position.order_no, task_name=ctx1['task_name'],
        progress_content='客户来稿', quantity='1', quantity_unit='人', duration_minutes=60,
    )
    capture.submit(db, actor, row_with_position.id, data1, 'recruitment')
    item = db.query(DailyReportItem).filter(DailyReportItem.source_id == row_with_position.id).one()
    assert item.task_name == '山东康迈机械-西班牙语翻译'


@pytest.mark.parametrize('project_type', ['translation', 'interpretation', 'annotation'])
def test_other_project_types_blank_name_falls_back_to_order_no(environment, monkeypatch, project_type):
    db, (actor, _, _) = environment
    monkeypatch.setattr(capture, 'now', lambda: datetime(2026, 11, 25, 10, tzinfo=BUSINESS_TIMEZONE))
    monkeypatch.setattr(capture, 'publish_report_update', lambda *_: None)

    row = capture.model(project_type)(
        id=uuid4(), order_no='ORD-' + uuid4().hex[:8], project_name=None, created_by=actor.id,
    )
    db.add(row)
    db.flush()
    db.add(ProjectOperationAudit(
        id=uuid4(), project_type=project_type, project_id=row.id,
        order_no=row.order_no, project_name=None, operation_type='create',
        operation_source='project_form', actor_user_id=actor.id,
        project_snapshot={'work_report_required': True},
        occurred_at=datetime(2026, 11, 25, 10, tzinfo=BUSINESS_TIMEZONE),
    ))
    db.commit()

    ctx = capture.capture_context(db, actor, row.id, project_type)
    assert ctx['task_name'] == row.order_no
    data = capture.ConsultationReportWrite(
        order_no=row.order_no, task_name=ctx['task_name'],
        progress_content='客户来稿', quantity='1', quantity_unit='项', duration_minutes=15,
    )
    capture.submit(db, actor, row.id, data, project_type)
    item = db.query(DailyReportItem).filter(DailyReportItem.source_id == row.id).one()
    assert item.task_name == row.order_no
