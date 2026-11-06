"""客户对账单默认值：只作为未人工设置项目的读取规则，不批量覆盖项目。"""
from sqlalchemy import Column,DateTime,ForeignKey,String,Uuid,CheckConstraint
from models import Base,SubClient
from annotation_progress_time import business_now


class CustomerStatementDefault(Base):
    __tablename__='customer_statement_default'
    __table_args__=(CheckConstraint("choice IN ('required','not_required','unknown')",name='ck_customer_statement_default_choice'),)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    choice=Column(String(20),nullable=False,default='unknown')
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def choices_for_projects(db,projects):
    sub_ids={row.sub_client_id for row in projects if row.sub_client_id and not row.client_id}
    parents=dict(db.query(SubClient.id,SubClient.parent_client_id).filter(SubClient.id.in_(sub_ids)).all()) if sub_ids else {}
    owners={row.id:row.client_id or parents.get(row.sub_client_id) for row in projects}
    choices=dict(db.query(CustomerStatementDefault.client_id,CustomerStatementDefault.choice).filter(CustomerStatementDefault.client_id.in_({key for key in owners.values() if key})).all())
    return {key:choices.get(owner,'unknown') for key,owner in owners.items()}
