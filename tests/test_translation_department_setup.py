from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import AppUser
from department_models import Department, DepartmentMember
from tools.ensure_translation_project_department import ensure, USERNAMES


def test_department_setup_additive_repeatable_and_original_memberships_preserved(environment):
    db,_=environment
    users=[AppUser(id=uuid4(),username=name,full_name=name,password_hash='disabled',is_active=True,department='项目部') for name in USERNAMES]
    db.add_all(users);db.commit()
    assert len(ensure(db)['added'])==5;db.commit()
    dept=db.query(Department).filter_by(name='笔译项目部').one()
    assert db.query(DepartmentMember).filter_by(department_id=dept.id).count()==5
    assert all(u.department=='项目部' for u in users)
    revision=dept.revision
    assert ensure(db)['added']==[];db.commit()
    assert dept.revision==revision
