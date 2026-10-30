"""行政部组织架构权限、跨部门归属、撤销和额外权限隔离；仅内存 SQLite。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_chat_participant_access import environment
from department_models import Department,DepartmentMember
from permission_service import get_user_permission_codes
import department_service
import work_report_access


@pytest.fixture
def organization(environment,monkeypatch):
 db,(admin,person,zhao)=environment
 admin.department='行政部';person.department='项目部';zhao.username='williamzhao'
 dept=Department(name='行政部');db.add(dept);db.commit()
 monkeypatch.setattr('notification_ws.broadcast_to_users',lambda *args:None)
 return db,admin,person,zhao,dept


def test_administration_dynamic_permission_and_revocation(organization):
 db,admin,person,zhao,dept=organization
 granted={'system:users:read','system:organization:write'}
 assert set(get_user_permission_codes(db,admin.id))==granted
 assert department_service.catalog(db,admin)['canManage']
 assert not department_service.can_manage(db,person)
 admin.is_active=False;db.commit();assert get_user_permission_codes(db,admin.id)==[]
 admin.is_active=True;admin.is_deleted=True;db.commit();assert get_user_permission_codes(db,admin.id)==[]
 admin.is_deleted=False;admin.department='项目部';db.commit();assert get_user_permission_codes(db,admin.id)==[]
 link=DepartmentMember(department_id=dept.id,user_id=admin.id);db.add(link);db.commit()
 assert set(get_user_permission_codes(db,admin.id))==granted
 assert department_service.can_manage(db,admin)
 db.delete(link);db.commit();assert get_user_permission_codes(db,admin.id)==[]
 assert not department_service.can_manage(db,admin)


def test_administration_can_edit_person_office_and_department_without_mail_role_password_access(organization):
 db,admin,person,zhao,dept=organization
 from database import get_db
 from routers import auth,users,departments
 import office_management as office
 from tools.apply_office_management_migration import apply_migration
 apply_migration(db.connection());db.commit()
 app=FastAPI();app.include_router(users.router);app.include_router(departments.router);app.include_router(office.router)
 app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[auth.get_current_user]=lambda:admin
 with TestClient(app) as client:
  assert client.put('/users/'+str(person.id),json={'full_name':'行政调整人员'}).status_code==200
  assert client.post('/office-management',json={'city':'杭州','name':'杭州办公室','seats':12}).status_code==200
  assert client.post('/departments',json={'name':'新组织部门'}).status_code==200
  assert client.get('/users/'+str(person.id)+'/mail-account').status_code==403
  assert client.put('/users/'+str(person.id)+'/password',json={'password':'test-only-password'}).status_code==403
  app.dependency_overrides[auth.get_current_user]=lambda:person
  assert client.put('/users/'+str(zhao.id),json={'full_name':'不应保存'}).status_code==403
  assert client.post('/departments',json={'name':'不应创建'}).status_code==403
  assert client.post('/office-management',json={'city':'苏州','name':'不应创建','seats':1}).status_code==403


def test_report_settings_keep_original_configurator_not_current_operator(organization):
 db,admin,person,zhao,dept=organization
 assert work_report_access.can_configure(admin,db)
 assert not work_report_access.can_configure(person,db)
 assert work_report_access.settings(db,admin)['configurator_id']==str(zhao.id)
 row=work_report_access.save_rule(db,admin,work_report_access.AccessRuleWrite(name='行政配置范围',viewer_ids=[person.id],senders_all=True))
 assert str(zhao.id) in row['viewer_ids'] and str(admin.id) not in row['viewer_ids']
 assert db.get(work_report_access.WorkReportAccessRule,row['id']).updated_by==admin.id
 admin.department='项目部';db.commit()
 assert not work_report_access.can_configure(admin,db)
