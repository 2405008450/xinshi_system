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


@pytest.mark.parametrize('is_sub', [False, True])
def test_translation_project_create_and_update_new_contact_without_autoflush(environment, is_sub):
    import crud
    from sqlalchemy import event
    from client_contact_people import owner_rows
    from project_client_contact_details import contact_details
    from schemas import TranslationProjectCreate, TranslationProjectUpdate

    db, (actor, _, _) = environment
    db.autoflush = False
    db.info['client_contacts_visible'] = True

    def fill_uuid_ids(session, *_):
        for row in session.new:
            if hasattr(row, 'id') and row.id is None:
                row.id = uuid4()

    event.listen(db, 'before_flush', fill_uuid_ids)
    parent = Client(id=uuid4(), client_code='TP-CONTACT-P', client_name='笔译客户', client_short_name='笔译客户')
    db.add(parent)
    db.flush()
    owner = (
        SubClient(
            id=uuid4(),
            parent_client_id=parent.id,
            sub_client_code='TP-CONTACT-S',
            client_name='笔译子客户',
            client_short_name='笔译子客户',
        )
        if is_sub
        else parent
    )
    if is_sub:
        db.add(owner)
        db.flush()

    created = crud.create_translation_project(
        db,
        TranslationProjectCreate(
            project_name='字幕翻译.docx',
            source_file_name='字幕翻译.docx',
            client_id=parent.id,
            sub_client_id=owner.id if is_sub else None,
            contact_name='xuanen',
            client_contact_version='new',
            client_contact_method='微信：xuanen',
            client_contact_description='新建项目时直接录入',
            created_by=actor.id,
        ),
        order_no=f"TP-261126-9{'1' if is_sub else '0'}1",
    )
    assert created.contact_name == 'xuanen'
    assert [row.contact_name for row in owner_rows(db, owner)] == ['xuanen']

    updated = crud.update_translation_project(
        db,
        created.id,
        TranslationProjectUpdate(
            contact_name='孙小温',
            client_contact_version='new',
            client_contact_method='电话：13800000000',
            client_contact_description='编辑项目时直接录入',
        ),
        actor_user_id=actor.id,
    )
    assert updated.contact_name == '孙小温'
    db.expire_all()
    owner = db.get(SubClient if is_sub else Client, owner.id)
    saved = {item['name']: item for item in contact_details(db, owner)}
    assert set(saved.keys()) == {'xuanen', '孙小温'}
    assert saved['xuanen']['contact_method'] == '微信：xuanen'
    assert saved['孙小温']['contact_method'] == '电话：13800000000'
    assert saved['孙小温']['description'] == '编辑项目时直接录入'
