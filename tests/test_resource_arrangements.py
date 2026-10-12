"""每日安排回归；只在显式启用的隔离/局域网数据库中运行。"""
import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from resource_development_schemas import ArrangementCellWrite, ArrangementCompletionWrite, ArrangementTargetWrite, ArrangementWrite


def test_target_validation_and_no_actor_spoofing():
    for payload in [dict(kind='request'), dict(kind='manual'), dict(kind='internal', language_id=uuid4()),
                    dict(kind='manual', language_id=uuid4(), request_id=uuid4())]:
        with pytest.raises(ValidationError):
            ArrangementTargetWrite(**payload)
    with pytest.raises(ValidationError):
        ArrangementCompletionWrite(revision=1, completed=True, completed_by=uuid4())
    platform = uuid4()
    with pytest.raises(ValidationError):
        ArrangementWrite(revision=0, cells=[dict(platform_id=platform), dict(platform_id=platform)])


def test_role_tag_normalization_and_limits():
    platform = uuid4()
    value = ArrangementCellWrite(platform_id=platform, role_tags=[' HR ', '', '客服', 'HR', '  '])
    assert value.role_tags == ['HR', '客服']
    assert 'role_tags' not in ArrangementCellWrite(platform_id=platform).model_fields_set
    assert 'role_tags' in ArrangementCellWrite(platform_id=platform, role_tags=[]).model_fields_set
    assert ArrangementCellWrite(platform_id=platform, role_tags=['岗' * 100]).role_tags == ['岗' * 100]
    for tags in [['岗' * 101], ['岗'] * 101, None, [123]]:
        with pytest.raises(ValidationError):
            ArrangementCellWrite(platform_id=platform, role_tags=tags)


def test_arrangement_business_clock_and_snapshot(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import business_time
    from resource_development_models import DevelopmentArrangementCell
    from resource_development_service import snapshot

    class ServerUtcClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 9, 9, 18, 43, 787825, tzinfo=timezone.utc)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(business_time, 'datetime', ServerUtcClock)
    stored = business_time.business_now()
    assert stored == datetime(2026, 10, 9, 17, 18, 43, 787825) and stored.tzinfo is None
    assert business_time.business_iso(stored) == '2026-10-09T17:18:43.787825+08:00'
    assert business_time.business_iso(datetime(2026, 10, 9, 9, 18, 43, 787825, tzinfo=timezone.utc)) == business_time.business_iso(stored)
    table = DevelopmentArrangementCell.__table__
    cell = SimpleNamespace(__table__=table, __tablename__=table.name, **{column.name: None for column in table.columns})
    cell.completed_at = stored
    assert snapshot(cell)['completed_at'] == '2026-10-09T17:18:43.787825+08:00'
    assert cell.completed_at == stored


def test_roles_legacy_write_completion_reorder_and_partial_update(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells, read_arrangement
    manager, owner, other, platforms, _ = context
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id, role_tags=[' HR ', '客服', 'HR'])
    day = save(db, context, cells=[payload, dict(platform_id=platforms[1].id, owner_id=other.id, role_tags=['译员'])])
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    first = next(c for c in get_cells(db, day) if c.platform_id == platforms[0].id)
    assert first.role_tags == ['HR', '客服'] and first.completed
    # 旧客户端只更新备注，不能意外清除岗位或完成信息。
    save(db, context, revision=day.revision, user=owner, cells=[dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='补充备注')])
    assert first.role_tags == ['HR', '客服'] and first.completed
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=['客服', 'HR'], remarks='补充备注')])
    assert first.completed and first.role_tags == ['客服', 'HR']
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=['译员'])])
    assert not first.completed and first.completed_at is None and first.completed_by is None
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=[])])
    assert first.role_tags == [] and not first.completed
    result = read_arrangement(db, manager, day.work_date)
    assert next(c for c in result['cells'] if c['platform_id'] == str(platforms[1].id))['role_tags'] == ['译员']


