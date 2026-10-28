"""月度排班权限、独立部门和并发校验；仅隔离 SQLite。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_chat_participant_access import environment
from department_models import Department,DepartmentMember
import monthly_shift as service

def setup(db,users):
    rows=[Department(id=uuid4(),name=name,aliases=[],revision=1) for name in ['行政部','销售部','客户部','项目部','标注项目部','HR部','排版','IT部']]
    db.add_all(rows);db.flush()
    users[0].department='行政部';users[1].department='销售部';users[2].department='项目部';db.commit()
    return {row.name:row for row in rows}

def payload(user,revision=0,department='customer',shift='early'):
    return service.PlanWrite(revision=revision,assignments=[{'user_id':user.id,'department':department,'shift':shift}])

def test_administration_participates_in_all_schedule_periods(environment):
    import weekly_shift
    import weekend_duty
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    data=service.directory(db,admin)
    administrator=next(row for row in data['people'] if row['id']==str(admin.id))
    assert administrator['departments']==[{'id':'administration','name':'行政部'}]
    assignment={'user_id':admin.id,'department':'administration','shift':'early'}
    monthly=service.save_plan(db,admin,'2026-11',service.PlanWrite(revision=0,assignments=[assignment]))
    weekly=weekly_shift.save_plan(db,admin,'2026-11-02',weekly_shift.WeeklyPlanWrite(revision=0,assignments=[assignment]))
    duty=weekend_duty.save_plan(db,admin,'2026-11',weekend_duty.DutyWrite(revision=0,assignments=[{'user_id':admin.id,'department':'administration','date':'2026-11-01'}]))
    for result in (monthly,weekly,duty):
        assert result['assignments'][0]['department']=='administration'
        assert {'code':'administration','label':'行政部'} in result['departments']
    assert weekly_shift.my_plan(db,admin,'2026-11-02')['assignment']['department']=='administration'

def test_admin_only_and_sales_separate_from_customer_globally(environment):
    from organization_service import directory,department_condition
    from hr_access import can_manage_hr
    db,users=environment;setup(db,users)
    catalog=directory(db,users[0]);sales=next(row for row in catalog['people'] if row['id']==str(users[1].id))
    assert [row['name'] for row in sales['departments']]==['销售部']
    assert db.query(type(users[1])).filter(department_condition(db,['客户部'])).count()==0
    scheduled=service.directory(db,users[0]);sales=next(row for row in scheduled['people'] if row['id']==str(users[1].id))
    assert sales['departments']==[{'id':'customer','name':'客户/销售部'}]
    users[2].department='IT部';db.commit()
    it_person=next(row for row in service.directory(db,users[0])['people'] if row['id']==str(users[2].id))
    assert it_person['departments']==[{'id':'it','name':'IT部门'}]
    assert can_manage_hr(db,users[0]) and not can_manage_hr(db,users[1])
    for user in users[1:]:
        for operation in [lambda:service.directory(db,user),lambda:service.get_plan(db,user,'2026-11'),lambda:service.save_plan(db,user,'2026-11',payload(user))]:
            with pytest.raises(HTTPException) as error:operation()
            assert error.value.status_code==403
    # 跨部门行政成员也有权限；账号停用立即失效。
    db.add(DepartmentMember(department_id=db.query(Department).filter_by(name='行政部').one().id,user_id=users[1].id,position=''));db.commit()
    assert can_manage_hr(db,users[1])
    users[1].is_active=False;db.commit();assert not can_manage_hr(db,users[1])

def test_month_unique_move_return_history_isolation_and_mine_only(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    assert service.get_plan(db,admin,'2026-11')['revision']==0
    saved=service.save_plan(db,admin,'2026-11',payload(person))
    assert saved['revision']==1 and len(saved['assignments'])==1
    with pytest.raises(HTTPException) as error:service.save_plan(db,admin,'2026-11',payload(person))
    assert error.value.status_code==409
    saved=service.save_plan(db,admin,'2026-11',payload(person,1,'project','late'))
    assert saved['assignments'][0]['department']=='project' and len(saved['assignments'])==1
    assert service.my_plan(db,person,'2026-11')['assignment']['shift']=='late'
    assert service.my_plan(db,other,'2026-11')['assignment'] is None
    assert 'assignments' not in service.my_plan(db,other,'2026-11')
    assert service.get_plan(db,admin,'2026-10')['assignments']==[]
    assert service.get_plan(db,admin,'2026-11')['updated_at'].utcoffset().total_seconds()==28800
    assert service.save_plan(db,admin,'2026-11',service.PlanWrite(revision=2,assignments=[]))['assignments']==[]

def test_duplicate_invalid_people_remote_shift_and_migration(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    with pytest.raises(ValidationError):service.PlanWrite(revision=0,assignments=[payload(person).assignments[0]]*2)
    with pytest.raises(ValidationError):payload(person,department='hr',shift='customer_remote')
    unknown=service.PlanWrite(revision=0,assignments=[{'user_id':uuid4(),'department':'customer','shift':'early'}])
    with pytest.raises(HTTPException):service.save_plan(db,admin,'2026-11',unknown)
    for month in ['2026-13','2026-1','2026-11-01']:
        with pytest.raises(HTTPException):service.get_plan(db,admin,month)
    from tools.apply_monthly_shift_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
    assert service.ready(db)

def test_api_denies_nonadmin_even_if_superadmin_and_no_person_selector(environment):
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    from models import Role,UserRole
    role=Role(id=uuid4(),role_name='超级管理员');db.add(role);db.flush()
    db.add(UserRole(id=uuid4(),user_id=other.id,role_id=role.id));db.commit()
    service.save_plan(db,admin,'2026-11',payload(person))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:other
    with TestClient(app) as client:
        assert client.get('/monthly-shifts?month=2026-11').status_code==403
        assert client.get('/monthly-shifts/directory').status_code==403
        assert client.put('/monthly-shifts?month=2026-11',json=payload(person).model_dump(mode='json')).status_code==403
        assert client.get(f'/monthly-shifts/mine?month=2026-11&user_id={person.id}').json()['assignment'] is None
