from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from models import Client,SubClient
from schemas import ClientContactPersonInput
from client_contact_people import replace_details,attach,ensure,ClientContactPersonDetail
from tools.apply_client_contact_details_migration import apply_migration

@pytest.mark.parametrize('is_sub',[False,True])
def test_details_are_per_person_preserved_after_project_add_and_reload(environment,is_sub):
    db,_=environment
    db.autoflush=False
    client=Client(id=uuid4(),client_code='CONTACT',client_name='客户',client_short_name='客户',client_manager='原联系人',manager_contact='旧号码')
    db.add(client);db.flush()
    owner=SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code='SUB-C',client_name='子客户',client_short_name='子客户') if is_sub else client
    db.add(owner);db.flush()
    values=[ClientContactPersonInput(name='甲',contact_method='甲电话',description='甲说明'),ClientContactPersonInput(name='乙',contact_method='乙邮箱',description='乙说明')]
    replace_details(db,owner,values);db.commit();db.expire_all()
    attach(db,sub_clients=[owner]) if is_sub else attach(db,clients=[owner])
    assert owner.contact_names==['甲','乙'] and owner.contact_people[1]['description']=='乙说明'
    assert owner.manager_contact=='甲电话'
    ensure(db,owner,'丙');db.commit();attach(db,sub_clients=[owner]) if is_sub else attach(db,clients=[owner])
    assert owner.contact_people[0]['contact_method']=='甲电话' and owner.contact_people[-1]['contact_method']==''
    replace_details(db,owner,list(reversed(values)));db.commit();attach(db,sub_clients=[owner]) if is_sub else attach(db,clients=[owner])
    assert owner.contact_people[0]['description']=='乙说明' and owner.manager_contact=='乙邮箱'

def test_legacy_contact_and_idempotent_migration(environment):
    db,_=environment
    ClientContactPersonDetail.__table__.drop(db.connection());apply_migration(db.connection());apply_migration(db.connection())
    owner=Client(id=uuid4(),client_code='LEGACY',client_name='客户',client_short_name='客户',client_manager='历史姓名',manager_contact='历史号码')
    db.add(owner);db.commit();attach(db,clients=[owner])
    assert owner.contact_people==[{'name':'历史姓名','contact_method':'历史号码','description':''}]


@pytest.mark.parametrize('is_sub',[False,True])
@pytest.mark.parametrize('visible',[False,True])
def test_customer_create_and_edit_contacts_without_autoflush(environment,is_sub,visible):
    from sqlalchemy import event
    from schemas import ClientCreate,ClientUpdate,SubClientCreate,SubClientUpdate
    import crud
    db,_=environment
    db.autoflush=False
    db.info['client_contacts_visible']=visible
    def assign_ids(session,*_):
        for item in session.new:
            if isinstance(item,(Client,SubClient)) and item.id is None:item.id=uuid4()
    event.listen(db,'before_flush',assign_ids)
    first=ClientContactPersonInput(name='新增联系人',contact_method='新增电话',description='采购')
    if is_sub:
        parent=Client(id=uuid4(),client_code='PARENT',client_name='母客户',client_short_name='母客户')
        db.add(parent);db.flush()
        owner=crud.create_sub_client(db,SubClientCreate(parent_client_id=parent.id,sub_client_code='PARENT.001',client_name='子客户',client_short_name='子客户',contact_people=[first]))
    else:
        owner=crud.create_client(db,ClientCreate(client_code='CREATE',client_name='新增客户',client_short_name='新增客户',contact_people=[first]))
    second=ClientContactPersonInput(name='第二联系人',contact_method='第二电话',description='财务')
    schema=SubClientUpdate if is_sub else ClientUpdate
    update=crud.update_sub_client if is_sub else crud.update_client
    update(db,owner.id,schema(contact_people=[second,first]))
    db.expire_all()
    owner=db.get(SubClient if is_sub else Client,owner.id)
    attach(db,sub_clients=[owner]) if is_sub else attach(db,clients=[owner])
    assert [p['name'] for p in owner.contact_people]==['第二联系人','新增联系人']
    assert owner.contact_people[0]['description']=='财务'
    assert owner.contact_people[0]['contact_method']==('第二电话' if visible else '')


@pytest.mark.parametrize('is_sub',[False,True])
@pytest.mark.parametrize('visible',[False,True])
def test_project_new_contact_without_autoflush(environment,is_sub,visible):
    from project_client_contact_details import save_project_contact_details,contact_details
    db,_=environment
    db.autoflush=False
    db.info['client_contacts_visible']=visible
    parent=Client(id=uuid4(),client_code='PROJECT-PARENT',client_name='客户',client_short_name='客户')
    db.add(parent);db.flush()
    owner=SubClient(id=uuid4(),parent_client_id=parent.id,sub_client_code='PROJECT-SUB',client_name='子客户',client_short_name='子客户') if is_sub else parent
    db.add(owner);db.flush()
    payload={'client_id':parent.id,'contact_name':'项目新联系人','client_contact_version':'new','client_contact_description':'项目采购'}
    if is_sub:payload['sub_client_id']=owner.id
    if visible:payload['client_contact_method']='项目电话'
    save_project_contact_details(db,payload)
    db.commit();db.expire_all()
    saved=contact_details(db,owner)[0]
    assert saved['description']=='项目采购'
    assert saved['contact_method']==('项目电话' if visible else '')
