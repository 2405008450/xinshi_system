"""工作报告分类：项目分类共享，其余自定义分类按用户隔离。"""
from uuid import uuid4

from sqlalchemy import String, UniqueConstraint, Uuid, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from models import Base
from permission_registry import ALL_PERMISSION
from permission_service import get_user_permission_codes

DEFAULT_CATEGORIES = {
    '项目工作': ['笔译项目', '口译项目', '招聘项目', '标注项目', '配音项目', '字幕项目', '公证项目', '认证项目', '新咨询对接', '其他项目'],
    '非项目工作': ['接待客户', '研究工作', '开发工作', '技术支持', '行政工作', '人事工作'],
    '外勤工作': ['拜访客户', '口译现场', '投标', '陪标'],
    '管理工作': ['查看工作报告', '分析数据'],
}


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
    ready = inspect(db.connection()).has_table(WorkReportCategory.__tablename__)
    if ready:
        rows = db.query(WorkReportCategory).filter(WorkReportCategory.scope.in_(['*', str(user.id)])).order_by(WorkReportCategory.name).all()
        for row in rows:
            if row.parent in groups and row.name not in groups[row.parent]:
                groups[row.parent].append(row.name)
    return {'work_categories': groups, 'can_add_project_category': can_add_project_category(db, user), 'category_storage_ready': ready}


def add_category(db, user, parent, name):
    name = name.strip()
    if parent not in DEFAULT_CATEGORIES or not name or name=='__custom__' or len(name) > 80 or '::' in name or any(token in name.lower() for token in ['screenshot://', 'data:image/', '<img']):
        raise ValueError('请填写有效的二级分类名称（最多80字）')
    if parent == '项目工作' and not can_add_project_category(db, user):
        raise PermissionError('只有超级管理员可以新增项目工作分类')
    catalog = category_catalog(db, user)
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
