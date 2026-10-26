"""新咨询保存后的强制工作报告填写。状态存于既有咨询 JSON，不新增表结构。"""
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select

from chat_time import now,api_time
from models import Consultation,Client
from task_models import DailyReport,DailyReportItem
from work_report_dates import report_business_date

CAPTURE_KEY='_work_report_capture'


class ConsultationReportWrite(BaseModel):
    order_no:str=Field(min_length=1,max_length=100)
    task_name:str=Field(min_length=1,max_length=255)
    progress_content:str=Field(min_length=1,max_length=10000)
    quantity:str|float=Field()
    quantity_unit:str=Field(min_length=1,max_length=80)
    duration_minutes:int=Field(ge=1,le=1440)

    @model_validator(mode='after')
    def valid(self):
        import math
        for field in ['order_no','task_name','progress_content','quantity_unit']:
            value=getattr(self,field).strip()
            if not value or any(token in value.lower() for token in ['screenshot://','data:image/','<img']):raise ValueError('请完整填写文字字段，不支持截图')
            setattr(self,field,value)
        try:number=float(self.quantity)
        except (ValueError,TypeError):raise ValueError('请填写非负数字工作量')
        if isinstance(self.quantity,bool) or not math.isfinite(number) or number<0:raise ValueError('请填写非负数字工作量')
        return self


def preserve_capture(existing,incoming):
    result={key:value for key,value in (incoming or {}).items() if key!=CAPTURE_KEY}
    if (existing or {}).get(CAPTURE_KEY):result[CAPTURE_KEY]=existing[CAPTURE_KEY]
    return result


def mark_pending(consultation,user):
    data=dict(consultation.project_intake or {})
    if not data.get(CAPTURE_KEY):
        data[CAPTURE_KEY]={'owner_id':str(user.id),'status':'pending','created_at':now().isoformat(),'item_key':str(uuid4())}
        consultation.project_intake=data


def pending(db,user):
    rows=db.query(Consultation).filter(Consultation.project_intake[CAPTURE_KEY]['owner_id'].as_string()==str(user.id),Consultation.project_intake[CAPTURE_KEY]['status'].as_string()=='pending').order_by(Consultation.created_at,Consultation.id).limit(100).all()
    return [{'id':row.id,'consultation_code':row.consultation_code} for row in rows]


def owned_consultation(db,user,consultation_id,lock=False):
    query=db.query(Consultation).filter_by(id=consultation_id)
    if lock:query=query.with_for_update()
    row=query.first()
    if not row or (row.project_intake or {}).get(CAPTURE_KEY,{}).get('owner_id')!=str(user.id):raise HTTPException(404,'待填写的新咨询工作报告不存在')
    return row


def capture_context(db,user,consultation_id):
    row=owned_consultation(db,user,consultation_id)
    client=db.get(Client,row.client_id) if row.client_id else None
    # 使用咨询表关联的客户名称，不使用项目名称替代。
    name=(client.client_name or client.client_short_name) if client else ''
    capture=row.project_intake[CAPTURE_KEY]
    method=row.consultation_method_detail if row.consultation_method=='其他' and row.consultation_method_detail else row.consultation_method
    return {'consultation_id':row.id,'consultation_code':row.consultation_code,'client_name':name or '未命名客户','completed':capture['status']=='completed','report_date':capture.get('report_date') or report_business_date(),'order_no':row.consultation_code,'task_name':f'{name or "未命名客户"} - 新咨询对接','progress_content':' - '.join(str(value or '-') for value in [method,row.consultation_type,row.client_source])}


def submit(db,user,consultation_id,payload):
    # 同用户所有自动追加串行化，避免两个新咨询同时创建同一天日报。
    from models import AppUser
    db.execute(select(AppUser.id).where(AppUser.id==user.id).with_for_update()).first()
    consultation=owned_consultation(db,user,consultation_id,lock=True)
    capture=dict(consultation.project_intake[CAPTURE_KEY])
    if capture['status']=='completed':return {'report_id':capture['report_id'],'report_date':capture['report_date'],'already_saved':True}
    instant=now();day=report_business_date(instant)
    report=db.query(DailyReport).filter_by(user_id=user.id,report_date=day).with_for_update().first()
    if not report:
        report=DailyReport(id=uuid4(),user_id=user.id,report_date=day,status='draft',generated_at=instant.replace(tzinfo=None),created_at=instant.replace(tzinfo=None),updated_at=instant.replace(tzinfo=None))
        db.add(report);db.flush()
    item=DailyReportItem(id=uuid4(),report_id=report.id,source_type='manual',source_id=consultation.id,task_type='项目工作',task_name=payload.task_name,progress_content=payload.progress_content,duration_minutes=payload.duration_minutes,sort_order=max((item.sort_order for item in report.items),default=-1)+1,display_metadata={'report_types':['新咨询对接'],'order_no':payload.order_no,'quantity':payload.quantity,'quantity_unit':payload.quantity_unit,'source':'consultation_handoff','consultation_id':str(consultation.id),'consultation_code':consultation.consultation_code,'added_at':instant.isoformat(),'_feedback_key':capture['item_key']})
    report.items.append(item)
    report.updated_at=instant.replace(tzinfo=None)
    # 追加与修订不同：既有工作项、确认状态和修订记录均不改写。
    capture.update(status='completed',report_id=str(report.id),report_date=day.isoformat(),completed_at=instant.isoformat(),original_entry=payload.model_dump(mode='json'))
    consultation.project_intake={**consultation.project_intake,CAPTURE_KEY:capture}
    db.commit()
    try:
        publish_report_update(db,report)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('工作报告追加已保存，但实时通知失败')
    return {'report_id':report.id,'report_date':day,'already_saved':False}


def publish_report_update(db,report):
    import work_report_access as access
    from notification_ws import broadcast_to_users
    viewers={str(report.user_id)}
    if access.ready(db):
        rules=db.query(access.WorkReportAccessRule).filter_by(enabled=True).all()
        people=access.active_people(db).all()
        configurator=next((person.id for person in people if person.username==access.CONFIGURATOR_USERNAME),None)
        senders={rule.id:access.sender_ids_for_rules(db,[rule]) for rule in rules}
        for person in people:
            matching=[rule for rule in rules if rule.viewers_all or str(person.id) in rule.viewer_ids]
            if any(report.user_id in senders[rule.id] for rule in access.prioritize_rules(person.id,matching,configurator)):
                viewers.add(str(person.id))
    broadcast_to_users(list(viewers),{'type':'daily_report_updated','report_id':str(report.id),'user_id':str(report.user_id),'report_date':report.report_date.isoformat()})
