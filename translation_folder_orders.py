"""笔译目录订单：文件夹元数据单独存储，不修改现有订单表。"""
from uuid import UUID, uuid4
from pathlib import Path
import ntpath
from sqlalchemy import ForeignKey, String, JSON, DateTime, Integer, Boolean, inspect
from sqlalchemy.orm import Mapped, mapped_column
from models import Base, TranslationProject, TranslationSubOrder, AppUser
from annotation_progress_time import business_now, business_datetime
from pydantic import BaseModel, Field
from translation_file_name_rules import normalize_single_file_name

MAX_DEPTH=4
class TranslationOrderFolder(Base):
    __tablename__='translation_order_folder'
    sub_order_id:Mapped[UUID]=mapped_column(ForeignKey('translation_sub_order.id',ondelete='CASCADE'),primary_key=True)
    source_kind:Mapped[str]=mapped_column(String(10),nullable=False)
    root_path:Mapped[str]=mapped_column(String(2000),nullable=False)
    relative_path:Mapped[str]=mapped_column(String(2000),nullable=False)
    files:Mapped[list]=mapped_column(JSON,nullable=False,default=list)

class TranslationFolderImportLog(Base):
    __tablename__='translation_folder_import_log'
    id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    project_id:Mapped[UUID]=mapped_column(ForeignKey('translation_project.id',ondelete='CASCADE'),index=True)
    actor_id:Mapped[UUID|None]=mapped_column(ForeignKey('app_user.id',ondelete='SET NULL'))
    created_at:Mapped[object]=mapped_column(DateTime(timezone=True),default=business_now,nullable=False)
    source_kind:Mapped[str]=mapped_column(String(10),nullable=False)
    root_path:Mapped[str]=mapped_column(String(2000),nullable=False)
    empty_folders:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    empty_detection_complete:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0)


def attach_folder_roots(db,projects):
    if not projects or not inspect(db.connection()).has_table('translation_folder_import_log'):return
    ids={row[0] for row in db.query(TranslationFolderImportLog.project_id).filter(TranslationFolderImportLog.project_id.in_([project.id for project in projects])).distinct()}
    for project in projects:project.folder_root=project.id in ids


def is_folder_root(db,project_id):
    return inspect(db.connection()).has_table('translation_folder_import_log') and db.query(TranslationFolderImportLog.id).filter_by(project_id=project_id).first() is not None


def import_records(db,project_id,limit=100):
    if not inspect(db.connection()).has_table('translation_folder_import_log'):return []
    rows=db.query(TranslationFolderImportLog,AppUser.full_name,AppUser.username).outerjoin(AppUser,AppUser.id==TranslationFolderImportLog.actor_id).filter(TranslationFolderImportLog.project_id==project_id).order_by(TranslationFolderImportLog.created_at.desc(),TranslationFolderImportLog.id.desc()).limit(limit).all()
    return [{'id':str(row.id),'actor_name':name or username or '用户已移除','created_at':business_datetime(row.created_at).isoformat(),'root_path':row.root_path,'source_kind':row.source_kind,'empty_folders':row.empty_folders,'created_count':row.created_count,'empty_detection_complete':row.empty_detection_complete} for row,name,username in rows]


class FolderEntry(BaseModel):
    relative_path:str=Field(min_length=1,max_length=2000)
    files:list[str]=Field(default_factory=list,max_length=2000)
class FolderImport(BaseModel):
    empty_detection_complete:bool=True
    parent_project_id:UUID|None=None
    order_no:str|None=Field(default=None,max_length=50)
    source_kind:str=Field(pattern='^(local|unc)$')
    root_path:str=Field(min_length=1,max_length=2000)
    entries:list[FolderEntry]=Field(min_length=1,max_length=500)

def ready(db):return inspect(db.connection()).has_table('translation_order_folder')
def info(db,owner_id):
    if not ready(db):return None
    row=db.get(TranslationOrderFolder,owner_id)
    return {'source_kind':row.source_kind,'root_path':row.root_path,'relative_path':row.relative_path,'files':row.files} if row else None

