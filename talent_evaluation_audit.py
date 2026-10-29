"""人才评价的自动署名、UTC+8 时间及不可由客户端改写的修改历史。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import mapped_column

from business_time import BUSINESS_TIMEZONE, business_iso
from models import Base

EVALUATION_GROUPS = {
    'talent_grade': ('人才分级', ('talent_grade',)),
    'overall': ('标注总体评价', ('overall_score', 'overall_rating')),
    'cooperation': ('配合度', ('cooperation_level', 'cooperation_note')),
    'punctuality': ('守时度', ('punctuality_level', 'punctuality_note')),
    'audio_annotation': ('音频标注表现', ('audio_annotation_score', 'audio_annotation_evaluation')),
    'non_audio_annotation': ('非音频标注表现', ('non_audio_annotation_score', 'non_audio_annotation_evaluation')),
    'collection': ('采集表现', ('collection_score', 'collection_evaluation')),
    'interpretation': ('口译评价', ('interpretation_rating', 'interpretation_rating_note', 'interpretation_domains')),
    'written_translation': ('笔译评价', ('written_translation_score', 'written_translation_evaluation')),
    'written_profile': ('笔译能力评价', ('written_profile.quality_score',)),
    'interpretation_profile': ('口译能力评价', ('interpretation_profile.interpretation_level', 'interpretation_profile.quality_score', 'interpretation_profile.evaluation_summary')),
    'annotation_profile': ('标注能力评价', ('annotation_profile.quality_score', 'annotation_profile.remarks')),
}


class TalentEvaluationChange(Base):
    __tablename__ = 'talent_evaluation_change'
    __table_args__ = (Index('ix_talent_evaluation_change_person_group_time', 'person_id', 'group_key', 'created_at', 'id'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    person_id = mapped_column(Uuid, ForeignKey('resource_person.id', ondelete='CASCADE'), nullable=False)
    group_key = mapped_column(String(40), nullable=False)
    actor_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    actor_account = mapped_column(String(255), nullable=False)
    before_values = mapped_column(JSON, nullable=False)
    after_values = mapped_column(JSON, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)


def _value(person, path):
    value = person
    for key in path.split('.'):
        value = getattr(value, key, None) if value is not None else None
    return value.strip() or None if isinstance(value, str) else value


def evaluation_snapshot(person):
    return {key: {field: _value(person, field) for field in fields}
            for key, (_, fields) in EVALUATION_GROUPS.items()}


def _meaningful(values):
    return any(value is not None and value != '' and value != 'pending' for value in values.values())


def record_evaluation_changes(db, person, before, actor):
    after = evaluation_snapshot(person)
    now = datetime.now(BUSINESS_TIMEZONE)
    for key, values in after.items():
        previous = before.get(key, dict.fromkeys(values))
        if previous == values or not (_meaningful(previous) or _meaningful(values)):
            continue
        db.add(TalentEvaluationChange(
            person_id=person.id, group_key=key, actor_id=getattr(actor, 'id', None),
            actor_account=getattr(actor, 'username', None) or '系统',
            before_values=previous, after_values=values, created_at=now,
        ))


def latest_evaluations(db, person_id):
    from sqlalchemy import func
    ranked = db.query(
        TalentEvaluationChange.group_key, TalentEvaluationChange.actor_account, TalentEvaluationChange.created_at,
        func.row_number().over(partition_by=TalentEvaluationChange.group_key,
                               order_by=(TalentEvaluationChange.created_at.desc(), TalentEvaluationChange.id.desc())).label('position'),
    ).filter(TalentEvaluationChange.person_id == person_id).subquery()
    return {row.group_key: {'actor_account': row.actor_account, 'created_at': business_iso(row.created_at)}
            for row in db.query(ranked).filter(ranked.c.position == 1).all()}


def evaluation_history(db, person_id, group_key, *, skip=0, limit=10):
    from fastapi import HTTPException
    from resource_models import ResourcePerson
    from talent_duplicate_service import family_ids
    if group_key not in EVALUATION_GROUPS:
        raise HTTPException(422, '未知评价区域')
    if not db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first():
        raise HTTPException(404, '人才档案不存在')
    query = db.query(TalentEvaluationChange).filter(
        TalentEvaluationChange.person_id.in_(family_ids(db, person_id)), TalentEvaluationChange.group_key == group_key,
    )
    total = query.count()
    rows = query.order_by(TalentEvaluationChange.created_at.desc(), TalentEvaluationChange.id.desc()).offset(skip).limit(limit).all()
    return {'total': total, 'items': [dict(id=str(row.id), actor_account=row.actor_account,
            created_at=business_iso(row.created_at), before_values=row.before_values, after_values=row.after_values) for row in rows]}
