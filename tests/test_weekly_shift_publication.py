"""草稿与工作台隔离、同步后修改、审计可见性；仅内存 SQLite。"""
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload
import weekly_shift as weekly
import weekly_shift_publication as service


def version(plan):return service.SyncWrite(revision=plan['revision'],publication_revision=plan['publication_revision'],fixed_revision=plan['fixed_revision'])


def test_draft_publish_edit_and_private_audit(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    first=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    assert first['needs_sync'] and not first['published']
    assert weekly.overview(db,person,'2026-10-26')['assignments']==[]
    assert weekly.my_plan(db,person,'2026-10-26')['assignment'] is None
    assert service.history(db,person,'2026-10-26',public=True)['total']==0
    synced=service.publish(db,admin,'2026-10-26',version(first))
    assert synced['published'] and not synced['can_edit'] and not synced['needs_sync']
    assert weekly.my_plan(db,person,'2026-10-26')['assignment']['shift']=='early'
    public=service.history(db,person,'2026-10-26',public=True)
    assert public['total']==2
    assert all(row['created_at'].utcoffset().total_seconds()==28800 for row in public['items'])
    with pytest.raises(HTTPException):weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=1,assignments=[]))
    enabled=service.enable_edit(db,admin,'2026-10-26',version(synced));assert enabled['can_edit']
    changed=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=1,assignments=payload(person,shift='late').assignments))
    assert changed['needs_sync'] and weekly.my_plan(db,person,'2026-10-26')['assignment']['shift']=='early'
    assert service.history(db,person,'2026-10-26',public=True)['total']==2
    service.publish(db,admin,'2026-10-26',version(changed))
    assert weekly.my_plan(db,person,'2026-10-26')['assignment']['shift']=='late'
    public=service.history(db,other,'2026-10-26',public=True)
    assert public['total']==5
    assert any(row['action']=='draft_save' and row['changes'][0]['after']['shift']=='late' for row in public['items'])


def test_noop_draft_fixed_config_and_stale_sync(environment):
    import fixed_shift
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    first=weekly.save_plan(db,admin,'2026-12-28',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    again=weekly.save_plan(db,admin,'2026-12-28',weekly.WeeklyPlanWrite(revision=1,assignments=payload(person).assignments))
    assert again['revision']==1 and service.history(db,admin,'2026-12-28')['total']==1
    fixed_shift.save_config(db,admin,payload(other,shift='late'))
    with pytest.raises(HTTPException) as error:service.publish(db,admin,'2026-12-28',version(first))
    assert error.value.status_code==409
    current=weekly.get_plan(db,admin,'2026-12-28');service.publish(db,admin,'2026-12-28',version(current))
    before=weekly.overview(db,person,'2026-12-28')['assignments']
    fixed_shift.save_config(db,admin,payload(other,revision=1,shift='early'))
    assert weekly.overview(db,person,'2026-12-28')['assignments']==before
    assert weekly.get_plan(db,admin,'2026-12-28')['needs_sync']
    with pytest.raises(HTTPException):service.publish(db,person,'2026-12-28',version(current))
    with pytest.raises(HTTPException):service.history(db,person,'2026-12-28')


def test_new_table_migration_is_idempotent_and_preserves_draft(environment):
    from tools.apply_weekly_shift_publication_migration import apply_migration
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    before=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    service.WeeklyShiftAudit.__table__.drop(db.connection());service.WeeklyShiftPublication.__table__.drop(db.connection());db.commit()
    assert not service.ready(db)
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert weekly.get_plan(db,admin,'2026-10-26')==before


def test_only_sync_broadcasts_and_api_guards(environment,monkeypatch):
    import notification_ws
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    events=[];monkeypatch.setattr(notification_ws,'broadcast_to_users',lambda users,event:events.append(event))
    plan=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    assert events==[]
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    with TestClient(app) as client:
        assert client.post('/monthly-shifts/weekly/sync?week=2026-10-26',json=version(plan).model_dump()).status_code==403
        assert client.get('/monthly-shifts/weekly/history?week=2026-10-26&public=true').json()['total']==0
        assert client.get('/monthly-shifts/weekly/history?week=2026-10-26&public=true&offset=-1').status_code==422
        service.publish(db,admin,'2026-10-26',version(plan))
        assert len(events)==1 and events[0]['type']=='weekly_shift_published'
        assert client.get('/monthly-shifts/weekly/history?week=2026-10-26&public=true').json()['total']==2


def test_legacy_public_rows_are_not_modified_by_new_private_drafts(environment):
    from datetime import date
    from chat_time import now
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    legacy=weekly.WeeklyShiftPlan(week_start=date(2026,10,26),revision=3,assignments=[{'user_id':str(person.id),'department':'customer','shift':'early'}],updated_by=admin.id,updated_at=now())
    db.add(legacy);db.commit()
    changed=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=3,assignments=payload(person,shift='late').assignments))
    assert changed['revision']==4
    db.refresh(legacy)
    assert legacy.revision==3 and legacy.assignments[0]['shift']=='early'
    assert weekly.overview(db,person,'2026-10-26')['assignments']==[]
    service.publish(db,admin,'2026-10-26',version(changed))
    db.refresh(legacy)
    assert legacy.revision==4 and legacy.assignments[0]['shift']=='late'
