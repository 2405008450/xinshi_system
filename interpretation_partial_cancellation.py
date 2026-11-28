"""口译部分取消原因使用既有状态历史保存，不新增业务表。"""
OPTIONS={'行程/计划改变','支付定金后（部分）取消','其他原因（自行填写）'}

def validate_reason(value):
    text=str(value or '').strip()
    first=text.split('\n',1)[0]
    reasons=first.removeprefix('部分取消原因：').split('；') if first.startswith('部分取消原因：') else []
    if not reasons or any(item not in OPTIONS for item in reasons):raise ValueError('请在弹窗中至少选择一项部分取消原因')
    if '其他原因（自行填写）' in reasons and not any(line.startswith('其他原因：') and line.removeprefix('其他原因：').strip() for line in text.splitlines()):raise ValueError('请选择其他原因后填写具体内容')
    if len(text)>10000:raise ValueError('部分取消原因及截图说明不能超过10000字')
    return text

def preserve_screenshots(db,text):
    from editor_screenshot_service import references,valid_references,ready,api_time,now,promote_business_references
    from editor_screenshot_models import EditorScreenshot
    ids=references(text)
    if not ids:return
    if ids!=valid_references(text):raise ValueError('部分取消截图引用无效，请重新上传')
    if not ready(db):raise ValueError('截图存储尚未初始化')
    rows=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(ids)).all()
    if len(rows)!=len(ids) or any(not row.blob_sha256 or row.expires_at and api_time(row.expires_at)<=now() for row in rows):raise ValueError('部分取消截图不存在或已过期，请重新上传')
    promote_business_references(db,ids)
# Leaf paths are explicit to keep hierarchy validation identical for UI and saved classifications.
CANCELLATION_TREE={
 '客户已找到':{'已找到其他供应商':None,'已自行找到译员':None,'同事找到译员':None,'其他合作伙伴已协助解决':None,'时间赶不及/时间已过':None,'其他原因（自行填写）':None},
 '客户已取消':{'公司内部消化':None,'客户自身改变计划':None,'客户的客户改变计划':None,'客户的客户已有译员':None,'客户的客户未回复':None,'信实费用高':None,'客户预算低':None,'客户（领导）审批未通过':None,'有懂该语言的朋友同行':None,'不可抗力':None,'未回复原因':None,'客户无法出国':None,'译员原因':{'译员无法联系上':None,'译员主观原因':{'价格问题':None,'态度问题':None,'其他原因（自行填写）':None},'译员客观原因':{'交通问题':None,'身体原因':None,'家庭原因':None,'其他原因（自行填写）':None},'客户对译员不满意':None,'其他原因（自行填写）':None}},
 '客户不回复':None,'客户未回复原因':None,'无法找到译员':None,'无法提供合适译员':None,'其他原因（自行填写）':None}

def leaf_paths(tree,prefix=()):
 return [path for key,children in tree.items() for path in (leaf_paths(children,(*prefix,key)) if children else [(*prefix,key)])]
from typing import Optional
from uuid import UUID,uuid4
from copy import deepcopy
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import Column,Uuid,ForeignKey,String,Text,JSON,DateTime,inspect
from models import Base
from annotation_progress_time import business_now

class CancellationDetails(BaseModel):
 reason_paths:list[list[str]]=Field(min_length=1,max_length=50)
 explanations:dict[str,str]=Field(default_factory=dict)
 translator_issues:list[dict]=Field(default_factory=list,max_length=100)
 note:str=Field(default='',max_length=7000)
 @model_validator(mode='after')
 def validate_fields(self):
  allowed=set(leaf_paths(CANCELLATION_TREE))|{(item,) for item in OPTIONS}
  if any(tuple(path) not in allowed for path in self.reason_paths):raise ValueError('请选择有效的分级取消原因')
  for path in self.reason_paths:
   if path[-1]=='其他原因（自行填写）' or path[0] in {'无法找到译员','无法提供合适译员'}:
    value=self.explanations.get('|'.join(path),'').strip()
    if not value or len(value)>2000:raise ValueError('请填写其他原因或无法提供译员的具体说明（最多2000字）')
  for row in self.translator_issues:
   UUID(str(row.get('translator_id','')))
   if row.get('reason_path') not in self.reason_paths or '译员原因' not in row['reason_path']:raise ValueError('译员问题必须对应所选取消原因')
  for path in self.reason_paths:
   if '译员原因' in path and not any(row['reason_path']==path for row in self.translator_issues):raise ValueError('请为每项译员原因选择对应译员')
  return self

