"""首次手工补充子订单时，将原单文件母订单保留为第一个子订单。"""
from uuid import UUID
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Uuid, inspect
from sqlalchemy.orm import Mapped, mapped_column
from fastapi.encoders import jsonable_encoder
from models import Base, TranslationProject, TranslationSubOrder, ProjectFile
from annotation_progress_time import business_now, business_datetime


class TranslationMotherSplit(Base):
    __tablename__='translation_mother_split'
    project_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),primary_key=True)
    first_sub_order_id:Mapped[UUID|None]=mapped_column(Uuid,ForeignKey('translation_sub_order.id',ondelete='SET NULL'),unique=True)
    original_information:Mapped[dict]=mapped_column(JSON,nullable=False)
    needs_review:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    actor_id:Mapped[UUID|None]=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)
    reviewed_by=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    reviewed_at=mapped_column(DateTime(timezone=True))


def ready(db):
    return inspect(db.connection()).has_table(TranslationMotherSplit.__tablename__)


def attach(db,projects=(),children=()):
    owners={row.id for row in projects}|{row.parent_project_id for row in children}
    if not owners or not ready(db):return
    records={row.project_id:row for row in db.query(TranslationMotherSplit).filter(TranslationMotherSplit.project_id.in_(owners))}
    for owner in [*projects,*children]:
        record=records.get(owner.id if isinstance(owner,TranslationProject) else owner.parent_project_id)
        owner.mother_split_review=None if not record else {
            'required':record.needs_review,'first_sub_order_id':str(record.first_sub_order_id) if record.first_sub_order_id else None,
            'original_name':record.original_information.get('source_file_name') or record.original_information.get('project_name'),
            'created_at':business_datetime(record.created_at).isoformat(),
        }
        if record and isinstance(owner,TranslationSubOrder) and owner.id==record.first_sub_order_id:
            owner.original_project_information=record.original_information


def preserve_original(db,root,actor):
    """调用方持有母订单行锁。没有有效后缀、已有子订单、已转换时均不再复制。"""
    from translation_file_name_rules import normalize_single_file_name
    from schemas import TranslationSubOrderCreate, TranslationSubOrderChargeItemInput
    from crud import _create_sub_order_in_transaction, get_translation_project
    from word_count_service import hierarchy_matrix
    from translation_order_inheritance import TranslationOrderInheritance, FIELDS, values
    name=root.source_file_name or root.project_name
    try:name=normalize_single_file_name(name)
    except ValueError:return None
    if db.query(TranslationSubOrder.id).filter_by(parent_project_id=root.id).first():return None
    if not ready(db):raise ValueError('母订单转子订单记录表尚未初始化')
    if db.get(TranslationMotherSplit,root.id):return None
    root=get_translation_project(db,root.id)
    hierarchy_matrix(db,'project',root)
    excluded={'id','order_no','client_id','sub_client_id','customer_order_no','customer_reception_time','consultation_id','created_at','updated_at','created_by','idempotency_key'}
    encode=lambda value:jsonable_encoder(value,custom_encoder={datetime:lambda moment:business_datetime(moment).isoformat()})
    snapshot=encode({col.key:getattr(root,col.key,None) for col in root.__table__.columns if col.key not in excluded})
    snapshot['word_count_matrix']=jsonable_encoder(root.word_count_matrix)
    for key in ('role_assignments','project_manager_name','project_specialist_name','project_assistant_name','layout_specialist_name','assigned_translators','translator_name'):
        if hasattr(root,key):snapshot[key]=encode(getattr(root,key))
    snapshot['project_files']=[jsonable_encoder({col.key:getattr(row,col.key,None) for col in row.__table__.columns if col.key not in {'id','translation_project_id','uploaded_by','created_at'}}) for row in db.query(ProjectFile).filter_by(translation_project_id=root.id)]
    snapshot['customer_charge_items']=[jsonable_encoder(TranslationSubOrderChargeItemInput.model_validate(row,from_attributes=True).model_dump(exclude={'id'})) for row in root.customer_charge_items]
    data={key:getattr(root,key,None) for key in TranslationSubOrderCreate.model_fields if hasattr(root,key) and key not in {'sub_order_no','parent_project_id','parent_sub_order_id','folder_info','created_by','customer_charge_items'}}
    data.update(parent_project_id=root.id,sub_order_no=root.order_no+'.001',sub_project_name=name,status=root.project_status,created_by=actor,word_count_matrix=root.word_count_matrix,customer_charge_items=snapshot['customer_charge_items'])
    child=_create_sub_order_in_transaction(db,TranslationSubOrderCreate(**data))
    # 原文件信息固定保存，后续修改母订单不会覆盖这一份原始内容。
    state=db.get(TranslationOrderInheritance,child.id)
    if state:state.overrides={**(state.overrides or {}),**values(root)}
    stem=name.rpartition('.')[0]
    root.source_file_name=stem;root.project_name=stem
    db.add(TranslationMotherSplit(project_id=root.id,first_sub_order_id=child.id,original_information=snapshot,actor_id=actor))
    db.flush()
    return child


def review(db,root,actor):
    if not ready(db):return
    record=db.get(TranslationMotherSplit,root.id)
    if record and record.needs_review:
        record.needs_review=False;record.reviewed_by=actor;record.reviewed_at=business_now()
