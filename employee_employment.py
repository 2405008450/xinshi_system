"""人员入职日期与公司年度年假额度；按香港业务日期计算。"""
from datetime import date,datetime
import calendar
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import Date,DateTime,ForeignKey,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from chat_time import now,api_time


class EmployeeEmployment(Base):
    __tablename__='employee_employment'
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),primary_key=True)
    hire_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


def ready(db):return inspect(db.connection()).has_table(EmployeeEmployment.__tablename__)


def annual_days(hire_date,on_date=None):
    """首年上半年1天、下半年0天；每个周年再过三个月加1天，上限10天。"""
    day=on_date or now().date()
    if hire_date is None:return None
    if hire_date>day:return 0
    first_year=int((hire_date.month,hire_date.day)<=(6,30))
    increments=sum(grant is not None and grant<=day for grant in (anniversary_grant(hire_date,year) for year in range(1,11)))
    return min(10,first_year+increments)


def anniversary_grant(hire_date,years):
    # 先取周年（闰日遇非闰年为2月末），再顺延三个月；月底截到目标月最后一天。
    if hire_date.year+years>9999:return None
    anniversary=date(hire_date.year+years,hire_date.month,min(hire_date.day,calendar.monthrange(hire_date.year+years,hire_date.month)[1]))
    month_index=anniversary.year*12+anniversary.month-1+3
    year,month=divmod(month_index,12);month+=1
    if year>9999:return None
    return date(year,month,min(anniversary.day,calendar.monthrange(year,month)[1]))


def values(hire_date,on_date=None):
    day=on_date or now().date()
    next_increase=next((grant for grant in (anniversary_grant(hire_date,year) for year in range(1,11)) if grant is not None and grant>day),None) if hire_date and annual_days(hire_date,day)<10 else None
    return {'hire_date':hire_date,'annual_leave_year':day.year,'annual_leave_days':annual_days(hire_date,day),'annual_leave_next_increase':next_increase}


def attach(db,users):
    """人员列表一次批量读取，避免逐人查询。"""
    ids=[user.id for user in users]
    records={row.user_id:row.hire_date for row in db.query(EmployeeEmployment).filter(EmployeeEmployment.user_id.in_(ids)).all()} if ids and ready(db) else {}
    day=now().date()
    for user in users:
        for key,value in values(records.get(user.id),day).items():setattr(user,key,value)
    return users


def write(db,user,hire_date):
    """与用户新增/编辑共用事务；不单独提交。"""
    if not ready(db):
        if hire_date is not None:raise HTTPException(503,'入职时间数据表尚未初始化')
        return
    db.flush()
    row=db.get(EmployeeEmployment,user.id)
    if row is None:
        if hire_date is None:return
        row=EmployeeEmployment(user_id=user.id);db.add(row)
    row.hire_date=hire_date;row.updated_at=now()


def allowances(db,user_ids,year):
    day=date(year,12,31)
    records={row.user_id:row.hire_date for row in db.query(EmployeeEmployment).filter(EmployeeEmployment.user_id.in_(user_ids)).all()} if user_ids and ready(db) else {}
    # 当年尚未正式入职的人员不提前发额度。
    effective=min(day,now().date()) if year==now().year else day
    return {str(uid):api_time(values(records.get(uid),effective)) for uid in user_ids}
