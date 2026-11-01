"""安排任务与下级订单的附属关联；保留旧母订单任务，不改既有表。"""
import re
from fastapi import HTTPException
from sqlalchemy import Column, ForeignKey, Integer, String, Uuid, inspect

from models import Base, TranslationProject, TranslationSubOrder


class ArrangementOrderTarget(Base):
    __tablename__ = 'translation_arrangement_order_target'
    arrangement_id = Column(Uuid, ForeignKey('translation_project_arrangement.id', ondelete='CASCADE'), primary_key=True)
    sub_order_id = Column(Uuid, nullable=False, index=True)
    order_no = Column(String(60), nullable=False)
    project_name = Column(String(255), nullable=False)
    order_level = Column(Integer, nullable=False)
    previous_order_status = Column(String(50), nullable=True)


def ready(db):
    key = 'translation_arrangement_order_target_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(ArrangementOrderTarget.__tablename__)
    return db.info[key]


def order_level(parent, child):
    suffix = (child.sub_order_no or '')[len(parent.order_no):] if (child.sub_order_no or '').startswith(parent.order_no) else ''
    return 1 + suffix.count('.') if re.fullmatch(r'(?:\.\d+)+', suffix) else 2


def catalog(db, project_id):
    parent = db.get(TranslationProject, project_id)
    if not parent or parent.annotation_migrated_at:
        raise HTTPException(404, '笔译项目不存在')
    children = db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.sub_order_no).all()
    root = dict(id=str(parent.id), order_no=parent.order_no, project_name=parent.source_file_name or parent.project_name or '-',
                level=1, status=parent.project_status, children=[])
    nodes = {parent.order_no: root}
    for child in children:
        nodes[child.sub_order_no] = dict(id=str(child.id), order_no=child.sub_order_no,
            project_name=child.sub_project_name or '-', level=order_level(parent, child), status=child.status, children=[])
    for child in children:
        node = nodes[child.sub_order_no]
        ancestor = nodes.get(child.sub_order_no.rsplit('.', 1)[0], root) if node['level'] > 2 else root
        ancestor['children'].append(node)
    return {'items': [root], 'ready': ready(db)}


def resolve(db, parent, target_ids, item_count):
    ids = [parent.id] if target_ids is None else target_ids
    if not ids or len(set(ids)) != len(ids):
        raise HTTPException(422, '请选择订单，且订单不能重复')
    if len(ids) * item_count > 100:
        raise HTTPException(422, '单次最多安排100项任务，请减少订单或人员数量')
    children = {row.id: row for row in db.query(TranslationSubOrder).filter(
        TranslationSubOrder.parent_project_id == parent.id, TranslationSubOrder.id.in_(ids)).order_by(
        TranslationSubOrder.id).with_for_update().all()}
    if set(ids) - {parent.id} - children.keys():
        raise HTTPException(422, '所选下级订单不属于该母订单，或已被删除，请刷新后重选')
    if children and not ready(db):
        raise HTTPException(503, '下级订单安排存储尚未初始化')
    return [None if uid == parent.id else children[uid] for uid in ids]


def attach(db, task, parent, child, previous_status):
    if child is not None:
        db.add(ArrangementOrderTarget(arrangement_id=task.id, sub_order_id=child.id, order_no=child.sub_order_no,
            project_name=child.sub_project_name or '-', order_level=order_level(parent, child), previous_order_status=previous_status))


def identity(db, task, parent=None):
    parent = parent or db.get(TranslationProject, task.project_id)
    result = dict(order_no=parent.order_no if parent else '-', project_name=(parent.source_file_name or parent.project_name or '-') if parent else '-',
                  sub_order_id=None, order_level=1, root_order_no=parent.order_no if parent else '-', target_deleted=False)
    target = db.get(ArrangementOrderTarget, task.id) if ready(db) else None
    if target:
        child = db.get(TranslationSubOrder, target.sub_order_id)
        result.update(order_no=child.sub_order_no if child else target.order_no,
            project_name=(child.sub_project_name or '-') if child else target.project_name,
            sub_order_id=str(target.sub_order_id), order_level=target.order_level, target_deleted=child is None,
            previous_order_status=target.previous_order_status)
    return result
