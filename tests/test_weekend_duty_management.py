"""周末值班草稿隔离、同步锁定、跨月调整、固定日期；仅隔离 SQLite。"""
from datetime import date
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_monthly_shift import setup
from test_weekend_duty import payload
from test_weekly_shift_publication import version
import weekend_duty as duty
import weekend_duty_management as service
import weekend_duty_transfer as transfer


def test_publish_lock_edit_private_history_and_broadcast(environment,monkeypatch):
    import notification_ws
    db,(admin,person,other)=environment;setup(db,[admin,person,other]);events=[]
    monkeypatch.setattr(notification_ws,'broadcast_to_users',lambda users,event:events.append(event))
    saved=duty.save_plan(db,admin,'2026-11',payload(person))
    assert not events and service.overview(db,other,'2026-11')['assignments']==[]
    assert db.get(duty.WeekendDutyPlan,date(2026,11,1)) is None
    assert service.history(db,other,'2026-11',True)['total']==0
    synced=service.publish(db,admin,'2026-11',version(saved))
    assert not synced['can_edit'] and not synced['needs_sync'] and events[-1]['type']=='weekend_duty_published'
    assert service.overview(db,other,'2026-11')['assignments'][0]['date']=='2026-11-01'
    with pytest.raises(HTTPException):duty.save_plan(db,admin,'2026-11',payload(person,revision=synced['revision'],dates=()))
    service.enable_edit(db,admin,'2026-11',version(synced))
    saved=duty.save_plan(db,admin,'2026-11',payload(person,revision=synced['revision'],dates=('2026-11-07',)))
    assert saved['needs_sync'] and len(events)==1
    assert service.overview(db,other,'2026-11')['assignments'][0]['date']=='2026-11-01'
    assert service.history(db,other,'2026-11',True)['total']==2
    assert service.history(db,admin,'2026-11')['total']==4
    service.publish(db,admin,'2026-11',version(saved))
    assert service.overview(db,other,'2026-11')['assignments'][0]['date']=='2026-11-07'
    assert service.history(db,other,'2026-11',True)['total']==5
    with pytest.raises(HTTPException):service.publish(db,person,'2026-11',version(saved))


def test_fixed_dates_prospective_and_not_published_until_sync(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    settings=service.FixedWrite(revision=0,assignments=[{'user_id':person.id,'department':'customer','weekdays':[5]}])
    service.save_fixed(db,admin,settings)
    assert duty.get_plan(db,admin,'2026-09')['assignments']==[]
    plan=duty.get_plan(db,admin,'2026-11');assert len(plan['assignments'])==4
    assert all(row['fixed'] and date.fromisoformat(row['date']).weekday()==5 for row in plan['assignments'])
    assert service.overview(db,other,'2026-11')['assignments']==[]
    saved=duty.save_plan(db,admin,'2026-11',duty.DutyWrite(revision=0,assignments=[]))
    assert len(saved['assignments'])==4
    service.publish(db,admin,'2026-11',version(saved))
    service.save_fixed(db,admin,service.FixedWrite(revision=1,assignments=[]))
    assert duty.get_plan(db,admin,'2026-11')['assignments']==[]
    assert len(service.overview(db,other,'2026-11')['assignments'])==4


def transfer_payload(db,admin,source,target,operation):
    left=transfer.get_week(db,admin,source);right=transfer.get_week(db,admin,target)
    return transfer.DutyTransfer(source_week=source,target_week=target,operation=operation,versions={**left['versions'],**right['versions']},fixed_revision=left['fixed_revision'])


@pytest.mark.parametrize('operation',['copy','move','swap'])
def test_cross_month_sat_sun_atomic_transfer(environment,operation):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    duty.save_plan(db,admin,'2026-10',payload(person,dates=('2026-10-31',)))
    duty.save_plan(db,admin,'2026-11',duty.DutyWrite(revision=0,assignments=[
        {'user_id':person.id,'department':'customer','date':'2026-11-01'},
        {'user_id':other.id,'department':'customer','date':'2026-11-07'},
        {'user_id':other.id,'department':'customer','date':'2026-11-14'}]))
    result=transfer.transfer(db,admin,transfer_payload(db,admin,'2026-10-26','2026-11-02',operation))
    target=result['target']['assignments'];assert {(row['date'],row['user_id']) for row in target}=={('2026-11-07',str(person.id)),('2026-11-08',str(person.id))}
    source=result['source']['assignments']
    assert len(source)==(2 if operation=='copy' else 1 if operation=='swap' else 0)
    if operation=='swap':assert source[0]['date']=='2026-10-31' and source[0]['user_id']==str(other.id)
    assert any(row['date']=='2026-11-14' for row in duty.get_plan(db,admin,'2026-11')['assignments'])
    assert service.overview(db,person,'2026-11')['assignments']==[]


def test_stale_locked_month_and_fixed_preservation(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    duty.save_plan(db,admin,'2026-10',payload(person,dates=('2026-10-31',)))
    stale=transfer_payload(db,admin,'2026-10-26','2026-11-02','move')
    saved=duty.save_plan(db,admin,'2026-11',payload(other))
    with pytest.raises(HTTPException):transfer.transfer(db,admin,stale)
    assert len(duty.get_plan(db,admin,'2026-10')['assignments'])==1
    service.publish(db,admin,'2026-11',version(saved))
    with pytest.raises(HTTPException):transfer.transfer(db,admin,transfer_payload(db,admin,'2026-10-26','2026-11-02','move'))
    assert len(duty.get_plan(db,admin,'2026-10')['assignments'])==1
    service.enable_edit(db,admin,'2026-11',version(duty.get_plan(db,admin,'2026-11')))
    service.save_fixed(db,admin,service.FixedWrite(revision=0,assignments=[{'user_id':other.id,'department':'customer','weekdays':[5,6]}]))
    transfer.transfer(db,admin,transfer_payload(db,admin,'2026-10-26','2026-11-02','copy'))
    target=transfer.get_week(db,admin,'2026-11-02')['assignments']
    assert len([row for row in target if row.get('fixed')])==2
    assert len([row for row in target if not row.get('fixed')])==1


def test_migration_idempotent_preserves_existing(environment):
    from tools.apply_weekend_duty_management_migration import apply_migration
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    before=duty.save_plan(db,admin,'2026-11',payload(person))
    for model in (service.WeekendDutyPublication,service.WeekendDutyAudit,service.WeekendDutyFixedConfig):model.__table__.drop(db.connection())
    db.commit();assert not service.ready(db)
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert duty.get_plan(db,admin,'2026-11')==before


def test_removed_fixed_people_never_become_manual_copies(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_fixed(db,admin,service.FixedWrite(revision=0,assignments=[{'user_id':person.id,'department':'customer','weekdays':[5,6]}]))
    duty.save_plan(db,admin,'2026-11',duty.DutyWrite(revision=0,assignments=[]))
    service.save_fixed(db,admin,service.FixedWrite(revision=1,assignments=[]))
    assert duty.get_plan(db,admin,'2026-11')['assignments']==[]
    with pytest.raises(HTTPException) as error:transfer.transfer(db,admin,transfer_payload(db,admin,'2026-11-02','2026-11-09','copy'))
    assert error.value.status_code==422


def test_sync_relocks_after_edit_without_changes(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    saved=duty.save_plan(db,admin,'2026-11',payload(person))
    synced=service.publish(db,admin,'2026-11',version(saved))
    enabled=service.enable_edit(db,admin,'2026-11',version(synced))
    assert enabled['can_edit']
    assert not service.publish(db,admin,'2026-11',version(enabled))['can_edit']
