"""人事管理仅限行政部门，超级管理员身份不绕过部门限制。"""
from fastapi import HTTPException
from models import AppUser

def can_manage_hr(db,user):
    if not user or not user.is_active or user.is_deleted:return False
    from organization_service import department_condition
    return bool(db.query(AppUser.id).filter(AppUser.id==user.id,department_condition(db,['行政部','行政部门'])).first())

def require_hr(db,user):
    if not can_manage_hr(db,user):raise HTTPException(403,'仅行政部门可访问人事管理或调整排班安排')
