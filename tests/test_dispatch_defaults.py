from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment


def test_initial_rules_dynamic_hr_and_custom_defaults(environment,monkeypatch):
    db,(admin,receiver,other)=environment
    from department_models import Department,DepartmentMember
    import resource_request_dispatch_defaults as service
    monkeypatch.setattr(service,'can_manage',lambda db,u:u.id==admin.id)
    annotation=Department(id=uuid4(),name='标注项目部',aliases=[],revision=1)
    hr=Department(id=uuid4(),name='HR部',aliases=[],revision=1)
    admin.username='williamzhao';receiver.full_name='王露'
    db.add_all([annotation,hr]);db.flush()
    db.add_all([DepartmentMember(department_id=annotation.id,user_id=receiver.id),DepartmentMember(department_id=hr.id,user_id=admin.id),DepartmentMember(department_id=hr.id,user_id=other.id)]);db.commit()
    assert service.catalog(db,admin,'circle')['user_ids']==[str(receiver.id)]
    assert service.catalog(db,admin,'post')['user_ids']==[str(other.id)]
    # 发帖可以选择全公司人员，发圈不能选标注部门以外人员。
    saved=service.save(db,admin,'post',service.DefaultWrite(user_ids=[receiver.id],revision=0))
    assert saved['user_ids']==[str(receiver.id)]
    with pytest.raises(HTTPException) as stale:service.save(db,admin,'post',service.DefaultWrite(user_ids=[],revision=0))
    assert stale.value.status_code==409
    cleared=service.save(db,admin,'post',service.DefaultWrite(user_ids=[],revision=saved['revision']))
    assert cleared['user_ids']==[] and not cleared['rule_based']
    restored=service.save(db,admin,'post',service.DefaultWrite(user_ids=None,revision=cleared['revision']))
    assert restored['user_ids']==[str(other.id)] and restored['rule_based']
    with pytest.raises(HTTPException):service.save(db,admin,'circle',service.DefaultWrite(user_ids=[other.id],revision=0))
    with pytest.raises(HTTPException) as denied:service.save(db,receiver,'post',service.DefaultWrite(user_ids=[],revision=restored['revision']))
    assert denied.value.status_code==403