def test_role_only_carry_permissions_conflict_and_audit(db, context):
    from resource_arrangement_service import carry_preview, complete_arrangement, read_arrangement
    from resource_development_models import DevelopmentAudit
    manager, owner, other, platforms, _ = context
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id, role_tags=['HR', '英语客服'])
    day = save(db, context, cells=[payload])
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['targets'] == []
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    revision = day.revision
    preview = carry_preview(db, manager, date(2026, 10, 9))
    assert preview['cells'][0]['role_tags'] == ['HR', '英语客服']
    assert not preview['cells'][0]['completed'] and preview['cells'][0]['completed_at'] is None
    assert read_arrangement(db, manager, date(2026, 10, 9))['revision'] == 0
    for actor in [other]:
        with pytest.raises(HTTPException) as error:
            save(db, context, user=actor, revision=day.revision, cells=[payload | dict(role_tags=['越权'])])
        assert error.value.status_code == 403
    save(db, context, user=owner, revision=day.revision, cells=[payload | dict(role_tags=['法语译员'])])
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=revision, cells=[payload])
    assert error.value.status_code == 409
    changes = db.query(DevelopmentAudit).filter_by(entity_type='arrangement_cell').all()
    assert any(a.before.get('role_tags') == ['HR', '英语客服'] and a.after.get('role_tags') == ['法语译员'] for a in changes)


@pytest.fixture
def db():
    if os.getenv('RUN_RESOURCE_DEVELOPMENT_DB_TESTS') != '1':
        pytest.skip('数据库回归需在局域网显式启用')
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    assert engine.url.host in {'localhost', '127.0.0.1', '192.168.31.144'}, '禁止连接生产数据库'
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode='create_savepoint')
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def context(db, monkeypatch):
    from models import AppUser
    from interpretation_models import InterpretationLanguage
    from resource_development_models import DevelopmentOption
    import resource_arrangement_service as service
    users = [AppUser(id=uuid4(), username='arrange_'+uuid4().hex, full_name=name,
                     password_hash='test-no-login', is_active=True) for name in ['统筹', '负责人', '其他人员']]
    platforms = [DevelopmentOption(id=uuid4(), kind='platform', category='national', name='测试平台'+uuid4().hex) for _ in range(2)]
    language = InterpretationLanguage(id=uuid4(), label='方言'+uuid4().hex, language_type='dialect', is_active=True)
    db.add_all([*users, *platforms, language]); db.flush()
    monkeypatch.setattr(service, 'can_delegate', lambda _db, user: user.id == users[0].id)
    return users[0], users[1], users[2], platforms, language


def request_context(db, context, status='confirmed', child=False):
    from annotation_models import AnnotationProject
    from resource_request_models import ResourceRequest, ResourceRequestItem
    _, _, _, _, language = context
    parent = AnnotationProject(id=uuid4(), order_no='AP-'+uuid4().hex, project_name='母项目')
    db.add(parent); db.flush()
    project = parent
    if child:
        project = AnnotationProject(id=uuid4(), order_no=parent.order_no+'-01', project_name='精确子订单',
                                    parent_project_id=parent.id, child_sequence_no=1)
        db.add(project); db.flush()
    request = ResourceRequest(id=uuid4(), request_no='RR-'+uuid4().hex, source_type='annotation', request_category='annotation_trial',
                              annotation_project_id=project.id, source_project_name_snapshot=project.project_name,
                              request_detail='需求', demand_status=status, request_status='draft' if status == 'draft' else 'submitted')
    request.items = [ResourceRequestItem(id=uuid4(), sequence_no=1, source_language_id=language.id, required_count=1)]
    db.add(request); db.flush()
    return request, project


def save(db, context, revision=0, cells=None, day=date(2026, 10, 8), user=None, **kwargs):
    from resource_arrangement_service import save_arrangement
    manager, owner, _, platforms, _ = context
    if cells is None:
        cells = [dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='账号备注')]
    return save_arrangement(db, user or manager, day, ArrangementWrite(revision=revision, cells=cells, **kwargs))


def test_read_blank_is_read_only_and_ranges(db, context):
    from resource_arrangement_service import read_arrangement, list_arrangements
    from resource_development_models import DevelopmentArrangement
    manager, *_ = context
    result = read_arrangement(db, manager, date(2026, 10, 8))
    assert result['revision'] == 0 and result['cells'] == []
    assert db.query(DevelopmentArrangement).count() == 0
    save(db, context)
    assert list_arrangements(db, manager, date(2026, 10, 9), date(2026, 10, 10))['total'] == 0
    assert list_arrangements(db, manager, date(2026, 10, 8), date(2026, 10, 8))['total'] == 1
    with pytest.raises(HTTPException) as error:
        list_arrangements(db, manager, date(2026, 10, 9), date(2026, 10, 8))
    assert error.value.status_code == 422


