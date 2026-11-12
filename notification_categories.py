"""分类由已存通知推导，列表和计数共用同一规则。"""
from typing import Literal

from sqlalchemy import case, func, or_

from resource_summary_service import CATEGORY_LABELS

NotificationCategory = Literal[
    'translation', 'interpretation', 'annotation', 'recruitment',
    'conversation_saved', 'resource_request', 'invoice', 'administration', 'other',
]
SummaryCategory = Literal['arrangement', 'request', 'idea', 'decision', 'execution', 'problem', 'risk', 'standard', 'other']
PROJECT_CATEGORIES = ('translation', 'interpretation', 'annotation', 'recruitment')


def normalized(column):
    return func.lower(func.trim(func.coalesce(column, '')))


def category_expression(model):
    kind = normalized(model.notification_type)
    project = normalized(model.related_project_type)
    return case(
        (or_(kind == 'invoice', kind.startswith('invoice_', autoescape=True), project == 'invoice_request'), 'invoice'),
        (or_(*(kind.startswith(prefix, autoescape=True) for prefix in (
            'attendance_', 'leave_', 'comp_time_', 'home_office_', 'administration_',
        ))), 'administration'),
        (kind == 'chat_summary', 'conversation_saved'),
        (kind == 'resource_request_dispatch', 'resource_request'),
        *((or_(project == name, kind.startswith(f'{name}_', autoescape=True)), name) for name in PROJECT_CATEGORIES),
        # This legacy foreign key references only translation projects.
        (model.related_project_id.is_not(None), 'translation'),
        else_='other',
    )


def summary_category_expression(model):
    # The saved title carries the category at the time the notification was sent.
    # Keep it searchable even if the source record is renamed or deleted later.
    return case(
        (normalized(model.notification_type) == 'chat_summary', case(
            *((func.trim(model.title) == f'总结同步 · {label}', key) for key, label in CATEGORY_LABELS.items()),
            else_='other',
        )),
        else_=None,
    )
