"""按客户档案精确查询历史笔译项目方向；只读轻量列表。"""
from datetime import datetime,timedelta
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import or_,and_,func
from models import TranslationProject,SubClient,Client
from annotation_progress_time import business_now,business_datetime
from search_matching import keyword_any

PERIOD_DAYS={'week':7,'month':30,'year':365,'all':None}

def history(db,client_id,period='week',keyword='',skip=0,limit=20,exclude_project_id=None,at=None):
    client=db.get(Client,client_id)
    if not client:raise HTTPException(404,'客户档案不存在，请重新选择客户')
    at=business_datetime(at or business_now());end=at.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    days=PERIOD_DAYS[period];start=end-timedelta(days=days) if days else None
    P=TranslationProject
    query=db.query(P.id,P.order_no,P.project_name,P.language_pair,P.created_at).outerjoin(SubClient,SubClient.id==P.sub_client_id).filter(P.annotation_migrated_at.is_(None),or_(P.client_id==client_id,and_(P.client_id.is_(None),SubClient.parent_client_id==client_id)))
    if exclude_project_id:query=query.filter(P.id!=exclude_project_id)
    if start:query=query.filter(P.created_at>=start.replace(tzinfo=None),P.created_at<end.replace(tzinfo=None))
    query=query.filter(keyword_any([P.order_no,P.project_name,P.source_file_name,P.language_pair],keyword))
    total=query.count();rows=query.order_by(P.created_at.desc().nullslast(),P.order_no.desc(),P.id).offset(skip).limit(limit).all()
    return dict(items=[dict(id=str(row.id),order_no=row.order_no,project_name=row.project_name,language_pair=row.language_pair or '',created_at=business_datetime(row.created_at).isoformat() if row.created_at else None) for row in rows],total=total,period=period,client_id=str(client.id),client_name=client.client_short_name or client.client_name or '',range_start=start.date().isoformat() if start else None,range_end=(end-timedelta(days=1)).date().isoformat())
