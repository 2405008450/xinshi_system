"""简单需求的统计来源记录：同事务累加，重试不重复；不改旧表结构。"""
from copy import deepcopy
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import Column,DateTime,ForeignKey,JSON,Uuid,inspect
from models import Base,TranslationSubOrder
from annotation_progress_time import business_now

class SimpleRequirementWordCount(Base):
    __tablename__='translation_simple_requirement_word_count'
    requirement_id=Column(Uuid,ForeignKey('translation_simple_requirement.id',ondelete='CASCADE'),primary_key=True)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    matrix=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def ready(db):
    if db.info.get('simple_requirement_word_count_ready'):return True
    result=inspect(db.connection()).has_table(SimpleRequirementWordCount.__tablename__)
    if result:db.info['simple_requirement_word_count_ready']=True
    return result


def normalized(matrix):
    from word_count_schemas import WordCountCreateMatrix
    values=matrix.model_dump() if hasattr(matrix,'model_dump') else WordCountCreateMatrix.model_validate(matrix or {}).model_dump()
    return {dim:{metric:value for metric,value in counts.items() if value is not None} for dim,counts in values.items() if any(value is not None for value in counts.values())}


def summary(db,ids):
    if not ids or not ready(db):return {}
    result={}
    for row in db.query(SimpleRequirementWordCount).filter(SimpleRequirementWordCount.project_id.in_(ids)):
        matrix=result.setdefault(row.project_id,{})
        for dimension,counts in row.matrix.items():
            values=matrix.setdefault(dimension,{})
            for metric,value in counts.items():values[metric]=values.get(metric,0)+value
    for matrix in result.values():
        for values in matrix.values():
            if values.get('minutes') is not None and values.get('hours') is not None:values['minutes']=round(values['minutes']+values.pop('hours')*60,4)
    return result


def attach(db,projects):
    totals=summary(db,[owner.id for owner in projects])
    for owner in projects:owner.simple_requirement_word_count_matrix=totals.get(owner.id,{})


def add(db,parent,requirement,matrix,actor_id):
    data=normalized(matrix)
    if not data:return False
    if not ready(db):raise HTTPException(503,'简单需求统计表尚未初始化')
    from word_count_service import _entity_metric_rows, _apply_cell, _owner_filters, validate_matrix_regions, has_multiple_word_count_regions
    from word_count_schemas import WordCountCreateMatrix
    validate_matrix_regions(WordCountCreateMatrix.model_validate(data))
    base={}
    for row in _entity_metric_rows(db,'project',parent.id):base.setdefault(row.dimension,{})[row.metric_type]=row.count_value
    has_children=db.query(TranslationSubOrder.id).filter_by(parent_project_id=parent.id).first() is not None
    for dim,counts in data.items():
        existing=base.setdefault(dim,{})
        if not has_children and dim in ('company', 'customer') and has_multiple_word_count_regions({**existing, **counts}):
            label = '我司统计' if dim == 'company' else '客户统计'
            raise HTTPException(422, f'{label}请使用当前订单已登记的统计区域')
        for metric,value in counts.items():
            # 分钟和小时统一累计至当前使用的单位，不直接把小时当分钟相加。
            actual=metric
            if metric=='hours' and existing.get('minutes') is not None:actual='minutes';value*=60
            elif metric=='minutes' and existing.get('hours') is not None:actual='hours';value/=60
            current=existing.get(actual)
            total=(current if current is not None else 0)+value
            if total>9999999999:raise HTTPException(422,'累计统计超出允许范围，请核对数量')
            _apply_cell(db,owner_filters=_owner_filters('project',parent.id),dimension=dim,metric_type=actual,value=total,updated_by=actor_id)
            existing[actual]=total
    db.add(SimpleRequirementWordCount(requirement_id=requirement.id,project_id=parent.id,matrix=data))
    db.flush()
    return True


def record(db,requirement_id):
    if not ready(db):return {}
    row=db.get(SimpleRequirementWordCount,requirement_id)
    return row.matrix if row else {}


def without_additions(db,owner,matrix):
    """母单首次拆为文件子单时，简单需求仍归母单，不能复制后再次累计。"""
    result=deepcopy(matrix)
    totals=summary(db,[owner.id]).get(owner.id,{})
    for dim,counts in totals.items():
        for metric,value in counts.items():
            actual=metric
            if metric=='hours' and result.get(dim,{}).get('minutes') is not None:actual='minutes';value*=60
            elif metric=='minutes' and result.get(dim,{}).get('hours') is not None:actual='hours';value/=60
            existing=result.get(dim,{}).get(actual)
            if existing is not None:result[dim][actual]=round(max(0,existing-value),4)
    return result
