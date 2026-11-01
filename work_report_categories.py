"""工作报告分类：项目分类共享，其余自定义分类按用户隔离。"""
from uuid import uuid4

from sqlalchemy import String, UniqueConstraint, Uuid, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from models import Base
from permission_registry import ALL_PERMISSION
from permission_service import get_user_permission_codes

DEFAULT_CATEGORIES = {
    '项目工作': ['笔译项目', '口译项目', '招聘项目', '标注项目', '配音项目', '字幕项目', '公证项目', '认证项目', '新咨询对接', '开发任务', '其他项目'],
    '非项目工作': ['接待客户', '研究工作', '开发工作', '技术支持', '行政工作', '人事工作', '词汇整理'],
    '外勤工作': ['拜访客户', '口译现场', '投标', '陪标'],
    '管理工作': ['查看工作报告', '分析数据', '开发工作'],
    '培训工作': ['AI知识培训', '客户部培训', '标注项目培训', '笔译项目培训', '口译项目培训', '招聘项目培训', '资源开拓培训', 'HR工作培训', '排版培训', '专检培训'],
}


LAYOUT_TASK_PRESETS = ['专检', '排版', '稽查']
ROOT_CATEGORY_PARENT = '__work_groups__'
LAYOUT_PRESET_PARENT = '__layout_tasks__'


def valid_category_name(value, limit=80):
    return isinstance(value,str) and bool(value.strip()) and len(value)<=limit and not value.startswith('__') and '::' not in value and not any(token in value.lower() for token in ['screenshot://','data:image/','<img'])


def valid_category_value(value):
    if not isinstance(value,str):return False
    if value in DEFAULT_CATEGORIES or value in DEFAULT_CATEGORIES['项目工作']:return True
    parent,separator,name=value.partition('::')
    return bool(separator and valid_category_name(parent,20) and valid_category_name(name))


class WorkReportCategory(Base):
    __tablename__ = 'work_report_category'
    __table_args__ = (UniqueConstraint('scope', 'parent', 'name', name='uq_work_report_category'),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(36), nullable=False)
    parent: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


def can_add_project_category(db, user):
    return ALL_PERMISSION in get_user_permission_codes(db, user.id)


def category_catalog(db, user):
    groups = {parent: list(names) for parent, names in DEFAULT_CATEGORIES.items()}
    presets=list(LAYOUT_TASK_PRESETS)
    ready = inspect(db.connection()).has_table(WorkReportCategory.__tablename__)
    if ready:
        rows = db.query(WorkReportCategory).filter(WorkReportCategory.scope.in_(['*', str(user.id)])).order_by(WorkReportCategory.name).all()
        for row in rows:
            if row.parent==ROOT_CATEGORY_PARENT and row.scope==str(user.id):groups.setdefault(row.name,[])
        for row in rows:
            if row.parent in groups and row.name not in groups[row.parent]:
                groups[row.parent].append(row.name)
            if row.parent==LAYOUT_PRESET_PARENT and row.name not in presets:presets.append(row.name)
    return {'work_categories': groups, 'layout_task_presets':presets, 'can_add_project_category': can_add_project_category(db, user), 'category_storage_ready': ready}


def add_category(db, user, parent, name):
    name = name.strip()
    catalog = category_catalog(db, user)
    if parent not in catalog['work_categories'] or not valid_category_name(name):
        raise ValueError('请填写有效的二级分类名称（最多80字）')
    if parent == '项目工作' and not can_add_project_category(db, user):
        raise PermissionError('只有超级管理员可以新增项目工作分类')
    if name in catalog['work_categories'][parent]:
        return catalog
    if not catalog['category_storage_ready']:
        raise ValueError('工作分类存储尚未初始化，请联系管理员执行分类迁移')
    db.add(WorkReportCategory(scope='*' if parent == '项目工作' else str(user.id), parent=parent, name=name))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if name not in category_catalog(db, user)['work_categories'][parent]:
            raise
    return category_catalog(db, user)


def add_category_group(db,user,name,content):
    name,content=name.strip(),content.strip()
    if not valid_category_name(name,20) or not valid_category_name(content):raise ValueError('请填写分类名称（最多20字）和具体内容（最多80字）')
    catalog=category_catalog(db,user)
    if name in DEFAULT_CATEGORIES:raise ValueError('该分类已存在，请在原分类下添加内容')
    if not catalog['category_storage_ready']:raise ValueError('工作分类存储尚未初始化')
    existing=db.query(WorkReportCategory).filter_by(scope=str(user.id)).all()
    keys={(row.parent,row.name) for row in existing}
    for parent,value in [(ROOT_CATEGORY_PARENT,name),(name,content)]:
        if (parent,value) not in keys:db.add(WorkReportCategory(scope=str(user.id),parent=parent,name=value))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        if content not in category_catalog(db,user)['work_categories'].get(name,[]):raise
    return category_catalog(db,user)


def add_layout_task_preset(db,user,name):
    from organization_service import department_condition
    from models import AppUser
    if not db.query(AppUser.id).filter(AppUser.id==user.id,department_condition(db,['排版部'])).first():raise PermissionError('仅排版部人员可以添加排版固定任务')
    name=name.strip()
    if not valid_category_name(name):raise ValueError('请填写有效的固定任务（最多80字）')
    catalog=category_catalog(db,user)
    if name in catalog['layout_task_presets']:return catalog
    if not catalog['category_storage_ready']:raise ValueError('固定任务存储尚未初始化')
    db.add(WorkReportCategory(scope=str(user.id),parent=LAYOUT_PRESET_PARENT,name=name))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        if name not in category_catalog(db,user)['layout_task_presets']:raise
    return category_catalog(db,user)


def validate_categories(db, user, items):
    catalog = category_catalog(db, user)['work_categories']
    for item in items or []:
        if item.source_type == 'system_event':
            continue
        for value in (item.display_metadata or {}).get('report_types', []):
            if '::' in value:
                parent, name = value.split('::', 1)
                if name not in catalog.get(parent, []):
                    raise ValueError('工作分类不存在或无权使用，请重新选择')
        custom = (item.display_metadata or {}).get('custom_project_type')
        if custom and not can_add_project_category(db, user):
            # 历史自定义项目可原样保留，普通用户不能借旧字段新增分类。
            from task_models import DailyReport, DailyReportItem
            metadata_rows = db.query(DailyReportItem.display_metadata).join(DailyReport).filter(DailyReport.user_id == user.id).all()
            if not any((metadata or {}).get('custom_project_type') == custom for metadata, in metadata_rows):
                raise PermissionError('只有超级管理员可以新增项目工作分类')
