from uuid import uuid4
from tests.test_chat_participant_access import environment
from sqlalchemy import inspect
from models import Client,SubClient,ClientAddress,SubClientAddress
from geography_catalog import search
from tools.apply_client_address_migration import apply_migration

def test_global_and_china_search():
    assert search(q='',level='country',skip=0,limit=500)['total']==250
    rows=search(q='天河区',skip=0,limit=10)['items']
    assert rows[0]['province']=='广东省' and rows[0]['city']=='广州市'
    assert search(q='United States',skip=0,limit=10)['items']

def test_address_roundtrip_and_repeatable_migration(environment):
    db,_=environment
    for model in (SubClientAddress,ClientAddress):model.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    client=Client(id=uuid4(),client_code='ADDRESS',client_name='测试',client_short_name='测试',full_address='中国 广东省 广州市 天河区 测试路1号',detailed_address='测试路1号')
    sub=SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code='ADDRESS-SUB',client_name='子客户',client_short_name='子客户',full_address='完整地址',detailed_address='门牌号')
    db.add_all([client,sub]);db.commit();db.expire_all()
    assert db.get(Client,client.id).detailed_address=='测试路1号'
    assert db.get(SubClient,sub.id).full_address=='完整地址'
    client.full_address=None;db.commit();assert client.full_address
    client.full_address='';db.commit();assert client.full_address==''
