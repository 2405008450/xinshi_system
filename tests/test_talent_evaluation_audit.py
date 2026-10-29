from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, select
from sqlalchemy.orm import Session

from talent_evaluation_audit import TalentEvaluationChange, evaluation_snapshot, latest_evaluations, record_evaluation_changes


@pytest.fixture
def audit_db():
    engine = create_engine('sqlite:///:memory:')
    meta = MetaData()
    people = Table('resource_person', meta, Column('id', Uuid, primary_key=True))
    users = Table('app_user', meta, Column('id', Uuid, primary_key=True))
    TalentEvaluationChange.__table__.to_metadata(meta)
    meta.create_all(engine)
    with Session(engine) as db:
        person=SimpleNamespace(id=uuid4(), overall_score=8, overall_rating='旧评价')
        actor=SimpleNamespace(id=uuid4(), username='actual-account', full_name='展示姓名')
        db.execute(people.insert().values(id=person.id))
        db.execute(users.insert().values(id=actor.id))
        yield db, person, actor
    engine.dispose()


def test_changes_record_authenticated_account_values_and_business_time(audit_db):
    db, person, actor = audit_db
    before=evaluation_snapshot(person)
    person.overall_score=9
    person.overall_rating='新评价'
    record_evaluation_changes(db,person,before,actor)
    db.flush()
    event=db.scalars(select(TalentEvaluationChange)).one()
    assert event.actor_account=='actual-account'
    assert event.before_values=={'overall_score':8,'overall_rating':'旧评价'}
    assert event.after_values=={'overall_score':9,'overall_rating':'新评价'}
    assert latest_evaluations(db,person.id)['overall']['created_at'].endswith('+08:00')
    record_evaluation_changes(db,person,evaluation_snapshot(person),actor)
    db.flush()
    assert len(db.scalars(select(TalentEvaluationChange)).all())==1


def test_clear_preserves_history_and_no_fabricated_default_grade(audit_db):
    db,person,actor=audit_db
    before=evaluation_snapshot(person)
    person.overall_score=None
    person.overall_rating=None
    person.talent_grade='pending'
    record_evaluation_changes(db,person,before,actor)
    db.flush()
    events=db.scalars(select(TalentEvaluationChange)).all()
    assert [event.group_key for event in events]==['overall']
    assert events[0].after_values=={'overall_score':None,'overall_rating':None}


def test_profile_scores_audited_and_failed_transaction_rolls_back(audit_db):
    db,person,actor=audit_db
    db.commit()
    before=evaluation_snapshot(person)
    person.written_profile=SimpleNamespace(quality_score='优秀')
    person.interpretation_profile=SimpleNamespace(interpretation_level='高级',quality_score='9',evaluation_summary='合格')
    record_evaluation_changes(db,person,before,actor)
    db.flush()
    assert {row.group_key for row in db.scalars(select(TalentEvaluationChange)).all()}=={'written_profile','interpretation_profile'}
    db.rollback()
    assert db.scalars(select(TalentEvaluationChange)).all()==[]


def test_audit_migration_creates_only_new_table_and_is_repeatable(audit_db):
    from sqlalchemy import inspect, text
    from tools.apply_talent_evaluation_audit_migration import apply_migration
    db,person,actor=audit_db
    db.execute(text('DROP TABLE talent_evaluation_change'))
    apply_migration(db.connection())
    apply_migration(db.connection())
    assert inspect(db.connection()).has_table('talent_evaluation_change')
    record_evaluation_changes(db,person,{},actor)
    db.flush()
    assert db.scalars(select(TalentEvaluationChange)).one().actor_account==actor.username
