"""跨四种业务的客户新老判断；日期筛选临时计算，不回写客户档案。"""
import calendar,re
from datetime import date
from uuid import UUID
from sqlalchemy import Column,Uuid,ForeignKey,String,Text,JSON,DateTime,inspect,func
from models import Base,Client,SubClient,TranslationProject
from annotation_progress_time import business_now,business_datetime

class ClientCohortOverride(Base):
 __tablename__='client_cohort_override'
 client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
 cohort=Column(String(10),nullable=True)
 reason=Column(Text,nullable=False)
 updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
 updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)
 history=Column(JSON,nullable=False,default=list)

def order_records(db,client_ids=None):
 from interpretation_models import InterpretationProject
 from annotation_models import AnnotationProject
 from recruitment_models import RecruitmentProject
 result=[]
 for module,model,prefix,timefield in [('translation',TranslationProject,'TP','customer_reception_time'),('interpretation',InterpretationProject,'IP','customer_consultation_time'),('annotation',AnnotationProject,'AP','customer_consultation_time'),('recruitment',RecruitmentProject,'HP','customer_consultation_time')]:
  parent=func.coalesce(model.client_id,SubClient.parent_client_id)
  query=db.query(model.id,model.order_no,model.project_name,parent.label('parent_id'),model.created_at,getattr(model,timefield).label('received_at'),model.project_status).outerjoin(SubClient,model.sub_client_id==SubClient.id)
  if module=='translation':query=query.filter(model.annotation_migrated_at.is_(None))
  if module=='annotation':query=query.filter(model.parent_project_id.is_(None))
  if client_ids is not None:query=query.filter(parent.in_([UUID(str(value)) for value in client_ids]))
  seen=set()
  for row in query:
   if not row.order_no or (row.parent_id,row.order_no) in seen:continue
   seen.add((row.parent_id,row.order_no));match=re.match(r'^'+prefix+r'-(\d{8}|\d{6})-',row.order_no)
   day=None
   if match:
    digits=match[1] if len(match[1])==8 else '20'+match[1]
    try:day=date(int(digits[:4]),int(digits[4:6]),int(digits[6:8]))
    except ValueError:pass
   day=day or (business_datetime(row.created_at).date() if row.created_at else None)
   result.append(dict(module=module,id=str(row.id),order_no=row.order_no,project_name=row.project_name or '',client_id=str(row.parent_id) if row.parent_id else None,day=day,received_day=business_datetime(row.received_at).date() if row.received_at else day,status=str(row.project_status or '')))
 return result

def three_months(day):
 month=day.month+3;year=day.year+(month-1)//12;month=(month-1)%12+1
 return date(year,month,min(day.day,calendar.monthrange(year,month)[1]))

def snapshots(db,client_ids=None,*,start=None,end=None,date_basis='order',records=None):
 rows=records if records is not None else order_records(db,client_ids)
 grouped={str(value):[] for value in client_ids or []}
 for row in rows:
  if row['client_id']:grouped.setdefault(row['client_id'],[]).append(row)
 overrides={}
 if start is None and inspect(db.connection()).has_table(ClientCohortOverride.__tablename__):
  query=db.query(ClientCohortOverride)
  if client_ids is not None:query=query.filter(ClientCohortOverride.client_id.in_([UUID(str(value)) for value in client_ids]))
  overrides={str(row.client_id):row for row in query}
 result={}
 for key,orders in grouped.items():
  first=min((row['day'] for row in orders if row['day']),default=None)
  selected=orders if start is None else [row for row in orders if (row['received_day'] if date_basis=='reception' else row['day']) and start<=(row['received_day'] if date_basis=='reception' else row['day'])<=end]
  count=len(selected)
  automatic=('old' if count>=2 or first and three_months(first)<=business_now().date() else 'new') if start is None else ('old' if count>=2 or first and not start<=first<=end else 'new')
  override=overrides.get(key)
  result[key]=dict(cohort=override.cohort if override and override.cohort else automatic,automatic_cohort=automatic,override=override.cohort if override else None,reason=override.reason if override else '',order_count=count,total_order_count=len(orders),first_order_date=first.isoformat() if first else None,updated_at=business_datetime(override.updated_at).isoformat() if override else None,history=override.history or [] if override else [])
 return result

def attach(db,clients,*,start=None,end=None):
 states=snapshots(db,[row.id for row in clients],start=start,end=end)
 for row in clients:
  state=states[str(row.id)];row.order_count=state['order_count'];row.customer_cohort=state['cohort'];row.cohort_info=state
 return clients
