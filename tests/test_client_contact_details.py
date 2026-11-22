from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from models import Client,SubClient
from schemas import ClientContactPersonInput
from client_contact_people import replace_details,attach,ensure,ClientContactPersonDetail
from tools.apply_client_contact_details_migration import apply_migration


@pytest.mark.parametrize('is_sub', [False, True])
def test_affiliation_save_reload_and_legacy_update(environment, is_sub):
    from tools.apply_client_contact_affiliation_migration import apply_migration
    from client_contact_people import ClientContactPersonAffiliation
    from consultation_contacts import sync_contacts
    db, _ = environment
    ClientContactPersonAffiliation.__table__.drop(db.connection(), checkfirst=True)
    apply_migration(db.connection())
    apply_migration(db.connection())
    client = Client(id=uuid4(), client_code='AFFILIATION', client_name='客户')
    db.add(client)
    db.flush()
    owner = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='AFF-SUB') if is_sub else client
    db.add(owner)
    db.flush()
    replace_details(db, owner, [ClientContactPersonInput(name='甲', department=' 采购部 ', company=' 公司A ')])
    db.commit()
    sync_contacts(db, client.id, owner.id if is_sub else None, [ClientContactPersonInput(name='甲')])
    db.expire_all()
    attach(db, sub_clients=[owner]) if is_sub else attach(db, clients=[owner])
    assert owner.contact_people[0]['department'] == '采购部'
    assert owner.contact_people[0]['company'] == '公司A'
    replace_details(db, owner, [ClientContactPersonInput(name='甲', department='法务部', company='')])
    db.commit()
    attach(db, sub_clients=[owner]) if is_sub else attach(db, clients=[owner])
    assert owner.contact_people[0]['department'] == '法务部'
    assert owner.contact_people[0]['company'] == ''

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


def test_multiple_contact_methods_preserve_full_details(environment):
    db, _ = environment
    owner = Client(id=uuid4(), client_code='MULTI-CONTACT', client_name='客户', client_short_name='客户')
    db.add(owner)
    db.flush()
    methods = '微信：example\n邮箱：' + 'a' * 90 + '@example.test\n自定义：example'
    replace_details(db, owner, [ClientContactPersonInput(name='甲', contact_method=methods)])
    db.commit()
    db.expire_all()
    attach(db, clients=[owner])
    assert owner.contact_people[0]['contact_method'] == methods
    assert owner.manager_contact == '微信：example'


def test_job_title_is_per_contact_and_older_payloads_preserve_it(environment):
    from consultation_contacts import sync_contacts
    from client_contact_people import ClientContactPersonJobTitle
    from tools.apply_client_contact_job_title_migration import apply_migration

    db, _ = environment
    ClientContactPersonJobTitle.__table__.drop(db.connection())
    apply_migration(db.connection())
    apply_migration(db.connection())
    owner = Client(id=uuid4(), client_code='JOB-TITLES', client_name='测试', client_short_name='测试')
    db.add(owner)
    db.flush()
    contacts = [
        ClientContactPersonInput(name='甲', job_title=' 采购经理 '),
        ClientContactPersonInput(name='乙', job_title='法务'),
    ]
    replace_details(db, owner, contacts)
    db.commit()
    sync_contacts(db, owner.id, None, [ClientContactPersonInput(name='甲')])
    replace_details(db, owner, [ClientContactPersonInput(name='乙'), ClientContactPersonInput(name='甲', job_title='')])
    db.commit()
    db.expire_all()
    attach(db, clients=[owner])
    assert [(person['name'], person.get('job_title')) for person in owner.contact_people] == [('乙', '法务'), ('甲', None)]
