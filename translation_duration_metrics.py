"""笔译统计中的时长单元格，独立存储，不改动既有字数表。"""
from uuid import uuid4
from sqlalchemy import Column,Uuid,String,Numeric,DateTime,ForeignKey,CheckConstraint,UniqueConstraint,inspect,or_
from fastapi import HTTPException
from models import Base
from annotation_progress_time import business_now


class TranslationDurationMetric(Base):
    __tablename__='translation_duration_metric'
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'))
    sub_order_id=Column(Uuid,ForeignKey('translation_sub_order.id',ondelete='CASCADE'))
    arrangement_id=Column(Uuid,ForeignKey('manuscript_arrangement.id',ondelete='CASCADE'))
    dimension=Column(String(40),nullable=False)
    metric_type=Column(String(20),nullable=False)
    count_value=Column(Numeric(14,4),nullable=False)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)
    __table_args__=(
        CheckConstraint('(CASE WHEN project_id IS NULL THEN 0 ELSE 1 END + CASE WHEN sub_order_id IS NULL THEN 0 ELSE 1 END + CASE WHEN arrangement_id IS NULL THEN 0 ELSE 1 END)=1',name='ck_translation_duration_owner'),
        CheckConstraint("metric_type IN ('minutes','hours') AND count_value>=0",name='ck_translation_duration_value'),
        CheckConstraint("(arrangement_id IS NOT NULL AND dimension IN ('planned','actual')) OR (arrangement_id IS NULL AND dimension IN ('company','customer','preliminary','translator_estimate'))",name='ck_translation_duration_dimension'),
        UniqueConstraint('project_id','dimension',name='uq_translation_duration_project'),
        UniqueConstraint('sub_order_id','dimension',name='uq_translation_duration_suborder'),
        UniqueConstraint('arrangement_id','dimension',name='uq_translation_duration_arrangement'),
    )


def ready(db):
    key='translation_duration_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(TranslationDurationMetric.__tablename__)
    return db.info[key]


def rows(db,project_ids=(),sub_order_ids=(),arrangement_ids=()):
    if not ready(db) or not (project_ids or sub_order_ids or arrangement_ids):return []
    m=TranslationDurationMetric
    return db.query(m).filter(or_(m.project_id.in_(list(project_ids)),m.sub_order_id.in_(list(sub_order_ids)),m.arrangement_id.in_(list(arrangement_ids)))).all()


def apply_cell(db,owners,dimension,metric,value,actor_id):
    if not ready(db):
        if value is None:return
        raise HTTPException(503,'时长统计存储尚未初始化')
    row=db.query(TranslationDurationMetric).filter_by(**owners,dimension=dimension).first()
    if value is None:
        if row and row.metric_type==metric:db.delete(row);db.flush()
        return
    if row is None:row=TranslationDurationMetric(**owners,dimension=dimension);db.add(row)
    row.metric_type=metric;row.count_value=value;row.updated_by=actor_id;row.updated_at=business_now();db.flush()