def attach(db,rows):
    if not rows or not ready(db):return
    found={row.sub_order_id:row for row in db.query(TranslationOrderFolder).filter(TranslationOrderFolder.sub_order_id.in_([row.id for row in rows])).all()}
    for row in rows:
        folder=found.get(row.id)
        row.folder_info={'source_kind':folder.source_kind,'root_path':folder.root_path,'relative_path':folder.relative_path,'files':folder.files} if folder else None

def folder_name(value):
    value=str(value or '').strip()
    if not value or len(value)>255 or value in ('.','..') or any(c in value for c in '\\/:*?"<>|'):
        raise ValueError('文件夹名称不能为空，不能包含路径或特殊字符')
    return value

def normalized_entries(entries):
    result={}
    for entry in entries:
        parts=entry.relative_path.replace('\\','/').split('/')
        if len(parts)>MAX_DEPTH:raise ValueError('最多读取四级文件夹（含所选根文件夹），请整理目录后重试')
        parts=[folder_name(part) for part in parts]
        key='/'.join(parts)
        if key.casefold() in {item.casefold() for item in result}:raise ValueError('文件夹路径重复')
        result[key]=[normalize_single_file_name(name) for name in entry.files]
    if sum(len(files) for files in result.values())>2000:raise ValueError('单次最多读取2000个文件')
    roots={key.split('/')[0] for key in result}
    if len(roots)!=1:raise ValueError('一次只能导入一个根文件夹')
    for key in result:
        if '/' in key and key.rsplit('/',1)[0] not in result:raise ValueError('缺少上级文件夹')
    return result

def inspect_tree(root_path):
    from path_security import validate_managed_path
    from project_file_service import _is_reparse_point,_should_ignore_source_file
    import os
    normalized=validate_managed_path(root_path)
    if not normalized or not normalized.startswith('\\\\'):raise ValueError('请选择企业 UNC 共享文件夹路径')
    root=Path(normalized)
    if not root.is_dir():raise ValueError('共享文件夹不存在或当前服务无权访问')
    entries=[];file_count=0
    def walk(path,relative):
        nonlocal file_count
        if _is_reparse_point(path):raise ValueError('不能读取符号链接或目录联接')
        if len(relative.split('/'))>MAX_DEPTH:raise ValueError('目录超过四级（含根文件夹），请整理目录后重试')
        files=[];children=[]
        with os.scandir(path) as values:
            for item in values:
                if _should_ignore_source_file(item.name):continue
                if item.is_symlink():raise ValueError('不能读取符号链接')
                if item.is_dir(follow_symlinks=False):children.append(item.name)
                elif item.is_file(follow_symlinks=False):files.append(item.name);file_count+=1
        if file_count>2000:raise ValueError('单次最多读取2000个文件')
        entries.append({'relative_path':relative,'files':sorted(files,key=str.casefold)})
        if len(entries)>500:raise ValueError('单次最多读取500个文件夹')
        for name in sorted(children,key=str.casefold):walk(path/name,relative+'/'+name)
    try:walk(root,ntpath.basename(normalized.rstrip('\\')))
    except OSError as exc:raise ValueError('无法读取共享目录，请核对路径和访问权限') from exc
    return {'storage_path':normalized,'folder_entries':entries}

