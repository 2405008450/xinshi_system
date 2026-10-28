"""仅处理用户明确点名的赵震锋行政部总经理配置。"""
from fastapi import HTTPException
from models import AppUser
from department_models import Department,DepartmentMember
from chat_time import now


def inspect_target(db):
    people=db.query(AppUser).filter_by(full_name='赵震锋',is_active=True,is_deleted=False).all()
    departments=db.query(Department).filter(Department.name.in_(['行政部','行政部门'])).all()
    if len(people)!=1:raise HTTPException(409,'赵震锋在用人员匹配不唯一，未作任何修改')
    if len(departments)!=1:raise HTTPException(409,'行政部门匹配不唯一，未作任何修改')
    person,department=people[0],departments[0]
    link=db.get(DepartmentMember,(department.id,person.id))
    return person,department,link


def configure(db):
    db.query(Department).order_by(Department.id).with_for_update().all()
    person,department,link=inspect_target(db)
    if link and link.position=='总经理':return {'changed':False,'name':person.full_name,'department':department.name,'position':'总经理'}
    if not link:link=DepartmentMember(department_id=department.id,user_id=person.id);db.add(link)
    link.position='总经理';link.updated_at=now()
    department.revision+=1;department.updated_at=now();department.updated_by=None
    db.flush()
    return {'changed':True,'name':person.full_name,'department':department.name,'position':'总经理'}
