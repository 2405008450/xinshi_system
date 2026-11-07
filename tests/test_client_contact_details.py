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