def test_candidates_cancel_resend_language_adjustment_and_child(db, context):
    from resource_arrangement_service import arrangement_options, read_arrangement
    manager, owner, _, platforms, language = context
    first, child = request_context(db, context, child=True)
    second, _ = request_context(db, context)
    draft, _ = request_context(db, context, status='draft')
    targets = arrangement_options(db)['targets']
    assert {t['request_id'] for t in targets} == {str(first.id),str(second.id)}
    target = next(t for t in targets if t['request_id'] == str(first.id))
    assert target['project']['project_id'] == str(child.id) and target['project']['parent_project_id']
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id,
                   targets=[dict(kind='request', request_id=first.id, language_id=language.id), dict(kind='manual', language_id=language.id), dict(kind='internal')])
    day = save(db, context, cells=[payload])
    first.demand_status, first.request_status = 'cancelled', 'cancelled'; db.flush()
    assert {t['request_id'] for t in arrangement_options(db)['targets']} == {str(second.id)}
    row = read_arrangement(db, manager, day.work_date)['cells'][0]
    assert row['targets'][0]['inactive_reason'] == '需求已取消'
    assert row['projects'][0]['project_id'] == str(child.id)
    # 原有失效项可保存，不允许另一个账号新选取消的需求。
    save(db, context, revision=day.revision, cells=[payload])
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=day.revision, cells=[payload | {'platform_id':platforms[1].id}])
    assert error.value.status_code == 409
    first.demand_status, first.request_status = 'confirmed', 'submitted'; db.flush()
    assert str(first.id) in {t['request_id'] for t in arrangement_options(db)['targets']}
    first.items[0].source_language_id = None; db.flush(); db.expire(first, ['items'])
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['targets'][0]['inactive_reason'] == '需求语种已调整'
    assert str(draft.id) not in {t['request_id'] for t in arrangement_options(db)['targets']}


def test_partial_update_permissions_completion_and_revision(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells
    manager, owner, other, platforms, _ = context
    day = save(db, context, cells=[dict(platform_id=p.id, owner_id=u.id) for p,u in zip(platforms,[owner,other])], remarks='每日备注')
    complete_arrangement(db, manager, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    cells = get_cells(db, day)
    first = next(c for c in cells if c.platform_id == platforms[0].id)
    assert first.completed_by == manager.id and first.completed_by != first.owner_id and first.completed_at
    save(db, context, revision=day.revision, user=owner, cells=[dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='本人修改')])
    assert first.completed  # 仅修改备注不会重置完成。
    assert len(get_cells(db, day)) == 2 and day.remarks == '每日备注'
    for user,cells,remarks in [(owner,[dict(platform_id=platforms[1].id,owner_id=other.id)],None),
                               (owner,[dict(platform_id=platforms[0].id,owner_id=other.id)],None),
                               (owner,[], '越权每日备注')]:
        with pytest.raises(HTTPException) as error:
            save(db,context,revision=day.revision,user=user,cells=cells,remarks=remarks)
        assert error.value.status_code == 403
    old_revision = day.revision
    save(db, context, revision=day.revision, cells=[dict(platform_id=platforms[0].id,owner_id=other.id)])
    assert not first.completed and not first.completed_by and not first.completed_at
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=old_revision)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert error.value.status_code == 403


