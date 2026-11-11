from datetime import datetime
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from test_chat_participant_access import environment, project


def test_business_windows_cover_weekend_and_manual_cutoff():
    from annotation_chat_ai import manual_range, scheduled_range

    monday = datetime(2026, 11, 9, 11)
    assert scheduled_range(monday.date()) == (datetime(2026, 11, 6), datetime(2026, 11, 9))
    after_holiday = datetime(2026, 10, 8, 11)
    assert scheduled_range(after_holiday.date()) == (datetime(2026, 9, 30), datetime(2026, 10, 8))
    assert manual_range('day', monday) == (datetime(2026, 11, 8), monday)
    assert manual_range('week', monday) == (datetime(2026, 11, 2, 11), monday)
    march = datetime(2026, 3, 31, 11)
    assert manual_range('month', march) == (datetime(2026, 2, 28, 11), march)
    assert manual_range('all', monday) == (None, monday)


def seed_message(db, row, sender, sequence, content, *, recalled=False):
    from models import ChatProjectMessage

    message = ChatProjectMessage(
        id=uuid4(), annotation_project_id=row.id, sender_user_id=sender.id, sender_name=sender.full_name,
        created_at=datetime(2026, 11, 8, 10), message_type='user', content=content, sequence_no=sequence,
        recalled_at=datetime(2026, 11, 8, 11) if recalled else None,
    )
    db.add(message)
    db.commit()
    return message


def add_member(db, row, user):
    from models import AnnotationChatMember

    db.add(AnnotationChatMember(project_id=row.id, user_id=user.id, following=True, last_read_sequence=0))
    db.commit()


def test_scheduled_jobs_once_per_workday_and_separate_rooms(environment, monkeypatch):
    import annotation_chat_ai as ai
    from annotation_chat_ai_inference import PROMPT
    from tools.apply_annotation_chat_ai_migration import apply_migration

    db, (owner, _, _) = environment
    bind = db.get_bind()
    ai.Job.__table__.drop(db.connection())
    apply_migration(db.connection())
    apply_migration(db.connection())
    db.commit()
    first = project(db, owner, 'AP-AI-FIRST')
    second = project(db, owner, 'AP-AI-SECOND')
    empty = project(db, owner, 'AP-AI-EMPTY')
    seed_message(db, first, owner, 1, '第一会话')
    seed_message(db, second, owner, 2, '第二会话')
    seed_message(db, empty, owner, 3, '撤回内容', recalled=True)
    moment = datetime(2026, 11, 9, 11)
    assert ai.enqueue_scheduled(db, moment.replace(hour=10)) == 0
    assert ai.enqueue_scheduled(db, moment) == 2
    assert ai.enqueue_scheduled(db, moment) == 0
    db.rollback()
    inputs = []

    def generate(payload):
        assert payload['action'] == 'annotation_chat'
        inputs.append(json.loads(payload['content'][len(PROMPT):]))
        return {'state': 'succeeded', 'result': '[{"category":"idea","summary":"讨论想法","sources":[1]}]'}

    monkeypatch.setattr(ai.thoughts_ai_service, 'transport', generate)
    factory = sessionmaker(bind=bind)
    for _ in range(2):
        job_id = ai.claim(db, moment, allow_scheduled=True)
        ai.process(factory, job_id)
    db.expire_all()
    jobs = db.scalars(select(ai.Job)).all()
    assert {job.project_id for job in jobs} == {first.id, second.id}
    assert all(job.state == 'succeeded' and job.results and not job.imports for job in jobs)
    assert sorted([entry['text'] for entry in items] for items in inputs) == [['第一会话'], ['第二会话']]


def test_manual_permissions_chunking_and_transactional_progress_import(environment, monkeypatch):
    import annotation_chat_ai as ai
    from annotation_chat_ai_inference import PROMPT
    from routers.annotation_chat_ai import add_progress, detail

    db, (owner, member, outsider) = environment
    allowed = project(db, owner, 'AP-AI-ALLOWED')
    other = project(db, outsider, 'AP-AI-OTHER')
    add_member(db, allowed, owner)
    add_member(db, allowed, member)
    seed_message(db, allowed, owner, 1, '客户要求、项目完成、质检情况。' * 360)
    seed_message(db, other, outsider, 2, '其他会话机密')
    monkeypatch.setattr(ai.thoughts_ai_service, 'enabled', lambda: True)
    monkeypatch.setattr(ai, 'business_now', lambda: datetime(2026, 11, 9, 11))
    monkeypatch.setattr(ai, 'user_has_permission', lambda db, user_id, permission: user_id == owner.id)

    with pytest.raises(HTTPException) as error:
        ai.enqueue_manual(db, allowed.id, member, 'all', True, False)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        ai.enqueue_manual(db, allowed.id, outsider, 'all', False, False)
    assert error.value.status_code == 404
    assert ai.enqueue_manual(db, allowed.id, owner, 'all', True, True) == {'queued': 1}
    inputs = []

    def generate(payload):
        inputs.append(payload['content'])
        assert len(payload['content']) <= 3500
        assert all('其他会话机密' not in line['text'] for line in json.loads(payload['content'][len(PROMPT):]))
        return {'state': 'succeeded', 'result': json.dumps([
            {'category': category, 'summary': f'{category} 要点', 'sources': [1]}
            for category in ('customer', 'project', 'annotator', 'assignment')
        ])}

    monkeypatch.setattr(ai.thoughts_ai_service, 'transport', generate)
    job_id = ai.claim(db, ai.business_now(), allow_scheduled=False)
    ai.process(sessionmaker(bind=db.get_bind()), job_id)
    assert len(inputs) > 1
    db.expire_all()
    run = detail(allowed.id, job_id, db, owner)
    assert run['state'] == 'succeeded'
    assert len(run['results']) == 4
    assert {entry['track'] for entry in run['imports']} == {'customer', 'project', 'annotator'}
    assert all(entry['actor_id'] == str(owner.id) and entry['at'].endswith('+08:00') for entry in run['imports'])
    for model in ai.PROGRESS_MODELS.values():
        rows = db.scalars(select(model)).all()
        assert len(rows) == 1 and rows[0].change_note.startswith('【AI 分析】')
    assert add_progress(allowed.id, job_id, db, owner)['created'] == 0
    with pytest.raises(HTTPException) as error:
        detail(allowed.id, job_id, db, outsider)
    assert error.value.status_code == 404


def test_truncation_subdivides_and_unknown_sources_are_rejected(monkeypatch):
    from annotation_chat_ai_inference import analyze_chunk, parse_results, thoughts_ai_service

    rows = [
        {'id': str(uuid4()), 'sender': '甲', 'time': '2026-11-08T11:00:00+08:00', 'text': '消息'}
        for _ in range(2)
    ]
    answers = iter([
        {'state': 'succeeded', 'truncated': True, 'result': '['},
        {'state': 'succeeded', 'result': '[{"category":"other","summary":"事项","sources":[1]}]'},
        {'state': 'succeeded', 'result': '[]'},
    ])
    monkeypatch.setattr(thoughts_ai_service, 'transport', lambda payload: next(answers))
    assert analyze_chunk(rows, lambda: None)[0]['sources'] == [rows[0]['id']]
    with pytest.raises(ValueError):
        parse_results('[{"category":"other","summary":"事项","sources":[3]}]', rows)
