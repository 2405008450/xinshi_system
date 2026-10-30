"""仅内存 SQLite 验证客户经理默认、原因、历史和事务；不访问业务库。"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.test_chat_participant_access import environment
from project_client_manager import ProjectClientManagerChange, apply, attach, history, manager_name_expression


@pytest.mark.parametrize('kind', ['translation', 'interpretation', 'recruitment'])
def test_default_and_change_require_reason_with_immutable_snapshots(environment, kind):
    db, (owner, member, _) = environment
    project = SimpleNamespace(id=uuid4(), client_manager_id=None, client_manager_name=None, client=None)
    apply(db, kind, project, None, None, owner.id, creating=True)
    db.commit()
    first = db.query(ProjectClientManagerChange).one()
    assert first.new_manager_id == owner.id
    assert first.actor_name == 'owner'
    from annotation_progress_time import business_datetime
    assert business_datetime(first.changed_at).utcoffset().total_seconds() == 28800
    for reason in [None, '', '   ']:
        with pytest.raises(ValueError, match='调整原因'):
            apply(db, kind, project, member.id, reason, owner.id)
        db.rollback()
    apply(db, kind, project, member.id, '客户交接', owner.id)
    db.commit()
    second = db.query(ProjectClientManagerChange).filter_by(revision=2).one()
    assert second.previous_manager_id == owner.id
    assert second.new_manager_id == member.id
    assert second.reason == '客户交接'
    apply(db, kind, project, member.id, None, owner.id)
    db.commit()
    assert db.query(ProjectClientManagerChange).count() == 2
    member.full_name = '更名后的人员'
    db.commit()
    assert first.new_manager_name == 'owner'
    assert second.new_manager_name == 'member'
    apply(db, kind, project, None, '解除分配', owner.id)
    db.commit()
    assert db.query(ProjectClientManagerChange).filter_by(revision=3).one().new_manager_id is None
    assert db.scalar(select(manager_name_expression(kind, project.id, '历史客户经理'))) == ''


def test_creation_override_and_invalid_user_are_rejected(environment):
    db, (owner, member, _) = environment
    project = SimpleNamespace(id=uuid4(), client=None)
    with pytest.raises(ValueError, match='调整原因'):
        apply(db, 'translation', project, member.id, None, owner.id, creating=True)
    with pytest.raises(ValueError, match='启用'):
        apply(db, 'translation', project, uuid4(), '无效人员', owner.id, creating=True)
    member.is_active = False
    with pytest.raises(ValueError, match='启用'):
        apply(db, 'translation', project, member.id, '离职', owner.id, creating=True)
    assert db.query(ProjectClientManagerChange).count() == 0


def test_save_rollback_and_history_pagination(environment):
    db, (owner, member, _) = environment
    from models import TranslationProject
    project = TranslationProject(id=uuid4(), order_no='TP-TEST', project_name='隔离测试')
    db.add(project); db.flush()
    apply(db, 'translation', project, None, None, owner.id, creating=True)
    db.commit()
    apply(db, 'translation', project, member.id, '模拟后续保存失败', owner.id)
    db.rollback()
    attach(db, 'translation', [project])
    assert project.client_manager_id == owner.id
    result = history('translation', project.id, skip=0, limit=1, db=db)
    assert result['total'] == 1
    assert result['items'][0]['changed_at'].endswith('+08:00')
    assert history('translation', project.id, skip=1, limit=1, db=db)['items'] == []


def test_migration_is_repeatable_and_only_creates_new_table():
    from sqlalchemy import create_engine, inspect
    from tools.apply_project_client_manager_migration import apply_migration
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection); apply_migration(connection)
        assert inspect(connection).get_table_names() == ['project_client_manager_change']
    engine.dispose()


@pytest.mark.parametrize('kind', ['translation', 'interpretation', 'annotation', 'recruitment'])
def test_actual_creation_services_default_to_writer(environment, monkeypatch, kind):
    """真实服务和会话，序号生成独立于 PostgreSQL 方言。"""
    from sqlalchemy import event
    from models import Base
    from annotation_schemas import AnnotationProjectCreate, AnnotationProjectUpdate
    from interpretation_schemas import InterpretationProjectCreate, InterpretationProjectUpdate
    from recruitment_schemas import RecruitmentProjectCreate, RecruitmentProjectUpdate
    from schemas import TranslationProjectCreate, TranslationProjectUpdate
    import annotation_service, interpretation_service, recruitment_service, crud
    db, (owner, member, _) = environment
    services = {
        'translation': (crud, 'generate_order_no', TranslationProjectCreate, crud.create_translation_project),
        'interpretation': (interpretation_service, 'generate_interpretation_order_no', InterpretationProjectCreate, interpretation_service.create_interpretation_project),
        'annotation': (annotation_service, 'generate_annotation_order_no', AnnotationProjectCreate, annotation_service.create_annotation_project),
        'recruitment': (recruitment_service, 'generate_recruitment_order_no', RecruitmentProjectCreate, recruitment_service.create_recruitment_project),
    }
    module, generator, schema, create = services[kind]
    monkeypatch.setattr(module, generator, lambda *args: {'translation':'TP','interpretation':'IP','annotation':'AP','recruitment':'HP'}[kind]+'-QA-001')
    def set_sqlite_id(mapper, connection, target):
        if hasattr(target, 'id') and target.id is None:
            target.id = uuid4()
    event.listen(Base, 'before_insert', set_sqlite_id, propagate=True)
    try:
        values = {'project_name': '隔离客户经理测试'}
        if kind == 'translation':
            values['created_by'] = owner.id
            project = create(db, schema(**values))
        else:
            project = create(db, schema(**values), owner.id)
        assert project.client_manager_id == owner.id
        if kind == 'annotation':
            from annotation_manager_change_models import AnnotationManagerChangeLog
            row = db.query(AnnotationManagerChangeLog).filter_by(project_id=project.id, manager_role='client_manager').one()
        else:
            row = db.query(ProjectClientManagerChange).filter_by(project_type=kind, project_id=project.id).one()
        assert row.new_manager_id == owner.id
        update_schema = {'translation': TranslationProjectUpdate, 'interpretation': InterpretationProjectUpdate,
                         'annotation': AnnotationProjectUpdate, 'recruitment': RecruitmentProjectUpdate}[kind]
        update_service = {'translation': crud.update_translation_project,
                          'interpretation': interpretation_service.update_interpretation_project,
                          'annotation': annotation_service.update_annotation_project,
                          'recruitment': recruitment_service.update_recruitment_project}[kind]
        values = {'project_name': '隔离客户经理测试', 'client_manager_id': member.id}
        with pytest.raises(ValueError, match='调整原因'):
            update_service(db, project.id, update_schema(**values), owner.id)
        db.rollback()
        reason_key = 'manager_change_reason' if kind == 'annotation' else 'client_manager_change_reason'
        values[reason_key] = '客户交接'
        updated = update_service(db, project.id, update_schema(**values), owner.id)
        assert updated.client_manager_id == member.id
        records = history(kind, project.id, skip=0, limit=20, db=db)
        assert records['total'] == 2
        assert records['items'][0]['previous_manager_name'] == 'owner'
        assert records['items'][0]['new_manager_name'] == 'member'
        assert records['items'][0]['reason'] == '客户交接'
    finally:
        event.remove(Base, 'before_insert', set_sqlite_id)