def test_carry_nearest_weekend_skip_invalid_and_no_persistence(db, context):
    from resource_arrangement_service import carry_preview, complete_arrangement, get_cells
    from resource_development_models import DevelopmentArrangement
    manager, owner, _, platforms, language = context
    request, _ = request_context(db,context)
    friday=date(2026,10,9); monday=date(2026,10,12)
    day=save(db,context,day=friday,remarks='沿用备注',cells=[dict(platform_id=platforms[0].id,owner_id=owner.id,
        targets=[dict(kind='request',request_id=request.id,language_id=language.id),dict(kind='manual',language_id=language.id)],remarks='账号备注')])
    complete_arrangement(db,manager,friday,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    owner.is_active=False; request.demand_status='cancelled'; db.flush()
    preview=carry_preview(db,manager,monday)
    assert preview['carried_from']==friday.isoformat() and preview['remarks']=='沿用备注'
    assert preview['cells'][0]['owner_id'] is None and not preview['cells'][0]['completed']
    assert preview['cells'][0]['completed_at'] is None and len(preview['warnings'])==2
    assert [t['kind'] for t in preview['cells'][0]['targets']]==['manual']
    assert db.query(DevelopmentArrangement).count()==1
    save(db,context,day=monday,cells=[],carried_from=friday)
    with pytest.raises(HTTPException) as error:
        carry_preview(db,manager,monday)
    assert error.value.status_code==409
    assert get_cells(db,day)[0].completed


def test_unassigned_cannot_complete_and_name_snapshots(db,context):
    from resource_arrangement_service import complete_arrangement,read_arrangement
    manager,owner,_,platforms,language=context
    day=save(db,context,cells=[dict(platform_id=platforms[0].id,owner_id=None,targets=[dict(kind='manual',language_id=language.id)])])
    with pytest.raises(HTTPException) as error:
        complete_arrangement(db,manager,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert error.value.status_code==422
    old_platform,old_language=platforms[0].name,language.label
    platforms[0].name='平台更名'; language.label='方言更名'; db.flush()
    cell=read_arrangement(db,manager,day.work_date)['cells'][0]
    assert cell['platform_name']==old_platform and cell['targets'][0]['label']==old_language


def test_empty_carry_and_unprivileged_create(db,context):
    from resource_arrangement_service import carry_preview
    manager,owner,*_=context
    with pytest.raises(HTTPException) as error:
        carry_preview(db,manager,date(2026,10,8))
    assert error.value.status_code==404
    with pytest.raises(HTTPException) as error:
        save(db,context,user=owner)
    assert error.value.status_code==403


def test_stopped_language_candidates_and_carry(db,context):
    from resource_arrangement_service import arrangement_options,carry_preview,read_arrangement
    manager,owner,_,platforms,language=context
    request,_=request_context(db,context)
    day=save(db,context,cells=[dict(platform_id=platforms[0].id,owner_id=owner.id,
        targets=[dict(kind='request',request_id=request.id,language_id=language.id)])])
    language.is_active=False; db.flush()
    assert arrangement_options(db)['targets']==[]
    assert read_arrangement(db,manager,day.work_date)['cells'][0]['targets'][0]['inactive_reason']=='语种已停用'
    preview=carry_preview(db,manager,date(2026,10,9))
    assert preview['cells'][0]['targets']==[] and preview['warnings']


def test_all_request_language_positions_are_candidates(db,context):
    from interpretation_models import InterpretationLanguage
    from resource_request_models import ResourceRequestItemExtraLanguage
    from resource_arrangement_service import arrangement_options
    request,_=request_context(db,context)
    extras=[InterpretationLanguage(id=uuid4(),label='多语种'+uuid4().hex,language_type='language',is_active=True) for _ in range(3)]
    db.add_all(extras);db.flush()
    request.items[0].target_language_id=extras[0].id
    request.items[0].extra_languages=[ResourceRequestItemExtraLanguage(sequence_no=i,language_id=l.id) for i,l in enumerate(extras[1:],start=3)]
    db.flush();db.expire(request,['items'])
    assert {t['language_id'] for t in arrangement_options(db)['targets']}=={str(context[4].id),*(str(l.id) for l in extras)}


def test_manual_projects_and_completion_reopen(db,context):
    from resource_arrangement_service import complete_arrangement,get_cells,read_arrangement
    manager,owner,_,platforms,_=context
    _,project=request_context(db,context,child=True)
    cell=dict(platform_id=platforms[0].id,owner_id=owner.id,projects=[dict(source_type='annotation',project_id=project.id)])
    day=save(db,context,cells=[cell])
    complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert get_cells(db,day)[0].completed_by==owner.id
    complete_arrangement(db,manager,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=False))
    assert not get_cells(db,day)[0].completed_at
    read=read_arrangement(db,manager,day.work_date)['cells'][0]
    assert read['manual_projects'][0]['project_id']==str(project.id)
    complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    save(db,context,revision=day.revision,cells=[cell | {'projects':[]}])
    assert not get_cells(db,day)[0].completed


def test_http_routes_permissions_and_incremental_save(db,context,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    import routers.auth as auth
    from routers.resource_development import router
    manager,owner,other,platforms,_=context
    current={'user':manager,'codes':['talents:read','talents:write']}
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *_:current['codes'])
    app=FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:current['user']
    with TestClient(app) as client:
        path='/resource-development/arrangements/2026-10-08'
        assert client.get(path).json()['revision']==0
        created=client.put(path,json={'revision':0,'cells':[{'platform_id':str(platforms[0].id),'owner_id':str(owner.id)}]})
        assert created.status_code==200,created.text
        current.update(user=owner,codes=['talents:read'])
        assert client.get(path).status_code==200
        assert client.patch(path+f'/cells/{platforms[0].id}/completion',json={'revision':1,'completed':True}).status_code==403
        current['codes'].append('talents:write')
        complete=client.patch(path+f'/cells/{platforms[0].id}/completion',json={'revision':1,'completed':True})
        assert complete.status_code==200,complete.text
        assert complete.json()['cells'][0]['completed_by']==str(owner.id)
        assert complete.json()['cells'][0]['completed_at'].endswith('+08:00')
        assert complete.json()['updated_at'].endswith('+08:00')
        assert client.put(path,json={'revision':1,'cells':[]}).status_code==409
        assert client.put(path,json={'revision':2,'cells':[{'platform_id':str(platforms[0].id),'owner_id':str(other.id)}]}).status_code==403
        current['codes']=[]
        assert client.get(path).status_code==403


def assign(db, context, request, accounts, revision=0, day=date(2026, 10, 12), user=None):
    from resource_arrangement_service import assign_request
    from resource_development_schemas import RequestArrangementWrite
    return assign_request(db, user or context[0], request.id, day,
                          RequestArrangementWrite(revision=revision, platform_ids=accounts))


def test_request_batch_assignment_preserves_other_work_and_is_idempotent(db, context):
    from resource_arrangement_service import get_cells, list_arrangement_requests, arrangement_request_detail, read_arrangement
    manager, owner, _, platforms, language = context
    request, project = request_context(db, context, child=True)
    other_request, _ = request_context(db, context)
    day = save(db, context, day=date(2026, 10, 12), remarks='每日备注', cells=[{
        'platform_id': platforms[0].id, 'owner_id': owner.id, 'role_tags': ['HR'], 'remarks': '账号备注',
        'projects': [{'source_type': 'annotation', 'project_id': project.id}],
        'targets': [{'kind': 'request', 'request_id': other_request.id, 'language_id': language.id}],
    }])
    day = assign(db, context, request, [p.id for p in platforms], day.revision)
    first = next(c for c in get_cells(db, day) if c.platform_id == platforms[0].id)
    assert first.owner_id == owner.id and first.role_tags == ['HR'] and first.remarks == '账号备注'
    assert first.projects[0]['project_id'] == str(project.id) and day.remarks == '每日备注'
    assert len(first.targets) == 2
    version = day.revision
    day = assign(db, context, request, [p.id for p in platforms], version)
    assert day.revision == version
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 2
    assert len(list_arrangement_requests(db, keyword=project.order_no)['items']) == 1
    assert list_arrangement_requests(db, keyword='精确子订单')['items'][0]['id'] == str(request.id)
    rendered = read_arrangement(db, manager, day.work_date)
    assert all(any(p['project_id'] == str(project.id) for p in c['projects']) for c in rendered['cells'])
    day = assign(db, context, request, [platforms[1].id], day.revision)
    assert len(first.targets) == 1 and first.targets[0]['request_id'] == str(other_request.id)
    assert first.projects[0]['project_id'] == str(project.id)
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 1


def test_request_without_language_and_multiple_requests_for_same_project(db, context):
    from resource_arrangement_service import get_cells, arrangement_request_detail, carry_preview
    from resource_request_models import ResourceRequest
    request, project = request_context(db, context)
    request.items = []
    second = ResourceRequest(id=uuid4(), request_no='RR-'+uuid4().hex, source_type='annotation',
                             request_category='annotation_formal', annotation_project_id=project.id,
                             source_project_name_snapshot=project.project_name,
                             request_detail='无语种项目需求', demand_status='confirmed', request_status='submitted')
    db.add(second); db.flush()
    account = context[3][0].id
    day = assign(db, context, request, [account])
    day = assign(db, context, second, [account], day.revision)
    assert len(get_cells(db, day)[0].targets) == 2
    day = assign(db, context, request, [], day.revision)
    assert get_cells(db, day)[0].targets[0]['request_id'] == str(second.id)
    assert arrangement_request_detail(db, request.id)['arrangements'] == []
    preview = carry_preview(db, context[0], date(2026, 10, 13))
    assert preview['cells'][0]['targets'][0]['request_id'] == str(second.id)
    second.demand_status = 'cancelled'; db.flush()
    detail = arrangement_request_detail(db, second.id)
    assert detail['arrangements'][0]['active'] is False
    assert carry_preview(db, context[0], date(2026, 10, 13))['cells'][0]['targets'] == []


def test_request_assignment_permissions_conflicts_and_cancelled(db, context):
    request, _ = request_context(db, context)
    account = context[3][0].id
    for user in context[1:3]:
        with pytest.raises(HTTPException) as error:
            assign(db, context, request, [account], user=user)
        assert error.value.status_code == 403
    day = assign(db, context, request, [account])
    with pytest.raises(HTTPException) as error:
        assign(db, context, request, [], 0)
    assert error.value.status_code == 409
    request.demand_status = 'cancelled'; db.flush()
    with pytest.raises(HTTPException) as error:
        assign(db, context, request, [account], day.revision)
    assert error.value.status_code == 409


def test_request_list_pagination_drafts_and_live_project_names(db, context):
    from resource_arrangement_service import list_arrangement_requests
    values = [request_context(db, context) for _ in range(7)]
    draft, _ = request_context(db, context, status='draft')
    values[0][0].demand_status = 'cancelled'
    values[1][1].project_name = '新名称专用关键字'; db.flush()
    page = list_arrangement_requests(db)
    assert page['total'] == 6 and len(page['items']) == 5
    following = list_arrangement_requests(db, skip=5)
    assert len(following['items']) == 1
    assert set(r['id'] for r in page['items']).isdisjoint(r['id'] for r in following['items'])
    assert list_arrangement_requests(db, keyword='新名称专用关键字')['total'] == 1
    assert list_arrangement_requests(db, keyword=draft.request_no)['total'] == 0


def test_request_assignment_resets_completion_and_preserves_it_on_repeat(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells
    request, _ = request_context(db, context)
    platform = context[3][0]
    day = save(db, context, day=date(2026, 10, 12), cells=[dict(platform_id=platform.id, owner_id=context[1].id)])
    complete_arrangement(db, context[1], day.work_date, platform.id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    day = assign(db, context, request, [platform.id], day.revision)
    assert not get_cells(db, day)[0].completed
    complete_arrangement(db, context[1], day.work_date, platform.id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    revision = day.revision
    assign(db, context, request, [platform.id], revision)
    assert get_cells(db, day)[0].completed and day.revision == revision


def test_request_assignment_http_and_snapshot_validation(db, context, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    import routers.auth as auth
    request, _ = request_context(db, context)
    codes = ['talents:read', 'talents:write']
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda *_: codes)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: context[0]
    with TestClient(app) as client:
        base = '/resource-development/arrangement-requests'
        assert client.get(base).json()['total'] == 1
        path = f'{base}/{request.id}/dates/2026-10-12'
        payload = dict(revision=0, platform_ids=[str(p.id) for p in context[3]])
        assert client.put(path, json=payload | {'project_name': '伪造快照'}).status_code == 422
        assert client.put(path, json=payload | {'platform_ids': payload['platform_ids'] * 2}).status_code == 422
        response = client.put(path, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['updated_at'].endswith('+08:00')
        assert len(client.get(f'{base}/{request.id}').json()['arrangements']) == 2
        codes.remove('talents:write')
        assert client.put(path, json=payload).status_code == 403


def test_sent_project_request_enters_arrangement_queue(db, context):
    from resource_arrangement_service import list_arrangement_requests, arrangement_request_detail
    from resource_request_service import send_resource_request
    request, project = request_context(db, context, status='draft', child=True)
    assert list_arrangement_requests(db)['total'] == 0
    send_resource_request(db, request.id, context[0].id)
    row = list_arrangement_requests(db)['items'][0]
    assert row['id'] == str(request.id) and row['order_no'] == project.order_no
    assign(db, context, request, [p.id for p in context[3]])
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 2
