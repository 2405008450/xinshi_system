"""在独立 PostgreSQL 实例验证母子订单事务与执行隔离。"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import annotation_service as service
from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationProjectStatusHistory
from annotation_schemas import AnnotationProjectCreate, AnnotationProjectUpdate
from interpretation_models import InterpretationLanguage
from project_order_no_models import ProjectOrderNoReservation


@pytest.fixture(scope="module")
def sessions():
    url = os.getenv("ANNOTATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要独立 PostgreSQL 测试实例")
    import main  # noqa: F401 注册所有既有关系，不启动应用
    from models import Base
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        connection.execute(text("CREATE SEQUENCE IF NOT EXISTS chat_message_sequence"))
    Base.metadata.create_all(engine)
    # 还原历史表结构后实际执行增量迁移，两次执行均不改变历史记录。
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE annotation_project DROP COLUMN parent_project_id CASCADE"))
        connection.execute(text("ALTER TABLE annotation_project DROP COLUMN child_sequence_no CASCADE"))
        connection.execute(text("INSERT INTO annotation_project (order_no, project_name) VALUES ('AP-LEGACY-KEEP', '历史保留项目')"))
    sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261014_add_annotation_child_orders.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
        historical = connection.execute(text("SELECT project_name, parent_project_id, child_sequence_no FROM annotation_project WHERE order_no = 'AP-LEGACY-KEEP'")).one()
        assert tuple(historical) == ("历史保留项目", None, None)
    material_sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261015_annotation_material_shared_versions.sql").read_text(encoding="utf-8")
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE annotation_material_version ADD CONSTRAINT legacy_upload_unique UNIQUE (upload_id)"))
        connection.exec_driver_sql(material_sql)
        connection.exec_driver_sql(material_sql)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def context(sessions):
    with sessions() as db:
        language = InterpretationLanguage(id=uuid4(), label="子单测试语种" + uuid4().hex[:8])
        db.add(language)
        db.commit()
        parent = service.create_annotation_project(db, AnnotationProjectCreate(
            project_name="多语种母订单", task_description="公共任务要求",
            project_types=["text_annotation"], contact_name="原联系人", customer_order_no="CLIENT-001",
            language_items=[{"source_language_id": language.id}],
        ), None)
        yield db, parent.id, language.id


def item(language_id, **values):
    return AnnotationProjectCreate(language_items=[{"source_language_id": language_id}], **values)


def update_payload(project, **changes):
    from annotation_schemas import AnnotationProjectDetailResponse
    data = AnnotationProjectDetailResponse.model_validate(project).model_dump()
    fields = AnnotationProjectUpdate.model_fields
    data = {key: value for key, value in data.items() if key in fields}
    data.update(expected_updated_at=project.updated_at)
    data.update(changes)
    return AnnotationProjectUpdate.model_validate(data)


def add_test_language(db):
    language = InterpretationLanguage(label='自动方向'+uuid4().hex[:8])
    db.add(language); db.commit()
    return language.id


def test_automatic_create_single_and_multiple_directions(context):
    db, parent_id, language_id = context
    assert service.get_annotation_project(db, parent_id).child_count == 0
    second = add_test_language(db)
    directions = [{'source_language_id': language_id},
                  {'source_language_id': language_id, 'target_language_id': second},
                  {'source_language_id': second, 'target_language_id': language_id}]
    parent = service.create_annotation_project(db, AnnotationProjectCreate(
        project_name='自动母订单', language_items=directions), None)
    assert parent.auto_created_child_count == parent.child_count == 3
    children = service.get_annotation_projects(db, parent_project_id=parent.id)
    assert len(children) == 3 and all(len(child.language_items) == 1 for child in children)
    assert {(child.language_items[0].source_language_id, child.language_items[0].target_language_id)
            for child in children} == {(language_id, None), (language_id, second), (second, language_id)}
    assert parent.direction_summary['missing_directions'] == []
    parent = service.update_annotation_project(db, parent.id, update_payload(parent))
    assert parent.auto_created_child_count == 0 and parent.child_count == 3


def test_automatic_add_delete_change_and_shrink_preserve_children(context):
    db, parent_id, language_id = context
    second, third = add_test_language(db), add_test_language(db)
    existing = service.create_annotation_children(db, parent_id,
        [item(language_id, task_description='人工调整'), item(language_id)], None, 'manual-batches')[0]
    parent = service.get_annotation_project(db, parent_id)
    parent = service.update_annotation_project(db, parent_id, update_payload(parent,
        language_items=[{'id':parent.language_items[0].id,'source_language_id':language_id}, {'source_language_id':second}]))
    assert parent.auto_created_child_count == 1 and parent.child_count == 3
    assert service.get_annotation_project(db, existing.id).task_description == '人工调整'
    second_child = next(child for child in service.get_annotation_projects(db, parent_project_id=parent_id)
                        if child.language_items[0].source_language_id == second)
    old_number = second_child.order_no
    service.delete_annotation_project(db, second_child.id)
    parent = service.get_annotation_project(db, parent_id)
    parent = service.update_annotation_project(db, parent_id, update_payload(parent))
    assert parent.auto_created_child_count == 1
    replacement = next(child for child in service.get_annotation_projects(db, parent_project_id=parent_id)
                       if child.language_items[0].source_language_id == second)
    assert replacement.order_no != old_number
    service.update_annotation_project(db, replacement.id, update_payload(replacement,
        language_items=[{'id':replacement.language_items[0].id,'source_language_id':third}]))
    parent = service.get_annotation_project(db, parent_id)
    assert parent.direction_summary['extra_directions'] and parent.direction_summary['missing_directions']
    parent = service.update_annotation_project(db, parent_id, update_payload(parent))
    assert parent.auto_created_child_count == 1 and parent.child_count == 4
    parent = service.update_annotation_project(db, parent_id, update_payload(parent,
        language_items=[{'id':parent.language_items[0].id,'source_language_id':language_id}]))
    assert parent.auto_created_child_count == 0 and parent.child_count == 4
    assert not parent.direction_summary['automatic_enabled'] and parent.direction_summary['extra_directions']


def test_child_requires_exactly_one_direction(context):
    db, parent_id, language_id = context
    second = add_test_language(db)
    with pytest.raises(ValueError, match='只能绑定一个'):
        service.create_annotation_children(db, parent_id, [AnnotationProjectCreate(language_items=[
            {'source_language_id':language_id}, {'source_language_id':second}])], None, 'multi-child')
    db.rollback()
    child = service.create_annotation_children(db, parent_id, [item(language_id)], None, 'one-child')[0]
    with pytest.raises(ValueError, match='只能绑定一个'):
        service.update_annotation_project(db, child.id, update_payload(child, language_items=[]))
    db.rollback()
    assert len(service.get_annotation_project(db, child.id).language_items) == 1


def test_stale_parent_save_does_not_generate_children(context):
    from concurrency import StaleUpdateError
    db,parent_id,language_id = context
    second = add_test_language(db)
    parent = service.get_annotation_project(db,parent_id)
    with pytest.raises(StaleUpdateError):
        service.update_annotation_project(db,parent_id,update_payload(parent,
            expected_updated_at=datetime(2000,1,1),language_items=[{'source_language_id':language_id},{'source_language_id':second}]))
    db.rollback()
    assert service.get_annotation_project(db,parent_id).child_count == 0


def test_automatic_creation_failure_rolls_back_parent_and_children(context, monkeypatch):
    db, parent_id, language_id = context
    second = add_test_language(db)
    original = service.create_annotation_project
    calls = []
    def fail_second(db, payload, *args, **kwargs):
        if kwargs.get('operation_source') == 'automatic_direction_create':
            calls.append(payload)
            if len(calls) == 2:
                raise ValueError('自动创建失败测试')
        return original(db, payload, *args, **kwargs)
    monkeypatch.setattr(service, 'create_annotation_project', fail_second)
    parent = service.get_annotation_project(db, parent_id)
    before_name = parent.project_name
    with pytest.raises(ValueError, match='自动创建失败'):
        service.update_annotation_project(db, parent_id, update_payload(parent,
            project_name='不应保存', language_items=[{'source_language_id':language_id}, {'source_language_id':second}]))
    db.rollback()
    parent = service.get_annotation_project(db, parent_id)
    assert parent.project_name == before_name and len(parent.language_items) == 1 and parent.child_count == 0
    assert db.query(ProjectOrderNoReservation).filter(ProjectOrderNoReservation.order_no.like(parent.order_no+'.%')).count() == 0
    calls.clear()
    with pytest.raises(ValueError, match='自动创建失败'):
        service.create_annotation_project(db, AnnotationProjectCreate(project_name='整次新增回滚',
            language_items=[{'source_language_id':language_id},{'source_language_id':second}]), None)
    db.rollback()
    assert db.query(AnnotationProject).filter_by(project_name='整次新增回滚').count() == 0


def test_automatic_snapshot_includes_current_form_rates(context):
    from resource_models import ResourcePerson, ResourceCapability
    db, parent_id, language_id = context
    second = add_test_language(db)
    person = ResourcePerson(full_name='自动复制单价人员')
    db.add(person); db.flush()
    db.add(ResourceCapability(person_id=person.id, capability_type='annotation', status='active'))
    db.commit()
    parent = service.get_annotation_project(db, parent_id)
    parent = service.update_annotation_project(db, parent_id, update_payload(parent,
        language_items=[{'id':parent.language_items[0].id,'source_language_id':language_id},{'source_language_id':second}],
        assignees=[{'person_id':person.id,'rate':{'amount':8,'currency':'CNY','unit':'item','remarks':'本次表单单价'}}]))
    assert parent.auto_created_child_count == 2
    children = service.get_annotation_projects(db, parent_project_id=parent_id)
    assert len({parent.assignees[0].rate.id, *(child.assignees[0].rate.id for child in children)}) == 3
    assert all(child.assignees[0].rate.amount == 8 for child in children)
    parent = service.update_annotation_project(db, parent_id, update_payload(parent,
        assignees=[{'id':parent.assignees[0].id,'person_id':person.id,'rate':None}]))
    assert parent.assignees[0].rate is None
    assert all(service.get_annotation_project(db, child.id).assignees[0].rate.amount == 8 for child in children)


def test_historical_preview_apply_retry_partial_failure_and_legacy_child(context, sessions, monkeypatch):
    from annotation_models import AnnotationProjectLanguageItem
    from tools.backfill_annotation_direction_children import backfill
    import annotation_direction_service as directions
    db, parent_id, language_id = context
    second = add_test_language(db)
    parent = service.get_annotation_project(db, parent_id)
    parent.project_status = 'ended'
    parent.language_items.append(AnnotationProjectLanguageItem(sequence_no=2, source_language_id=second))
    legacy = AnnotationProject(order_no=parent.order_no+'-S001',parent_project_id=parent_id,child_sequence_no=1)
    legacy.language_items = [AnnotationProjectLanguageItem(sequence_no=1,source_language_id=language_id),
                             AnnotationProjectLanguageItem(sequence_no=2,source_language_id=second)]
    db.add(legacy); db.flush()
    service.reserve_annotation_order_no(db,project_id=legacy.id,order_no=legacy.order_no,
        assignment_source='historical_fixture',assigned_by=None)
    db.commit()
    before_history = db.query(AnnotationProjectStatusHistory).filter_by(project_id=parent_id).count()
    preview = backfill(sessions,parent_ids=[parent_id])
    assert len(preview) == 1 and len(preview[0]['pending_directions']) == 2 and preview[0]['anomalies']
    assert service.get_annotation_project(db,parent_id).child_count == 1
    db.rollback()
    applied = backfill(sessions,apply=True,parent_ids=[parent_id])
    assert applied[0]['status'] == 'success', applied
    assert len(applied[0]['created_order_nos']) == 2
    assert backfill(sessions,apply=True,parent_ids=[parent_id])[0]['created_order_nos'] == []
    assert db.query(AnnotationProjectStatusHistory).filter_by(project_id=parent_id).count() == before_history
    assert len(service.get_annotation_project(db,legacy.id).language_items) == 2
    db.rollback()
    other = AnnotationProject(order_no='AP-FAIL-BACKFILL-'+uuid4().hex[:8].upper())
    other.language_items = [AnnotationProjectLanguageItem(sequence_no=1,source_language_id=language_id),
                            AnnotationProjectLanguageItem(sequence_no=2,source_language_id=second)]
    db.add(other); db.commit()
    original = directions.ensure_direction_children
    def fail_one(db,parent,*args,**kwargs):
        if parent.id == other.id:
            raise ValueError('母订单失败测试')
        return original(db,parent,*args,**kwargs)
    monkeypatch.setattr(directions,'ensure_direction_children',fail_one)
    db.rollback()
    results = backfill(sessions,apply=True,parent_ids=[parent_id,other.id])
    assert sorted(row['status'] for row in results) == ['failed','success']


def test_concurrent_automatic_save_and_backfill_no_duplicates(context, sessions):
    from annotation_models import AnnotationProjectLanguageItem
    from tools.backfill_annotation_direction_children import backfill
    db,parent_id,language_id = context
    second = add_test_language(db)
    parent = service.get_annotation_project(db,parent_id)
    parent.language_items.append(AnnotationProjectLanguageItem(sequence_no=2,source_language_id=second))
    db.commit()
    payload = update_payload(parent,expected_updated_at=None)
    db.rollback()
    def save():
        with sessions() as concurrent:
            return service.update_annotation_project(concurrent,parent_id,payload).child_count
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks=[executor.submit(save), executor.submit(save),
               executor.submit(backfill,sessions,apply=True,parent_ids=[parent_id])]
        for task in tasks:
            task.result(timeout=30)
    assert service.get_annotation_project(db,parent_id).child_count == 2


def test_defaults_same_language_batches_and_retry(context):
    db, parent_id, language_id = context
    request = [item(language_id, project_name="英语一批"), item(language_id, project_name="英语二批")]
    children = service.create_annotation_children(db, parent_id, request, None, "same-batch-key")
    assert [child.child_sequence_no for child in children] == [1, 2]
    assert all(child.contact_name == "原联系人" and child.task_description == "公共任务要求" for child in children)
    assert all(child.parent_project_id == parent_id and not child.assignees and not child.price_items for child in children)
    again = service.create_annotation_children(db, parent_id, request, None, "same-batch-key")
    assert [child.id for child in children] == [child.id for child in again]
    with pytest.raises(ValueError, match="内容已改变"):
        service.create_annotation_children(db, parent_id, [item(language_id, project_name="改变")], None, "same-batch-key")
    db.rollback()


def test_full_snapshot_direction_remapping_and_override(context, monkeypatch):
    from resource_models import ResourcePerson
    from annotation_models import AnnotationProjectAssignee, AnnotationProjectPriceItem, AnnotationProjectLanguageItem
    from annotation_ops_models import AnnotationAssigneeRate, AnnotationCustomFieldDefinition
    db, parent_id, language_id = context
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\Win-server\服务器资料7")
    person = ResourcePerson(full_name="复制测试人员")
    other_language = InterpretationLanguage(label="另一复制方向" + uuid4().hex[:8])
    db.add_all([person, other_language]); db.flush()
    parent = service.get_annotation_project(db, parent_id)
    parent.project_status = 'project_in_progress'
    parent.priority = 'high'
    parent.potential_demand = '约1000条/批'
    parent.language_region = '地区要求'
    parent.project_path = r'\\Win-server\服务器资料7\复制测试'
    parent.task_submitted_at = datetime(2026, 12, 1)
    field = AnnotationCustomFieldDefinition(table_code='project', field_key='copy_'+uuid4().hex, field_label='复制字段', data_type='text', sequence_no=1)
    scoped = AnnotationCustomFieldDefinition(project_id=parent.id, table_code='assignment', field_key='person_copy', field_label='人员字段', data_type='text', sequence_no=1)
    db.add_all([field, scoped]); db.flush()
    parent.custom_values = {str(field.id): '母单自定义值'}
    direction = parent.language_items[0]
    second_direction = AnnotationProjectLanguageItem(sequence_no=2, source_language_id=other_language.id)
    parent.language_items.append(second_direction)
    db.flush()
    parent.price_items.append(AnnotationProjectPriceItem(sequence_no=1, amount=12, currency='CNY', unit='条', source_language_id=language_id))
    parent.price_items.append(AnnotationProjectPriceItem(sequence_no=2, amount=99, currency='CNY', unit='条', source_language_id=other_language.id))
    assigned = AnnotationProjectAssignee(person_id=person.id, sequence_no=1, language_item_id=direction.id, custom_values={str(scoped.id): '人员业务值'})
    parent.assignees.append(assigned); db.flush()
    parent.assignees.append(AnnotationProjectAssignee(person_id=person.id, sequence_no=2, language_item_id=second_direction.id))
    assigned.rate = AnnotationAssigneeRate(amount=3, currency='CNY', unit='item', remarks='人员单价')
    db.commit()
    child = service.create_annotation_children(db, parent_id, [item(other_language.id, copy_source_language_item_id=direction.id, expected_parent_updated_at=parent.updated_at)], None, 'snapshot-key')[0]
    assert child.project_name == parent.project_name
    assert child.priority == 'high' and child.project_status == 'project_in_progress'
    assert child.potential_demand == parent.potential_demand and child.project_path == parent.project_path
    assert child.task_submitted_at == parent.task_submitted_at and child.custom_values == parent.custom_values
    assert child.price_items[0].id != parent.price_items[0].id
    assert len(child.price_items) == 1 and child.price_items[0].amount == 12
    assert len(child.assignees) == 1
    assert child.price_items[0].source_language_id == other_language.id
    assert child.assignees[0].id != assigned.id and child.assignees[0].language_item_id == child.language_items[0].id
    assert child.assignees[0].rate.amount == 3 and child.assignees[0].rate.id != assigned.rate.id
    assert list(child.assignees[0].custom_values.values()) == ['人员业务值']
    assert str(scoped.id) not in child.assignees[0].custom_values
    override = service.create_annotation_children(db, parent_id, [item(language_id, price_items=[], assignees=[], custom_values={}, priority='low', copy_parent_materials=False)], None, 'override-key')[0]
    assert not override.price_items and not override.assignees and override.priority == 'low'


def test_snapshot_stale_parent_and_atomic_copy_rollback(context):
    from concurrency import StaleUpdateError
    db, parent_id, language_id = context
    parent = service.get_annotation_project(db, parent_id)
    stale = datetime(2000, 1, 1)
    with pytest.raises(StaleUpdateError):
        service.create_annotation_children(db, parent_id, [item(language_id, expected_parent_updated_at=stale)], None, 'stale-parent')
    db.rollback()
    assert service.get_annotation_project(db, parent_id).child_count == 0
    with pytest.raises(ValueError, match='复制来源语种'):
        service.create_annotation_children(db, parent_id, [item(language_id), item(language_id, copy_source_language_item_id=uuid4())], None, 'copy-failure')
    db.rollback()
    assert service.get_annotation_project(db, parent_id).child_count == 0


def test_copied_materials_independent_versions_and_last_reference_cleanup(context):
    from datetime import timedelta
    from annotation_material_models import AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialDeletion as Deletion
    from annotation_material_service import remove_material, versions
    db, parent_id, language_id = context
    upload = Upload(uploader_name='复制测试', original_name='合同.pdf', storage_key=uuid4().hex, file_size=100, content_type='application/pdf', sha256='a'*64, consumed_at=datetime.now(), expires_at=datetime.now()+timedelta(days=1))
    original = Material(project_id=parent_id, category='contract')
    db.add_all([upload, original]); db.flush()
    db.add(Version(file_id=original.id, upload_id=upload.id, version_no=1)); db.commit()
    children = service.create_annotation_children(db, parent_id, [item(language_id), item(language_id)], None, 'material-copy')
    child_files = [db.query(Material).filter_by(project_id=child.id).one() for child in children]
    assert len({original.id, *(file.id for file in child_files)}) == 3
    assert all(versions(db, child.id)[0]['original_name'] == '合同.pdf' for child in children)
    remove_material(db, original); db.commit()
    assert db.get(Upload, upload.id) and not db.get(Deletion, upload.storage_key)
    remove_material(db, child_files[0]); db.commit()
    assert len(versions(db, children[1].id)) == 1
    upload_id, key = upload.id, upload.storage_key
    remove_material(db, child_files[1]); db.commit()
    assert db.get(Upload, upload_id) is None and db.get(Deletion, key)
    assert service.get_annotation_project(db, parent_id).child_count == 2
    assert service.count_annotation_projects(db, parent_project_id=parent_id, order_scope="child") == 2
    assert len(service.get_annotation_projects(db, parent_project_id=parent_id, order_scope="child")) == 2


def test_batch_failure_rolls_back_rows_reservations_and_history(context):
    db, parent_id, language_id = context
    with pytest.raises(ValueError, match="语种不存在"):
        service.create_annotation_children(db, parent_id, [item(language_id), item(uuid4())], None, "rollback-key")
    db.rollback()
    assert service.get_annotation_project(db, parent_id).child_count == 0
    children = service.create_annotation_children(db, parent_id, [item(language_id)], None, "after-rollback")
    assert children[0].child_sequence_no == 1


def test_no_nested_children_no_manual_numbers_no_parent_delete(context):
    db, parent_id, language_id = context
    child = service.create_annotation_children(db, parent_id, [item(language_id)], None, "constraints-key")[0]
    with pytest.raises(ValueError, match="不能继续"):
        service.create_annotation_children(db, child.id, [item(language_id)], None, "nested-key")
    db.rollback()
    with pytest.raises(ValueError, match="不允许手动"):
        service.update_annotation_project_order_no(db, child.id, "AP-CHILD-EDIT", "测试", None, None)
    db.rollback()
    with pytest.raises(ValueError, match="不能修改"):
        service.update_annotation_project_order_no(db, parent_id, "AP-PARENT-EDIT", "测试", None, None)
    db.rollback()
    with pytest.raises(service.AnnotationProjectDeleteConflict, match="全部子订单"):
        service.delete_annotation_project(db, parent_id)
    db.rollback()


def test_delete_never_reuses_sequence(context):
    db, parent_id, language_id = context
    child = service.create_annotation_children(db, parent_id, [item(language_id)], None, "delete-first")[0]
    number = child.order_no
    assert service.delete_annotation_project(db, child.id)
    second = service.create_annotation_children(db, parent_id, [item(language_id)], None, "delete-second")[0]
    assert second.child_sequence_no == 2
    assert db.query(ProjectOrderNoReservation).filter_by(order_no=number).count() == 1
    assert service.delete_annotation_project(db, second.id)
    service.update_annotation_project_order_no(db, parent_id, "AP-RENAMED-" + uuid4().hex[:8].upper(), "测试删除后改号", None, None)
    third = service.create_annotation_children(db, parent_id, [item(language_id)], None, "after-parent-rename")[0]
    assert third.child_sequence_no == 3


def test_dot_numbering_keeps_legacy_and_deleted_sequences(context):
    db, parent_id, language_id = context
    parent = service.get_annotation_project(db, parent_id)
    for suffix in ('-S007', '.009'):
        service.reserve_annotation_order_no(db, project_id=uuid4(),
            order_no=parent.order_no + suffix, assignment_source='historical_fixture', assigned_by=None)
    db.commit()
    child = service.create_annotation_children(db, parent_id, [item(language_id)], None, 'dot-numbering')[0]
    assert child.order_no == parent.order_no + '.010'
    assert child.child_sequence_no == 10
    service.delete_annotation_project(db, child.id)
    replacement = service.create_annotation_children(db, parent_id, [item(language_id)], None, 'dot-replacement')[0]
    assert replacement.order_no == parent.order_no + '.011'


def test_copied_fields_remain_independent_after_parent_and_child_edits(context):
    db, parent_id, language_id = context
    child = service.create_annotation_children(db, parent_id, [item(language_id, task_description="独立任务")], None, "sync-key")[0]
    old_version = child.updated_at
    parent = service.get_annotation_project(db, parent_id)
    service.update_annotation_project(db, parent_id, update_payload(parent, contact_name="新联系人", task_description="新母任务"))
    child = service.get_annotation_project(db, child.id)
    assert child.contact_name == "原联系人" and child.task_description == "独立任务"
    assert child.updated_at == old_version
    service.update_annotation_project(db, child.id, update_payload(child, customer_order_no="CHILD-EDITED", contact_name="子单联系人"))
    assert service.get_annotation_project(db, parent_id).contact_name == "新联系人"
    assert service.get_annotation_project(db, child.id).customer_order_no == "CHILD-EDITED"
    service.update_annotation_project_status(db, child.id, "project_in_progress", datetime.now(), "子单开始", None)
    parent = service.get_annotation_project(db, parent_id)
    assert parent.project_status == "initial_consultation"
    assert parent.child_status_counts == {"project_in_progress": 1}
    assert db.query(AnnotationProjectStatusHistory).filter_by(project_id=child.id).count() == 2
    assert db.query(AnnotationProjectStatusHistory).filter_by(project_id=parent_id).count() == 1


def test_parallel_creations_are_unique(context, sessions):
    db, parent_id, language_id = context
    db.rollback()
    def create(index):
        with sessions() as concurrent:
            return service.create_annotation_children(concurrent, parent_id, [item(language_id)], None, f"parallel-{index}")[0].order_no
    with ThreadPoolExecutor(max_workers=4) as executor:
        numbers = list(executor.map(create, range(4)))
    assert len(set(numbers)) == 4
    assert service.get_annotation_project(db, parent_id).child_count == 4


def test_parallel_parent_rename_and_child_create_do_not_deadlock(context, sessions):
    db, parent_id, language_id = context
    db.rollback()
    new_number = "AP-CONCURRENT-" + uuid4().hex[:8].upper()
    def rename():
        with sessions() as concurrent:
            try:
                service.update_annotation_project_order_no(concurrent, parent_id, new_number, "并发改号验收", None, None)
                return True
            except ValueError as error:
                concurrent.rollback()
                assert "已有子订单" in str(error)
                return False
    def create():
        with sessions() as concurrent:
            return service.create_annotation_children(concurrent, parent_id, [item(language_id)], None, "parallel-rename-create")[0].order_no
    with ThreadPoolExecutor(max_workers=2) as executor:
        renamed = executor.submit(rename)
        created = executor.submit(create)
        number = created.result(timeout=20)
        success = renamed.result(timeout=20)
    parent = service.get_annotation_project(db, parent_id)
    assert number.startswith(parent.order_no + ".")
    assert (parent.order_no == new_number) == success


def test_api_scopes_atomic_failure_and_independent_client_fields(context, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import annotation_projects as routes, auth
    db, parent_id, language_id = context
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: SimpleNamespace(id=None)
    monkeypatch.setattr(auth, "user_has_permission", lambda *_args: True)
    monkeypatch.setattr(auth, "get_user_permission_codes", lambda *_args: {"projects:read", "projects:write"})
    with TestClient(app) as client:
        second = add_test_language(db)
        new_payload = {'project_name':'接口自动生成母单','language_items':[
            {'source_language_id':str(language_id)},{'source_language_id':str(second)}]}
        created = client.post('/projects/annotation/',json=new_payload,headers={'X-Idempotency-Key':'api-auto-parent'})
        assert created.status_code == 201, created.text
        automatic = created.json()
        assert automatic['auto_created_child_count'] == automatic['child_count'] == 2
        assert automatic['direction_summary']['missing_directions'] == []
        retry = client.post('/projects/annotation/',json=new_payload,headers={'X-Idempotency-Key':'api-auto-parent'}).json()
        assert retry['id'] == automatic['id'] and retry['child_count'] == 2 and retry['auto_created_child_count'] == 0
        saved = client.put(f"/projects/annotation/{automatic['id']}",json={**new_payload,'expected_updated_at':automatic['updated_at']})
        assert saved.status_code == 200, saved.text
        assert saved.json()['auto_created_child_count'] == 0 and saved.json()['child_count'] == 2
        prefix = f"/projects/annotation/{parent_id}/children"
        payload = {"language_items": [{"source_language_id": str(language_id)}], "project_name": "接口子单"}
        response = client.post(prefix, json=payload, headers={"X-Idempotency-Key": "api-child-key"})
        assert response.status_code == 201, response.text
        child = response.json()
        assert child["parent_project_id"] == str(parent_id)
        assert client.post(prefix, json=payload, headers={"X-Idempotency-Key": "api-child-key"}).json()["id"] == child["id"]
        page = client.get("/projects/annotation/page", params={"order_scope": "child", "parent_project_id": str(parent_id)}).json()
        count = client.get("/projects/annotation/count", params={"order_scope": "child", "parent_project_id": str(parent_id)}).json()
        assert page["total"] == count["total"] == 1
        assert page["items"][0]["parent_order_no"] == child["parent_order_no"]
        assert client.get("/projects/annotation/page", params={"order_scope": "invalid"}).status_code == 422
        illegal = client.patch(f"/projects/annotation/{child['id']}/text-field", json={"field": "contact_name", "value": "篡改", "expected_updated_at": child["updated_at"]})
        assert illegal.status_code == 200
        failed = client.post(prefix + "/batch", json={"items": [payload, {"language_items": [{"source_language_id": str(uuid4())}]}]}, headers={"X-Idempotency-Key": "api-invalid-batch"})
        assert failed.status_code == 400
        assert client.get(prefix).json()["total"] == 1
        assert service.get_annotation_project(db, parent_id).contact_name == "原联系人"
        monkeypatch.setattr(auth, "user_has_permission", lambda _db, _id, permission: permission == "projects:read")
        monkeypatch.setattr(auth, "get_user_permission_codes", lambda *_args: {"projects:read"})
        assert client.get(prefix).status_code == 200
        assert client.post(prefix, json=payload, headers={"X-Idempotency-Key": "read-only-key"}).status_code == 403
