"""项目预统计独立保存；不进入客户／我司计费统计。"""
from uuid import uuid4
from sqlalchemy import Column,Uuid,String,BigInteger,DateTime,ForeignKey,CheckConstraint,UniqueConstraint,inspect,or_
from models import Base
from annotation_progress_time import business_now


class PreliminaryWordCountMetric(Base):
    __tablename__='preliminary_word_count_metric'
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'))
    sub_order_id=Column(Uuid,ForeignKey('translation_sub_order.id',ondelete='CASCADE'))
    metric_type=Column(String(40),nullable=False)
    count_value=Column(BigInteger,nullable=False)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)
    dimension='preliminary'
    arrangement_id=None
    __table_args__=(
        CheckConstraint('(project_id IS NOT NULL AND sub_order_id IS NULL) OR (project_id IS NULL AND sub_order_id IS NOT NULL)',name='ck_preliminary_count_owner'),
        CheckConstraint('count_value >= 0',name='ck_preliminary_count_nonnegative'),
        CheckConstraint("metric_type IN ('words','characters_no_spaces','cjk_chars_korean_words','foreign_words','documents','pages')",name='ck_preliminary_count_metric'),
        UniqueConstraint('project_id','metric_type',name='uq_preliminary_project_metric'),
        UniqueConstraint('sub_order_id','metric_type',name='uq_preliminary_suborder_metric'),
    )


def ready(db):
    key='preliminary_word_count_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(PreliminaryWordCountMetric.__tablename__)
    return db.info[key]


def rows(db,project_ids=(),sub_order_ids=()):
    if not project_ids and not sub_order_ids:return []
    if not ready(db):return []
    model=PreliminaryWordCountMetric
    return db.query(model).filter(or_(model.project_id.in_(list(project_ids)),model.sub_order_id.in_(list(sub_order_ids)))).all()


def apply_cell(db,owner_filters,metric_type,value,updated_by):
    if not ready(db):
        if value is None:return
        from fastapi import HTTPException
        raise HTTPException(503,'预统计存储尚未初始化')
    model=PreliminaryWordCountMetric
    owners={key:owner_filters[key] for key in ('project_id','sub_order_id')}
    row=db.query(model).filter_by(**owners,metric_type=metric_type).first()
    if value is None:
        if row:db.delete(row)
        return
    if row is None:row=model(**owners,metric_type=metric_type);db.add(row)
    row.count_value=value;row.updated_by=updated_by;row.updated_at=business_now()
