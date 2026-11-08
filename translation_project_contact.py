"""笔译项目客户联系人，独立于客户档案中的旧联系方式。"""
from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid, inspect
from models import Base
from annotation_progress_time import business_now


class TranslationProjectContact(Base):
    __tablename__ = 'translation_project_contact'
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), primary_key=True)
    contact_name = Column(String(255), nullable=False)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now, onupdate=business_now)


def ready(db):
    key = 'translation_project_contact_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(TranslationProjectContact.__tablename__)
    return db.info[key]


def attach(db, projects):
    if not projects:
        return
    records = {row.project_id: row for row in db.query(TranslationProjectContact).filter(
        TranslationProjectContact.project_id.in_([project.id for project in projects])).all()} if ready(db) else {}
    for project in projects:
        client = project.sub_client or project.client
        personal_name = (client.client_short_name or '') if client and getattr(project, 'customer_type', None) == '个人客户' else ''
        project.contact_name = records[project.id].contact_name if project.id in records else personal_name


def save(db, project, contact_name, actor_id=None):
    name = str(contact_name or '').strip()
    if not name or len(name) > 255:
        raise ValueError('请填写客户联系人，且不能超过255个字符')
    if not ready(db):
        raise ValueError('客户联系人数据表尚未初始化')
    row = db.get(TranslationProjectContact, project.id)
    changed = row is None or row.contact_name != name
    client = project.sub_client or project.client
    if client:
        from client_contact_people import ensure
        ensure(db, client, name, reactivate=changed)
    if not row:
        row = TranslationProjectContact(project_id=project.id)
        db.add(row)
    row.contact_name = name
    row.updated_by = actor_id
    row.updated_at = business_now()
    project.contact_name = name
