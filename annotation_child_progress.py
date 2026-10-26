"""子订单未在当前订单登记的进度提示；只读汇总，不复制业务记录。"""
from sqlalchemy import select, union_all, literal, func, exists, inspect, String, cast
from sqlalchemy.orm import aliased
from annotation_models import AnnotationProject as Project
from annotation_ops_models import AnnotationProjectStatusHistory
from annotation_customer_progress_models import AnnotationCustomerProgress
from annotation_annotator_progress_models import AnnotationAnnotatorProgress
from models import AppUser


def pending_query(db, parent_ids):
    child, grandchild = aliased(Project), aliased(Project)
    family = union_all(
        select(Project.id.label('parent_id'), child.id.label('child_id')).join(child, child.parent_project_id == Project.id).where(Project.id.in_(parent_ids)),
        select(Project.id.label('parent_id'), grandchild.id.label('child_id')).join(child, child.parent_project_id == Project.id).join(grandchild, grandchild.parent_project_id == child.id).where(Project.id.in_(parent_ids)),
    ).cte('progress_family')
    ids = select(family.c.child_id).union(select(Project.id).where(Project.id.in_(parent_ids)))
    sources=[]
    inspector=inspect(db.connection())
    for track, model in [('project',AnnotationProjectStatusHistory),('customer',AnnotationCustomerProgress),('annotator',AnnotationAnnotatorProgress)]:
        if not inspector.has_table(model.__tablename__):continue
        # 老项目进度为香港本地无时区时间，新两类为带时区实际时刻；先统一展示/排序语义。
        def business_text(column):
            value=func.timezone('Asia/Hong_Kong',column) if track!='project' and db.bind.dialect.name=='postgresql' else column
            return cast(value,String)
        sources.append(select(model.id.label('id'),model.project_id.label('project_id'),literal(track).label('track'),
            model.change_note.label('note'),business_text(model.effective_on).label('effective_on'),
            business_text(model.changed_at).label('changed_at'),business_text(model.updated_at).label('updated_at'),model.changed_by.label('changed_by'))
            .where(model.project_id.in_(ids),func.length(func.trim(model.change_note))>0))
    notes=union_all(*sources).cte('family_notes')
    own=notes.alias('own_notes')
    reflected=exists(select(own.c.id).where(own.c.project_id==family.c.parent_id,own.c.track==notes.c.track,
        func.trim(own.c.note)==func.trim(notes.c.note)))
    return db.query(family.c.parent_id,notes.c.id,notes.c.project_id,notes.c.track,notes.c.note,
        notes.c.effective_on,notes.c.changed_at,notes.c.updated_at,notes.c.changed_by).join(notes,notes.c.project_id==family.c.child_id).filter(~reflected)


def read_key(row):
    return f'{row.track}:{row.id}:{row.updated_at or row.changed_at}'


def attach_counts(db, projects):
    for row in projects:row.child_progress_count=0;row.child_progress_keys=[]
    parents=[row.id for row in projects if getattr(row,'child_count',0)]
    if not parents:return
    pending=pending_query(db,parents).subquery()
    keys={}
    for row in db.query(pending.c.parent_id,pending.c.track,pending.c.id,pending.c.updated_at,pending.c.changed_at):
        keys.setdefault(row.parent_id,[]).append(read_key(row))
    for row in projects:
        row.child_progress_keys=keys.get(row.id,[])
        row.child_progress_count=len(row.child_progress_keys)


def listing(db, project_id, skip=0, limit=20):
    query=pending_query(db,[project_id])
    total=query.count()
    pending=query.subquery()
    rows=db.query(pending,Project.order_no,Project.project_name,AppUser.full_name,AppUser.username).join(Project,Project.id==pending.c.project_id).outerjoin(AppUser,AppUser.id==pending.c.changed_by).order_by(pending.c.changed_at.desc(),pending.c.id.desc()).offset(skip).limit(limit).all()
    keys=[read_key(row) for row in db.query(pending.c.track,pending.c.id,pending.c.updated_at,pending.c.changed_at)]
    return {'total':total,'record_keys':keys,'items':[dict(id=row.id,read_key=read_key(row),project_id=row.project_id,order_no=row.order_no,project_name=row.project_name,
        track=row.track,change_note=row.note,effective_on=row.effective_on,changed_at=row.changed_at,
        changed_by_name=row.full_name or row.username or '系统') for row in rows]}
