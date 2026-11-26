"""保存客户档案首次登记入口，后续关联项目不改变该来源。"""
from sqlalchemy import Column, ForeignKey, String, Uuid, inspect
from models import Base

LABELS = {'clients': '客户管理', 'consultation': '新咨询', 'translation': '笔译项目',
          'interpretation': '口译项目', 'annotation': '标注项目', 'recruitment': '招聘项目'}


class ClientRegistrationSource(Base):
    __tablename__ = 'client_registration_source'
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), primary_key=True)
    module = Column(String(30), nullable=False)


def record(db, client_id, module):
    if module not in LABELS:
        raise ValueError('客户登记来源无效')
    if not inspect(db.connection()).has_table(ClientRegistrationSource.__tablename__):
        raise ValueError('客户登记来源表尚未初始化')
    db.add(ClientRegistrationSource(client_id=client_id, module=module))


def attach(db, clients):
    values = {}
    if clients and inspect(db.connection()).has_table(ClientRegistrationSource.__tablename__):
        values = dict(db.query(ClientRegistrationSource.client_id, ClientRegistrationSource.module).filter(
            ClientRegistrationSource.client_id.in_([client.id for client in clients])).all())
    for client in clients:
        client.registration_source = LABELS.get(values.get(client.id), '历史数据（未记录）')
