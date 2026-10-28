"""月班次安排；每人每月唯一，行政部调整，本人只读。"""
from datetime import date,datetime
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import Date,Integer,JSON,DateTime,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr

SHIFTS=[
    {'code':'early_early','label':'早早班','periods':['08:30–12:00','13:30–18:00'],'description':'上午 08:30 到岗，午间休息 12:00–13:30，下午工作至 18:00。'},
    {'code':'early','label':'早班','periods':['09:00–12:00','13:30–18:30'],'description':'上午 09:00 到岗，午间休息 12:00–13:30，下午工作至 18:30。'},
    {'code':'late','label':'晚班','periods':['10:30–12:00','13:30–20:00'],'description':'上午 10:30 到岗，午间休息 12:00–13:30，下午及晚间工作至 20:00。'},
    {'code':'customer_remote','label':'晚班（客户部居家）','periods':['10:30–12:00','13:30–18:00','21:00–23:00'],'description':'适用于客户部居家班次：上午 10:30–12:00、下午 13:30–18:00、晚间 21:00–23:00；其余时段为非排班时段。'},
    {'code':'late_late','label':'晚晚班','periods':['13:30–21:30'],'description':'下午 13:30 到岗，工作至 21:30；班次内休息安排按公司制度执行。'},
]
DEPARTMENTS=[{'code':'customer','label':'客户/销售部'},{'code':'hr','label':'HR部'},{'code':'project','label':'项目部（翻译+标注）'},{'code':'layout','label':'排版部'},{'code':'it','label':'IT部门'},{'code':'administration','label':'行政部'}]

class MonthlyShiftPlan(Base):
    __tablename__='monthly_shift_plan'
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)

class Assignment(BaseModel):
    user_id:UUID
    department:str
    shift:str
    @model_validator(mode='after')
    def valid_cell(self):
        if self.department not in {row['code'] for row in DEPARTMENTS} or self.shift not in {row['code'] for row in SHIFTS}:raise ValueError('请选择有效部门和班次')
        if self.shift=='customer_remote' and self.department!='customer':raise ValueError('客户部居家晚班仅适用于客户部')
        return self

class PlanWrite(BaseModel):
    revision:int=Field(ge=0)
    assignments:list[Assignment]=Field(default_factory=list,max_length=2000)
    @model_validator(mode='after')
    def unique_people(self):
        if len({row.user_id for row in self.assignments})!=len(self.assignments):raise ValueError('同一人员每月只能安排一个班次')
        return self

def ready(db):return inspect(db.connection()).has_table(MonthlyShiftPlan.__tablename__)
def month_key(value):
    try:
        if len(value)!=7:raise ValueError()
        return date.fromisoformat(value+'-01')
    except (ValueError,TypeError):raise HTTPException(422,'月份格式应为 YYYY-MM')

def participating(name):
    value=(name or '').replace(' ','').casefold()
    return group_code(name) is not None

def group_code(name):
    value=(name or '').replace(' ','').casefold()
    if value in {'客户部','销售','销售部'}:return 'customer'
    if value in {'hr部','人力资源部','人事部'}:return 'hr'
    if value in {'排版','排版部'}:return 'layout'
    if value in {'项目部','翻译项目部','标注项目部'}:return 'project'
    if value in {'it部','it部门','技术部'}:return 'it'
    if value in {'行政','行政部','行政部门'}:return 'administration'

def directory(db,user):
    require_hr(db,user)
    from organization_service import directory as organization
    data=organization(db,user)
    # 仅在排班展示中合并；不修改任何组织部门或人员归属。
    names={row['id']:group_code(row['name']) for row in data['items']}
    departments=[{'id':row['code'],'name':row['label']} for row in DEPARTMENTS]
    by_code={row['id']:row for row in departments}
    people=[]
    for person in data['people']:
        codes={names.get(row['id']) for row in person['departments']}-{None}
        if person['active'] and codes:people.append({**person,'departments':[by_code[code] for code in by_code if code in codes]})
    return {'ready':ready(db),'items':departments,'people':people,'shifts':SHIFTS,'departments':DEPARTMENTS}

def serialize(db,row,month,weekly=False):
    from fixed_shift import effective
    entries=effective(db,row.assignments if row else [],month,weekly=weekly)
    ids=[UUID(entry['user_id']) for entry in entries]
    users={str(person.id):person for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    actor=db.get(AppUser,row.updated_by) if row else None
    return api_time({'ready':ready(db),'month':month.strftime('%Y-%m'),'revision':row.revision if row else 0,
        'assignments':[{**entry,'name':users[entry['user_id']].full_name or users[entry['user_id']].username,'active':users[entry['user_id']].is_active and not users[entry['user_id']].is_deleted} for entry in entries if entry['user_id'] in users],
        'shifts':SHIFTS,'departments':DEPARTMENTS,'updated_by_name':actor.full_name or actor.username if actor else None,'updated_at':row.updated_at if row else None})

def get_plan(db,user,month):
    require_hr(db,user);day=month_key(month)
    return serialize(db,db.get(MonthlyShiftPlan,day) if ready(db) else None,day)

def save_plan(db,user,month,payload):
    require_hr(db,user);day=month_key(month)
    if not ready(db):raise HTTPException(503,'月度排班表尚未初始化')
    row=db.query(MonthlyShiftPlan).filter_by(month=day).with_for_update().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'本月排班已被调整，请刷新后重试')
    previous={entry['user_id']:entry for entry in row.assignments} if row else {}
    allowed={person['id'] for person in directory(db,user)['people']}
    from fixed_shift import effective
    allowed.update(entry['user_id'] for entry in effective(db,[],day))
    values=[{key:entry[key] for key in ('user_id','department','shift')} for entry in effective(db,[entry.model_dump(mode='json') for entry in payload.assignments],day)]
    for entry in values:
        if entry['user_id'] not in allowed and entry!=previous.get(entry['user_id']):raise HTTPException(422,'所选人员不在参与排班的在用部门名册中，请刷新后重试')
    if not row:row=MonthlyShiftPlan(month=day,revision=0);db.add(row)
    row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'本月排班已被其他人创建，请刷新后重试')
    return serialize(db,row,day)

def my_plan(db,user,month):
    day=month_key(month)
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    row=db.get(MonthlyShiftPlan,day) if ready(db) else None
    # 只取本人信息，不向工作台传输其他人员的排班或姓名。
    from fixed_shift import effective
    entry=next((value for value in effective(db,row.assignments if row else [],day) if value['user_id']==str(user.id)),None)
    return api_time({'ready':ready(db),'month':month,'assignment':{**entry,'name':user.full_name or user.username} if entry else None,'shifts':SHIFTS,'departments':DEPARTMENTS,'updated_at':row.updated_at if row and entry else None})