def import_folders(db,payload,actor,idempotency_key=None):
    from schemas import TranslationSubOrderCreate
    from crud import _create_sub_order_in_transaction
    from translation_direction_service import next_number
    if not ready(db) or not inspect(db.connection()).has_table('translation_folder_import_log'):raise ValueError('目录导入数据表尚未初始化')
    if not payload.parent_project_id and idempotency_key:
        old=db.query(TranslationProject).filter_by(idempotency_key=idempotency_key).first()
        if old:
            if old.created_by!=actor:raise ValueError('该请求不属于当前账号')
            return {'project_id':old.id,'order_no':old.order_no,'project_name':old.project_name,'network_file_path':old.network_file_path,'created_root':True,'created_count':0,'skipped_count':0,'created':[],'skipped':[]}
    entries=normalized_entries(payload.entries)
    if payload.source_kind=='unc':
        actual=normalized_entries([FolderEntry(**row) for row in inspect_tree(payload.root_path)['folder_entries']])
        if entries!=actual:raise ValueError('共享文件夹内容已变化，请重新读取')
    elif not (ntpath.isabs(payload.root_path) or payload.root_path.startswith('/')):
        raise ValueError('请填写所选本地根文件夹的完整路径，如 D:\\项目\\客户资料')
    root_relative=next(key for key in entries if '/' not in key)
    if ntpath.basename(payload.root_path.rstrip('\\/'))!=root_relative:raise ValueError('根路径末尾名称必须与所选根文件夹一致')
    created_root=not payload.parent_project_id
    if created_root:
        from crud import create_translation_project
        from schemas import TranslationProjectCreate
        root=create_translation_project(db,TranslationProjectCreate(project_name=root_relative,created_by=actor,client_manager_id=actor,project_status='pending_confirmation',network_file_path=payload.root_path),commit=False,order_no=payload.order_no,idempotency_key=idempotency_key,operation_source='folder_import',folder_root=True)
    else:
        root=db.query(TranslationProject).filter_by(id=payload.parent_project_id).with_for_update().first()
        if not root:raise ValueError('母订单不存在')
    existing=db.query(TranslationSubOrder).filter_by(parent_project_id=root.id).all()
    folders={row.relative_path:row for row in db.query(TranslationOrderFolder).filter(TranslationOrderFolder.sub_order_id.in_([row.id for row in existing]),TranslationOrderFolder.root_path==payload.root_path,TranslationOrderFolder.source_kind==payload.source_kind).all()}
    empty=[key for key in entries if not any(files for child,files in entries.items() if child==key or child.startswith(key+'/'))]
    owners={root_relative:root};created=[];skipped=[{'name':key,'reason':'空文件夹，已记录，不生成子订单'} for key in empty]
    for relative,files in sorted(entries.items(),key=lambda item:(item[0].count('/'),item[0])):
        if relative in empty:continue
        if relative!=root_relative:
            parent=owners[relative.rsplit('/',1)[0]]
            old=folders.get(relative)
            if old:
                old.files=files
                owners[relative]=db.get(TranslationSubOrder,old.sub_order_id)
                skipped.append({'name':relative,'reason':'已存在相同目录订单'})
            else:
                path=ntpath.join(payload.root_path,*relative.split('/')[1:])
                metadata={'source_kind':payload.source_kind,'root_path':payload.root_path,'relative_path':relative,'files':files}
                owner=_create_sub_order_in_transaction(db,TranslationSubOrderCreate(parent_project_id=root.id,sub_order_no=next_number(db,root,parent),sub_project_name=relative.split('/')[-1],folder_info=metadata,network_file_path=path,created_by=actor))
                owners[relative]=owner;created.append(owner)
        parent=owners[relative]
        parent_number=parent.sub_order_no if isinstance(parent,TranslationSubOrder) else root.order_no
        for name in files:
            path=ntpath.join(payload.root_path,*relative.split('/')[1:],name)
            if any(row.sub_order_no.rsplit('.',1)[0]==parent_number and row.sub_project_name.casefold()==name.casefold() for row in existing):
                skipped.append({'name':path,'reason':'该层已有同名文件订单'});continue
            owner=_create_sub_order_in_transaction(db,TranslationSubOrderCreate(parent_project_id=root.id,sub_order_no=next_number(db,root,parent),sub_project_name=name,network_file_path=path,created_by=actor))
            created.append(owner);existing.append(owner)
    if any(entries.values()):root.project_name=root_relative;root.source_file_name=root_relative;root.network_file_path=payload.root_path
    db.add(TranslationFolderImportLog(project_id=root.id,actor_id=actor,source_kind=payload.source_kind,root_path=payload.root_path,empty_folders=empty,created_count=len(created),empty_detection_complete=payload.source_kind=='unc' or payload.empty_detection_complete))
    from annotation_progress_time import business_now
    if any(entries.values()):root.updated_at=business_now()
    db.commit()
    return {'project_id':root.id,'order_no':root.order_no,'project_name':root.project_name,'network_file_path':root.network_file_path,'created_root':created_root,'created_count':len(created),'skipped_count':len(skipped),'created':created,'skipped':skipped}
