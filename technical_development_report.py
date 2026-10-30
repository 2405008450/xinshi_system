"""技术任务追加到本人当日工作报告草稿；保留稳定来源与重试凭证。"""
from uuid import UUID, uuid4
from fastapi import HTTPException
import math
from pydantic import Field, field_validator, model_validator
from chat_time import now
from models import AppUser
from task_models import DailyReport, DailyReportItem
from work_report_dates import report_business_date
import technical_development as tasks


class ReportWrite(tasks.WriteModel):
    request_id: UUID
    report_type: str = Field(default='开发任务', min_length=1, max_length=80)
    order_no: str = Field(min_length=1, max_length=100)
    task_name: str = Field(min_length=1, max_length=255)
    progress_content: str = Field(min_length=1, max_length=10000)
    report_types: list[str] | None = Field(default=None, min_length=1, max_length=30)
    quantity: str | float
    quantity_unit: str = Field(min_length=1, max_length=80)
    quantity_unit_other: str = Field(default='', max_length=80)
    duration_minutes: int = Field(ge=1, le=1440, strict=True)

    @field_validator('quantity', mode='before')
    @classmethod
    def numeric_quantity(cls, value):
        if isinstance(value, bool):
            raise ValueError('请填写非负数字工作量')
        return value

    @field_validator('report_type', 'order_no', 'task_name', 'progress_content')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('请完整填写工作报告字段')
        if any(token in value.lower() for token in ('screenshot://', 'data:image/', '<img')):
            raise ValueError('工作报告字段仅允许文字')
        return value.strip()

    @model_validator(mode='after')
    def complete_fields(self):
        from work_report_categories import DEFAULT_CATEGORIES
        allowed = set(DEFAULT_CATEGORIES['项目工作']) | set(DEFAULT_CATEGORIES)
        self.report_types = list(dict.fromkeys(self.report_types or [self.report_type]))
        if any(value not in allowed for value in self.report_types):
            raise ValueError('请选择有效的任务/项目类型')
        self.report_type = self.report_types[0]
        try:
            quantity = float(self.quantity)
        except (ValueError, TypeError):
            raise ValueError('请填写非负数字工作量')
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError('请填写非负数字工作量')
        self.quantity_unit = self.quantity_unit.strip()
        self.quantity_unit_other = self.quantity_unit_other.strip()
        if not self.quantity_unit or self.quantity_unit == '其他' and not self.quantity_unit_other:
            raise ValueError('请填写单位')
        if any(token in (self.quantity_unit + self.quantity_unit_other).lower() for token in ('screenshot://', 'data:image/', '<img')):
            raise ValueError('单位仅允许文字')
        return self


def context(db, user, task_id):
    tasks.require_user(user, db)
    tasks.get_task(db, task_id)
    value = tasks.detail(db, user, task_id)
    from technical_task_allocations import require_individual
    require_individual(db,task_id)
    return dict(task_id=task_id, report_date=report_business_date(), report_type='开发任务', report_types=['开发任务'], order_no=value['task_no'], task_name=value['name'], progress_content=value['content'], quantity='', quantity_unit='', quantity_unit_other='', duration_minutes=None)


def submit(db, user, task_id, payload):
    tasks.require_user(user, db)
    tasks.require_ready(db)
    tasks.lock_tree(db)
    tasks.get_task(db, task_id)
    from technical_task_allocations import require_individual
    require_individual(db,task_id)
    # 与普通报告保存及其他任务追加共用用户行锁。
    db.query(AppUser.id).filter_by(id=user.id).with_for_update().first()
    receipt = db.get(tasks.DevelopmentReportReceipt, payload.request_id)
    if receipt:
        if receipt.user_id != user.id or receipt.task_id != task_id:
            raise HTTPException(409, '请求标识已被使用，请重新打开添加窗口')
        report = db.get(DailyReport, receipt.report_id)
        return dict(report_id=report.id, report_date=report.report_date, already_saved=True)
    instant = now()
    day = report_business_date(instant)
    report = db.query(DailyReport).filter_by(user_id=user.id, report_date=day).with_for_update().first()
    if report and report.status == 'finalized':
        raise HTTPException(409, '当天工作报告已确认，请先撤回后再添加')
    stamp = instant.replace(tzinfo=None)  # 既有日报字段按香港本地时间存储。
    if not report:
        report = DailyReport(id=uuid4(), user_id=user.id, report_date=day, status='draft', generated_at=stamp, created_at=stamp, updated_at=stamp)
        db.add(report); db.flush()
    from work_report_categories import DEFAULT_CATEGORIES
    allowed = set(DEFAULT_CATEGORIES['项目工作']) | set(DEFAULT_CATEGORIES)
    if payload.report_type not in allowed:
        raise HTTPException(422, '请选择有效的任务/项目类型')
    key = uuid4()
    metadata = dict(report_types=payload.report_types, order_no=payload.order_no, source='technical_development', technical_task_id=str(task_id), added_at=instant.isoformat(), _feedback_key=str(key), quantity=payload.quantity, quantity_unit=payload.quantity_unit, quantity_unit_other=payload.quantity_unit_other)
    entry = DailyReportItem(id=uuid4(), report_id=report.id, source_type='manual', source_id=task_id, task_type=payload.report_type, task_name=payload.task_name, progress_content=payload.progress_content, duration_minutes=payload.duration_minutes, display_metadata=metadata, sort_order=max((item.sort_order for item in report.items), default=-1)+1, created_at=stamp)
    report.items.append(entry)
    report.updated_at = stamp
    db.add(tasks.DevelopmentReportReceipt(request_id=payload.request_id, user_id=user.id, task_id=task_id, report_id=report.id, item_key=key, created_at=instant))
    db.commit()
    try:
        from consultation_work_report import publish_report_update
        publish_report_update(db, report)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('技术开发工作报告已保存，实时刷新通知失败')
    return dict(report_id=report.id, report_date=day, already_saved=False)
