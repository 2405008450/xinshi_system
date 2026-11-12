from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI,HTTPException,Request
from fastapi.testclient import TestClient
from tests.test_chat_participant_access import environment
from models import Client,SubClient
from schemas import ClientContactPersonInput
from client_contact_people import replace_details,ClientContactPersonDetail,owner_rows
from client_contact_privacy import can_view_client_contacts,ClientContactPrivacyMiddleware
from project_client_contact_details import contact_details,save_project_contact_details
from routers.client_management_window import read_window
from fastapi import Response


@pytest.mark.parametrize('department,allowed',[('客户部',True),('销售部',True),('销售',True),('行政部',True),('IT部',False),('项目部',False),('',False)])
def test_department_access_is_explicit(environment,department,allowed):
    db,(user,_,_)=environment
    user.department=department
    assert can_view_client_contacts(db,user) is allowed


def test_secondary_department_membership_is_supported(environment):
    db,(user,_,_)=environment
    from department_models import Department,DepartmentMember
    user.department='项目部'
    department=Department(id=uuid4(),name='行政部',aliases=[])
    db.add(department);db.flush();db.add(DepartmentMember(department_id=department.id,user_id=user.id));db.flush()
    assert can_view_client_contacts(db,user)


def test_management_window_masks_contact_data_and_resolves_ambiguous_names(environment, monkeypatch):
    db, (user, _, _) = environment
    first = Client(id=uuid4(), client_code='WINDOW-1', client_name='客户一', client_short_name='同名客户')
    second = Client(id=uuid4(), client_code='WINDOW-2', client_name='客户二', client_short_name='同名客户')
    db.add_all([first, second]); db.flush()
    child = SubClient(id=uuid4(), parent_client_id=first.id, sub_client_code='WINDOW-SUB', client_name='子客户', client_short_name='子客户')
    db.add(child); db.flush()
    replace_details(db, first, [ClientContactPersonInput(name='张晓明', contact_method='+86 13812345678', description='备用电话 13911112222')])
    db.flush()
    user.department = '项目部'
    response = Response()
    result = read_window(response, client_id=first.id, short_name='', db=db, user=user)
    assert result['contacts'] == [{'name': '张', 'method': '861'}]
    assert not result['can_manage']
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert len(read_window(Response(), short_name='同名客户', db=db, user=user)['matches']) == 2
    with pytest.raises(HTTPException) as error:
        read_window(Response(), client_id=second.id, sub_client_id=child.id, short_name='', db=db, user=user)
    assert error.value.status_code == 404
    user.department = '销售部'
    monkeypatch.setattr('routers.client_management_window.user_has_permission', lambda *args: True)
    full = read_window(Response(), client_id=first.id, short_name='', db=db, user=user)
    assert full['contacts'][0]['name'] == '张晓明'
    assert full['contacts'][0]['method'] == '+86 13812345678'
    assert full['can_manage']


def test_json_privacy_covers_nested_clients_projects_and_saved_email_subject():
    app=FastAPI();app.add_middleware(ClientContactPrivacyMiddleware)
    from fastapi.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware,minimum_size=1)
    source={'manager_contact':'secret-phone','contact_people':[{'name':'甲','contact_method':'secret-email','description':'采购'}],
        'project':{'client_contact_method':'secret-wechat','email_subject_preview':'客户 secret-phone 项目'}}
    @app.get('/sample')
    def sample(request:Request,allowed:bool=False):
        request.state.client_contacts_visible=allowed
        return source
    with TestClient(app) as client:
        denied=client.get('/sample')
        assert 'secret-' not in denied.text
        assert denied.json()['contact_people'][0]['name']=='甲'
        assert denied.json()['contact_people'][0]['description']=='采购'
        assert denied.headers['cache-control']=='private, no-store'
        assert client.get('/sample?allowed=true').json()==source
    assert source['manager_contact']=='secret-phone' # 脱敏不改ORM或业务源数据。


@pytest.mark.parametrize('is_sub',[False,True])
def test_save_details_is_scoped_to_selected_person_and_preserves_other_contacts(environment,is_sub):
    db,_=environment;db.info['client_contacts_visible']=True
    client=Client(id=uuid4(),client_code='SCOPE-C',client_name='客户',client_short_name='客户')
    db.add(client);db.flush()
    owner=SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code='SCOPE-S',client_name='子客户',client_short_name='子客户') if is_sub else client
    db.add(owner);db.flush()
    replace_details(db,owner,[ClientContactPersonInput(name='甲',contact_method='phone-A',description='原说明'),ClientContactPersonInput(name='乙',contact_method='phone-B')]);db.commit()
    before=contact_details(db,owner)
    data={'client_id':client.id,'sub_client_id':owner.id if is_sub else None,'contact_name':'甲','client_contact_method':'email-A','client_contact_description':'新说明','client_contact_version':before[0]['version']}
    save_project_contact_details(db,data);db.commit()
    after=contact_details(db,owner)
    assert after[0]['contact_method']=='email-A' and after[0]['description']=='新说明'
    assert after[1]['contact_method']=='phone-B'
    assert 'client_contact_method' not in data
    stale={**data,'client_contact_method':'old','client_contact_version':before[0]['version']}
    with pytest.raises(HTTPException) as conflict:save_project_contact_details(db,stale)
    assert conflict.value.status_code==409


