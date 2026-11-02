from uuid import uuid4
import pytest
from test_chat_participant_access import environment
from models import AppUser, Role, UserRole
from department_models import Department, DepartmentMember
from tools.ensure_interpretation_project_department import configure, FIXED, NAME


def test_selected_roles_memberships_and_additive_idempotency(environment):
    db, _ = environment
    users = {name: AppUser(id=uuid4(),username=name,full_name=name,password_hash='disabled',
        department='原部门',is_active=True,is_deleted=False) for name in
        [*FIXED,'customer','sales','manager','unrelated','inactive','deleted']}
    users['inactive'].is_active=False
    users['deleted'].is_deleted=True
    db.add_all(users.values())
    role=Role(id=uuid4(),role_name='客户专员')
    original=Department(id=uuid4(),name='原部门',aliases=[],revision=1)
    db.add_all([role,original]);db.flush()
    for name in ['customer','inactive','deleted']:
        db.add(UserRole(id=uuid4(),user_id=users[name].id,role_id=role.id))
    users['sales'].department='销售'
    db.add(DepartmentMember(department_id=original.id,user_id=users['manager'].id,position='客户经理'))
    db.commit()
    expected=FIXED|{'customer','sales','manager'}
    preview=configure(db,expected)
    assert set(preview['added'])==expected
    assert db.query(Department).filter_by(name=NAME).count()==0
    assert configure(db,expected,True)['total_selected']==7
    db.commit()
    department=db.query(Department).filter_by(name=NAME).one()
    assert db.query(DepartmentMember).filter_by(department_id=department.id).count()==7
    assert db.get(DepartmentMember,(original.id,users['manager'].id)).position=='客户经理'
    assert users['customer'].department=='原部门'
    revision=department.revision
    assert configure(db,expected,True)['added']==[]
    db.commit()
    assert department.revision==revision
    with pytest.raises(ValueError):
        configure(db,{'customer'},True)