class InterpretationCancellationClassification(Base):
 __tablename__='interpretation_cancellation_classification'
 id=Column(Uuid,primary_key=True,default=uuid4)
 project_id=Column(Uuid,ForeignKey('interpretation_project.id',ondelete='CASCADE'),nullable=False,index=True)
 status_event_id=Column(Uuid,ForeignKey('interpretation_project_status_history.id',ondelete='CASCADE'),nullable=True,unique=True)
 project_status=Column(String(50),nullable=False)
 original_note=Column(Text,nullable=False,default='')
 details=Column(JSON,nullable=False,default=dict)
 source=Column(String(30),nullable=False,default='manual')
 created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

def prepare_cancellation(db,project,status,details,note):
 if not details:
  if status=='partially_cancelled':return validate_reason(note)
  raise ValueError('请在弹窗中选择已取消原因并填写说明')
 details=details if isinstance(details,CancellationDetails) else CancellationDetails.model_validate(details)
 allowed={tuple(path) for path in details.reason_paths}
 if status=='partially_cancelled' and not allowed<={(item,) for item in OPTIONS}:raise ValueError('部分取消仅可选择对应的三个原因')
 if status=='cancelled' and not allowed<=set(leaf_paths(CANCELLATION_TREE)):raise ValueError('请选择已取消的分级原因')
 rows={str(row.translator_id):row for row in project.interpreter_assignments}
 for row in project.interpreter_assignments:
  if row.translator and row.translator.resource_person_id:rows[str(row.translator.resource_person_id)]=row
 texts=[('部分取消原因：' if status=='partially_cancelled' else '已取消原因：')+'；'.join(' / '.join(path) for path in details.reason_paths)]
 for path in details.reason_paths:
  key='|'.join(path)
  if details.explanations.get(key):texts.append('具体说明（'+' / '.join(path)+'）：'+details.explanations[key].strip())
 for issue in details.translator_issues:
  assignment=rows.get(str(issue['translator_id']))
  if not assignment:raise ValueError('对应译员必须在本项目的译员安排中')
  texts.append('对应译员（'+' / '.join(issue['reason_path'])+'）：'+assignment.translator_name)
 if details.note.strip():texts.append('截图和说明：\n'+details.note.strip())
 text='\n'.join(texts)
 if len(text)>10000:raise ValueError('取消原因及截图说明合计不能超过10000字')
 preserve_screenshots(db,text)
 return text

def store_cancellation(db,project,event,details,original_note):
 if not details:return
 if not inspect(db.connection()).has_table(InterpretationCancellationClassification.__tablename__):raise ValueError('取消原因分类存储尚未初始化')
 details=details if isinstance(details,CancellationDetails) else CancellationDetails.model_validate(details)
 db.flush()
 db.add(InterpretationCancellationClassification(project_id=project.id,status_event_id=event.id,project_status=event.to_status,original_note=original_note or '',details=details.model_dump(mode='json')))
 if details.translator_issues:
  from interpretation_lifecycle import InterpretationLifecycle
  record=db.get(InterpretationLifecycle,project.id)
  if record is None:record=InterpretationLifecycle(project_id=project.id,assignment_data={});db.add(record)
  data=deepcopy(record.assignment_data or {})
  for issue in details.translator_issues:
   assignment=next((row for row in project.interpreter_assignments if str(row.translator_id)==str(issue['translator_id']) or row.translator and str(row.translator.resource_person_id)==str(issue['translator_id'])),None)
   if assignment is None:raise ValueError('找不到对应译员')
   item=data.setdefault(str(assignment.translator_id),{});history=item.setdefault('cancellation_issues',[])
   history.append(dict(status_event_id=str(event.id),reason_path=issue['reason_path'],explanation=details.explanations.get('|'.join(issue['reason_path']),''),note=details.note,recorded_at=business_now().isoformat()))
  record.assignment_data=data