def test_hidden_contacts_are_not_erased_by_client_or_project_edits(environment):
    db,_=environment
    owner=Client(id=uuid4(),client_code='PRIVATE',client_name='客户',client_short_name='客户')
    db.add(owner);db.flush()
    replace_details(db,owner,[ClientContactPersonInput(name='甲',contact_method='keep-phone',description='旧说明')]);db.commit()
    db.info['client_contacts_visible']=False
    replace_details(db,owner,[ClientContactPersonInput(name='甲',contact_method='',description='客户编辑说明')]);db.flush()
    before=contact_details(db,owner)[0]
    assert before['contact_method']=='keep-phone' and owner.manager_contact=='keep-phone'
    save_project_contact_details(db,{'client_id':owner.id,'contact_name':'甲','client_contact_version':before['version'],'client_contact_description':'项目编辑说明'})
    db.flush()
    assert contact_details(db,owner)[0]['contact_method']=='keep-phone'
    with pytest.raises(HTTPException) as denied:
        save_project_contact_details(db,{'client_id':owner.id,'contact_name':'甲','client_contact_version':contact_details(db,owner)[0]['version'],'client_contact_method':'not-allowed'})
    assert denied.value.status_code==403


def test_new_contact_without_customer_data_reuses_existing_tables(environment):
    db,_=environment;db.info['client_contacts_visible']=True
    owner=Client(id=uuid4(),client_code='NEW-CONTACT',client_name='新客户',client_short_name='新客户')
    db.add(owner);db.flush()
    save_project_contact_details(db,{'client_id':owner.id,'contact_name':'新联系人','client_contact_version':'new','client_contact_method':'new-phone','client_contact_description':'销售对接'})
    db.flush()
    assert contact_details(db,owner)[0]['contact_method']=='new-phone'


def test_project_export_files_do_not_expose_contacts_for_other_departments():
    from io import BytesIO
    from openpyxl import load_workbook
    from tests.test_project_exports import project
    from tests.test_translation_project_export import sample_project
    from project_export_service import projects_to_xlsx
    from translation_project_export_service import translation_projects_to_xlsx
    oral=project(manager_contact='secret-export-phone',email_subject_preview='secret-export-subject')
    written=sample_project(with_sub_order=False)
    written.manager_contact='secret-export-phone';written.email_subject_preview='secret-export-subject'
    for content in (projects_to_xlsx('interpretation','projects',[[oral]],contacts_visible=False),translation_projects_to_xlsx([[written]],contacts_visible=False)):
        workbook=load_workbook(BytesIO(content),read_only=True)
        values=str([list(sheet.values) for sheet in workbook.worksheets])
        assert 'secret-export-' not in values


def test_authenticated_contact_endpoint_applies_department_to_response(environment,monkeypatch):
    db,(user,_,_)=environment
    import routers.auth as auth
    from routers.client_contact_people import router
    from database import get_db
    monkeypatch.setattr(auth,'get_user_from_token_value',lambda *_:user)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *_:['projects:write'])
    owner=Client(id=uuid4(),client_code='HTTP-PRIVATE',client_name='客户',client_short_name='客户')
    db.add(owner);db.flush();db.info['client_contacts_visible']=True
    replace_details(db,owner,[ClientContactPersonInput(name='甲',contact_method='http-private-phone',description='采购')]);db.commit()
    app=FastAPI();app.add_middleware(ClientContactPrivacyMiddleware);app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:
        headers={'Authorization':'Bearer isolated-contact-test'}
        user.department='客户部'
        allowed=client.get('/client-contact-people',params={'client_id':str(owner.id)},headers=headers)
        assert allowed.status_code==200 and allowed.json()['can_view_contacts'] is True
        assert allowed.json()['contact_people'][0]['contact_method']=='http-private-phone'
        user.department='项目部'
        denied=client.get('/client-contact-people',params={'client_id':str(owner.id)},headers=headers)
        assert denied.status_code==200 and denied.json()['can_view_contacts'] is False
        assert 'http-private-phone' not in denied.text
        assert denied.json()['contact_names']==['甲']
