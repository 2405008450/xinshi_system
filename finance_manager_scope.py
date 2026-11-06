"""财务主表与对账单复用同一客户经理筛选条件。"""
from models import AppUser

def manager_fields(db,user,manager_ids=None,only_mine=False,client_manager=None):
    ids=list(dict.fromkeys(manager_ids)) if isinstance(manager_ids,list) else []
    if ids:
        people=db.query(AppUser).filter(AppUser.id.in_(ids)).all()
        return {'finance_manager_ids':{'value':{'ids':[str(uid) for uid in ids],'names':[name for person in people for name in (person.full_name,person.username)]}}}
    if only_mine:
        return {'finance_manager_self':{'value':{'id':str(user.id),'names':[user.full_name,user.username]}}}
    if client_manager and client_manager.strip():return {'client_manager':{'op':'contains','value':client_manager.strip()}}
    return {}