def classify_original(status,text):
 """保守匹配明确语义；原始说明逐字保留，缺少细分依据时归其他并待复核。"""
 import re
 raw=text or '';clean=re.sub(r'!\[[^]]*\]\(screenshot://[^)]+\)','',raw);paths=[]
 def add(*path):
  if list(path) not in paths:paths.append(list(path))
 if status=='partially_cancelled':
  if re.search('行程|计划.*(改变|调整|变更|有变)',clean):add('行程/计划改变')
  if '定金' in clean and re.search('取消|退|不需要',clean):add('支付定金后（部分）取消')
 else:
  for path in sorted(leaf_paths(CANCELLATION_TREE),key=lambda path:len(path[-1]),reverse=True):
   if path[-1]!='其他原因（自行填写）' and path[-1] in clean and ('译员原因' not in path or '译员' in clean):add(*path)
  def client_reason(value):add('客户已取消',value)
  if re.search('其他供应商|别的翻译公司|其他翻译公司',clean):add('客户已找到','已找到其他供应商')
  elif re.search('同事.*找',clean):add('客户已找到','同事找到译员')
  elif re.search('其他合作伙伴.*(解决|处理)|合作伙伴已',clean):add('客户已找到','其他合作伙伴已协助解决')
  elif re.search('自己带.*翻译|自行找到|自己.*找到',clean):add('客户已找到','已自行找到译员')
  elif re.search('客户.*(找到了|已找到|已经找到|已经选好|说已经定了|另[外]?[找了]|找了朋友|找了其他|找了新的|找到更便宜)|^找到人了|^找了其他人|^找其他',clean):add('客户已找到','其他原因（自行填写）')
  if re.search('时间.*(已过|过了|已到)|到项目时间|已过时间|来不及|赶不及',clean):add('客户已找到','时间赶不及/时间已过')
  if re.search('(价格|费用).*(过高|太高|太贵|高|贵)|嫌贵|觉得贵',clean):client_reason('信实费用高')
  if re.search('预算.*(不足|不够|低)|超.*预算|不符合.*预算|费用不符合预算',clean):client_reason('客户预算低')
  if re.search('(领导|老板).*(审批|批准).*(没|未|不)|审批未通过',clean):client_reason('客户（领导）审批未通过')
  if re.search('内部.*消化',clean):client_reason('公司内部消化')
  if re.search('(子客户|外国客户|甲方|客户的客户).*(没回复|不回复|未回复)',clean):client_reason('客户的客户未回复')
  elif re.search('客户.*(不回复|未回复|没有回复|没回复|无回复|不回消息|不回邮件)|^无回复$',clean):add('客户不回复')
  if re.search('(甲方|客户的客户).*(不来|改变计划|取消行程)',clean):client_reason('客户的客户改变计划')
  elif re.search('客户(时间|计划).*(变|调整)|客户取消行程|老板行程变化',clean):client_reason('客户自身改变计划')
  if re.search('朋友.*(同行|翻译|帮忙)',clean):client_reason('有懂该语言的朋友同行')
  if re.search('战争|战乱|地震|不可抗力',clean):client_reason('不可抗力')
  if re.search('出不了国|无法出国|不能出国',clean):client_reason('客户无法出国')
  if re.search('没有合适|找不到适合|经验和费用不太合适|译员.*不太合适',clean):add('无法提供合适译员')
  elif re.search('没有译员|找不到译员|没有.*这个语种.*老师',clean):add('无法找到译员')
  if re.search('客户.*译员不满意',clean):add('客户已取消','译员原因','客户对译员不满意')
  if not paths and re.search('客户.*(不需要|不用|取消)|会议取消|行程取消|行程变动|不需要了',clean):client_reason('其他原因（自行填写）')
 if not paths:paths=[['客户未回复原因']] if status=='cancelled' and clean.strip()=='项目取消' else [['其他原因（自行填写）']]
 paths=list(dict.fromkeys(tuple(path) for path in paths))
 return dict(reason_paths=[list(path) for path in paths],explanations={'|'.join(path):raw or '原始说明未填写，待人工补充' for path in paths if path[-1]=='其他原因（自行填写）' or path[0] in {'无法找到译员','无法提供合适译员'}},note=raw,translator_issues=[],needs_review=any('译员原因' in path or path[-1]=='其他原因（自行填写）' for path in paths),classifier_version=2)

def review_classification(db,project_id,payload,actor_id):
 from fastapi import HTTPException
 from interpretation_models import InterpretationProject
 project=db.query(InterpretationProject).filter_by(id=project_id).with_for_update().one_or_none()
 if not project:raise HTTPException(404,'口译项目不存在')
 row=db.query(InterpretationCancellationClassification).filter_by(project_id=project_id,id=UUID(payload['classification_id'])).with_for_update().one_or_none()
 if not row:raise HTTPException(404,'原因分类不存在，请刷新后重试')
 if row.details!=payload.get('expected_details'):raise HTTPException(409,'原因已由其他人调整，请刷新后重试')
 if project.project_status!=row.project_status:raise HTTPException(409,'项目状态已改变，请刷新后重试')
 details=CancellationDetails.model_validate(payload.get('details'))
 prepare_cancellation(db,project,row.project_status,details,row.original_note)
 history=list((row.details or {}).get('_review_history',[]))
 history.append(dict(before={key:deepcopy(value) for key,value in row.details.items() if key!='_review_history'},actor_id=str(actor_id),at=business_now().isoformat()))
 row.details={**details.model_dump(mode='json'),'needs_review':False,'_review_history':history}
 row.source='manual'
 from interpretation_lifecycle import InterpretationLifecycle
 record=db.get(InterpretationLifecycle,project.id)
 if details.translator_issues or record:
  if record is None:record=InterpretationLifecycle(project_id=project.id,assignment_data={});db.add(record)
  data=deepcopy(record.assignment_data or {})
  for entry in data.values():
   entry['cancellation_issues']=[issue for issue in entry.get('cancellation_issues',[]) if issue.get('classification_id')!=str(row.id) and (not row.status_event_id or issue.get('status_event_id')!=str(row.status_event_id))]
  for issue in details.translator_issues:
   assignment=next(item for item in project.interpreter_assignments if str(item.translator_id)==str(issue['translator_id']) or item.translator and str(item.translator.resource_person_id)==str(issue['translator_id']))
   entry=data.setdefault(str(assignment.translator_id),{})
   entry.setdefault('cancellation_issues',[]).append(dict(reason_path=issue['reason_path'],explanation=details.explanations.get('|'.join(issue['reason_path']),''),note=details.note,classification_id=str(row.id)))
  record.assignment_data=data
 return dict(saved=True)


def classify_existing(db,check_only=False):
 from interpretation_models import InterpretationProject,InterpretationProjectStatusHistory
 from uuid import uuid5,NAMESPACE_URL
 projects=db.query(InterpretationProject).filter(InterpretationProject.project_status.in_(['cancelled','partially_cancelled'])).all()
 ids=[project.id for project in projects]
 events=db.query(InterpretationProjectStatusHistory).filter(InterpretationProjectStatusHistory.project_id.in_(ids)).order_by(InterpretationProjectStatusHistory.changed_at.desc(),InterpretationProjectStatusHistory.id.desc()) if ids else []
 by_project={}
 statuses={project.id:project.project_status for project in projects}
 for event in events:
  if event.to_status==statuses[event.project_id]:by_project.setdefault(event.project_id,event)
 counts={'projects':len(projects),'inserted':0,'updated':0,'existing':0,'needs_review':0}
 for project in projects:
  event=by_project.get(project.id);key=uuid5(NAMESPACE_URL,'interpretation-cancellation-classify:'+str(event.id if event else project.id)+':'+project.project_status)
  existing=db.get(InterpretationCancellationClassification,key) or (db.query(InterpretationCancellationClassification).filter_by(status_event_id=event.id).first() if event else None)
  if existing:
   if existing.source=='auto' and (existing.details or {}).get('classifier_version',0)<2:
    details=classify_original(existing.project_status,existing.original_note);counts['updated']+=1;counts['needs_review']+=int(details['needs_review'])
    if not check_only:existing.details=details
   else:counts['existing']+=1
   continue
  raw=event.change_note or '' if event else ''
  details=classify_original(project.project_status,raw);counts['inserted']+=1;counts['needs_review']+=int(details['needs_review'])
  if not check_only:db.add(InterpretationCancellationClassification(id=key,project_id=project.id,status_event_id=event.id if event else None,project_status=project.project_status,original_note=raw,details=details,source='auto'))
 return counts
