"""从当前 PostgreSQL 数据库生成数据库设计文档、字段字典和 draw.io ER 图。

运行方式（项目根目录）：
    python tools/generate_database_docs.py

说明：
- 只读取数据库结构，不读取业务数据。
- 连接参数沿用项目 database.py 和 .env。
- 输出不会包含数据库口令或完整连接串。
"""

from __future__ import annotations

import html
import importlib
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import UniqueConstraint, inspect, text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for module_name in (
    "models", "interpretation_models", "recruitment_models", "resource_models",
    "annotation_models", "annotation_ops_models", "resource_request_models",
    "workflow_models", "task_models", "manuscript_models", "business_mail_models",
    "word_count_models",
):
    importlib.import_module(module_name)

from database import engine  # noqa: E402
from models import Base  # noqa: E402


OUTPUT_DIR = ROOT / "docs" / "database"

TABLE_PURPOSES = {
    "app_user": "系统登录用户、人员基础信息及固定任务配置",
    "role": "角色定义",
    "user_role": "用户与角色的多对多关联",
    "role_permission": "角色拥有的细粒度权限",
    "client": "母客户/主客户档案",
    "sub_client": "母客户下属的子客户档案",
    "client_contact": "客户拜访与跟进记录",
    "consultation": "售前咨询、来源及跟进过程",
    "translator": "译员资源、能力、联系方式及可用性档案",
    "translator_schedule": "译员按日的可用时段和剩余产能",
    "translation_project": "翻译主订单及各生产阶段进度",
    "translation_sub_order": "主订单拆分后的子订单",
    "project_file": "项目文件及各生产环节路径",
    "workflow_instance": "主订单或子订单当前工作流状态",
    "workflow_log": "工作流阶段流转审计日志",
    "workflow_handover_request": "请假/离职等场景的工作交接申请",
    "workflow_handover_item": "交接申请所包含的工作流实例",
    "workflow_handover_attachment": "交接申请与聊天附件的关联",
    "chat_project_enabled": "项目群聊启用状态",
    "chat_project_message": "项目群聊消息",
    "chat_project_mention": "群聊消息中的用户提及",
    "chat_project_attachment": "项目群聊上传的附件实体",
    "chat_project_message_attachment": "群聊消息与附件的多对多关联",
    "app_notification": "站内通知及已读状态",
    "finance_record": "项目维度的报价、结算和开票信息",
    "finance_payment": "财务记录的定金/中期款/尾款明细",
    "non_project_task_recurrence": "非项目周期任务模板",
    "non_project_task": "一次性的或周期生成的非项目任务",
    "non_project_task_event": "非项目任务状态变更事件",
    "work_entry": "用户每日项目/非项目工作投入记录",
    "daily_report": "用户日清日报头及定稿状态",
    "daily_report_item": "日报中的工作条目快照",
    "work_schedule": "部门每日排班快照及紧急任务表",
    "employee_leave": "员工请假区间记录",
    "manuscript_dispatch": "一次主订单/子订单稿件派发批次",
    "manuscript_arrangement": "派发批次内针对译员的稿件安排与邮件结果",
    "manuscript_delivery_milestone": "稿件安排的阶段性/最终交付节点",
    "annotation_project_status_history": "标注项目状态实际生效日期与变更履历",
    "annotation_platform": "客户级标注平台资产",
    "annotation_platform_account": "标注平台账号资产（凭据明文存储）",
    "annotation_account_assignment": "账号与标注员、项目的分配履历",
    "annotation_account_assignment_language": "账号分配所覆盖的项目语种",
    "annotation_account_password_history": "账号历史密码明文与修改履历",
    "annotation_credential_access_log": "账号明文凭据查看审计",
    "annotation_trial_record": "标注员分轮次试标过程与结果",
    "annotation_assignee_rate": "正式标注或质检安排的人员计价",
    "annotation_custom_field_definition": "标注域动态业务字段定义",
    "resource_request": "跨业务来源的资源需求主记录与快照",
    "resource_request_item": "资源需求的语种、人数与要求明细",
    "resource_request_progress_log": "资源开拓进度变化履历",
}

MODULES = {
    "身份与权限": ["app_user", "role", "user_role", "role_permission"],
    "客户与咨询": ["client", "sub_client", "client_contact", "consultation"],
    "译员资源": ["translator", "translator_schedule"],
    "项目与文件": ["translation_project", "translation_sub_order", "project_file"],
    "工作流与交接": [
        "workflow_instance",
        "workflow_log",
        "workflow_handover_request",
        "workflow_handover_item",
        "workflow_handover_attachment",
    ],
    "协作与通知": [
        "chat_project_enabled",
        "chat_project_message",
        "chat_project_mention",
        "chat_project_attachment",
        "chat_project_message_attachment",
        "app_notification",
    ],
    "财务": ["finance_record", "finance_payment"],
    "任务与日报": [
        "non_project_task_recurrence",
        "non_project_task",
        "non_project_task_event",
        "work_entry",
        "daily_report",
        "daily_report_item",
    ],
    "排班与请假": ["work_schedule", "employee_leave"],
    "稿件安排": [
        "manuscript_dispatch",
        "manuscript_arrangement",
        "manuscript_delivery_milestone",
    ],
    "标注运营": [
        "annotation_project", "annotation_project_language_item", "annotation_project_price_item",
        "annotation_project_assignee", "annotation_project_status_history", "annotation_platform",
        "annotation_platform_account", "annotation_account_assignment", "annotation_account_assignment_language",
        "annotation_account_password_history", "annotation_credential_access_log",
        "annotation_trial_record", "annotation_assignee_rate", "annotation_custom_field_definition",
    ],
    "资源需求": ["resource_request", "resource_request_item", "resource_request_progress_log"],
}

MODULE_COLORS = {
    "身份与权限": ("#dae8fc", "#6c8ebf"),
    "客户与咨询": ("#d5e8d4", "#82b366"),
    "译员资源": ("#fff2cc", "#d6b656"),
    "项目与文件": ("#f8cecc", "#b85450"),
    "工作流与交接": ("#e1d5e7", "#9673a6"),
    "协作与通知": ("#d0e0e3", "#3d85c6"),
    "财务": ("#ffe6cc", "#d79b00"),
    "任务与日报": ("#cce5ff", "#4a86e8"),
    "排班与请假": ("#fce5cd", "#e69138"),
    "稿件安排": ("#ead1dc", "#a64d79"),
    "标注运营": ("#d5e8d4", "#2d7d46"),
    "资源需求": ("#fff2cc", "#b8860b"),
}

FIELD_DESCRIPTIONS = {
    "id": "UUID 主键",
    "username": "登录用户名",
    "password_hash": "密码哈希；不是明文密码",
    "full_name": "用户姓名",
    "email": "电子邮箱",
    "is_active": "账号是否启用",
    "created_at": "创建时间",
    "updated_at": "最后更新时间",
    "created_by": "创建用户",
    "department": "所属部门",
    "fixed_tasks": "用户固定任务配置",
    "role_name": "角色名称",
    "permission_code": "权限编码",
    "user_id": "关联用户",
    "role_id": "关联角色",
    "client_id": "关联客户",
    "origin_project_id": "首次登记来源标注项目",
    "platform_url_normalized": "用于客户内查重的平台规范化链接",
    "login_notes": "登录、验证码和二次验证说明",
    "parent_account_id": "备用账号所关联的主账号",
    "birth_date": "出生日期，用于动态计算年龄",
    "native_place": "籍贯",
    "residence_address": "现居地址",
    "dialects": "掌握的方言",
    "dialect_regions": "方言对应地域",
    "login_account": "登录账号明文",
    "login_account_normalized": "用于平台内查重的规范化登录账号",
    "password": "登录密码明文",
    "account_status": "账号状态",
    "registration_status": "平台注册状态",
    "account_source": "账号来源",
    "expires_on": "账号到期日期",
    "account_id": "关联标注账号资产",
    "assigned_on": "分配开始日期",
    "released_on": "释放日期；空表示当前使用中",
    "release_reason": "释放原因",
    "assignment_note": "账号分配说明",
    "assigned_by": "执行分配的系统用户",
    "effective_from": "历史密码原生效时间",
    "replaced_at": "密码被替换时间",
    "changed_by": "执行变更的系统用户",
    "accessed_at": "明文凭据查看时间",
    "access_reason": "明文凭据查看原因",
    "client_ip": "查看者客户端 IP",
    "parent_client_id": "所属母客户",
    "translator_id": "关联译员",
    "translation_project_id": "关联翻译主订单",
    "parent_project_id": "所属翻译主订单",
    "sub_order_id": "关联翻译子订单",
    "project_id": "关联翻译主订单",
    "finance_id": "关联财务记录",
    "workflow_instance_id": "关联工作流实例",
    "non_project_task_id": "关联非项目任务",
    "task_id": "关联任务",
    "report_id": "关联日报",
    "arrangement_id": "关联稿件安排",
    "request_id": "关联交接申请",
    "message_id": "关联聊天消息",
    "attachment_id": "关联聊天附件",
    "related_project_id": "通知关联的翻译主订单",
    "client_code": "客户编码",
    "sub_client_code": "子客户编码",
    "client_name": "客户全称",
    "client_short_name": "客户简称",
    "english_name": "英文全称",
    "english_short_name": "英文简称",
    "client_manager": "客户方负责人",
    "manager_contact": "负责人联系方式",
    "field_level1": "一级业务领域",
    "field_level2": "二级业务领域",
    "country": "国家",
    "province": "省/州",
    "city": "城市",
    "district": "区县",
    "client_status": "客户状态",
    "cooperation_start_date": "合作开始时间",
    "consultation_code": "咨询编号",
    "consultation_time": "咨询时间",
    "consultation_method": "咨询方式",
    "client_source": "客户来源",
    "source_keyword": "来源关键词",
    "consultation_description": "咨询内容描述",
    "consultation_type": "咨询类型",
    "handling_method": "处理方式",
    "customer_service_id": "客服用户",
    "sales_person_id": "销售用户",
    "editor_id": "编辑用户",
    "follow_up_person_id": "跟进用户",
    "follow_up_count": "跟进次数",
    "follow_up_time": "最近/计划跟进时间",
    "follow_up_date": "跟进日期",
    "follow_up_status": "跟进状态",
    "follow_up_remarks": "跟进备注",
    "visit_count": "拜访次数",
    "visit_date": "拜访日期",
    "visit_type": "拜访方式",
    "client_attitude": "客户态度",
    "translator_code": "译员编码",
    "translator_name": "译员姓名",
    "cooperation_type": "合作类型",
    "contact_info": "综合联系方式",
    "translation_type": "翻译类型/擅长类型",
    "quality_score": "质量评分",
    "cloud_revision": "云端修订能力（历史字段）",
    "daily_rate": "日费率/历史报价文本",
    "direction": "翻译方向",
    "default_priority": "默认资源优先级",
    "schedule_remarks": "排班备注",
    "languages": "可承接语种",
    "gender": "性别",
    "height": "身高信息",
    "appearance": "形象描述",
    "nationality": "国籍",
    "ethnicity": "民族",
    "phone": "主要电话",
    "phone2": "备用电话",
    "email1": "主要邮箱",
    "email2": "备用邮箱",
    "resume_path": "简历文件路径",
    "other_contact": "其他联系方式",
    "overdue_count": "历史逾期次数",
    "overall_rating": "综合评价",
    "first_contact_date": "首次沟通时间",
    "available_time_slot": "可用时间段",
    "daily_accept_count": "每日可接单数量",
    "hourly_speed": "每小时处理速度",
    "daily_word_capacity": "每日字数产能",
    "can_cloud_edit": "是否可云端编辑",
    "can_revision": "是否可修订",
    "domain_skills": "领域技能列表",
    "availability_updated_at": "可用性最后更新时间",
    "schedule_date": "排班日期",
    "remaining_capacity": "当日剩余产能",
    "source_type": "数据来源类型",
    "source_ref": "来源对象标识",
    "last_confirmed_at": "最近确认时间",
    "order_no": "主订单号",
    "sub_order_no": "子订单号",
    "project_name": "项目名称",
    "sub_project_name": "子项目名称",
    "file_type_secondary": "二级文件类型",
    "customer_reception_time": "客户稿件接收时间",
    "customer_deadline_time": "客户要求截止时间",
    "sent_to_client_time": "发送客户时间",
    "client_feedback": "客户反馈",
    "project_status": "项目状态",
    "pm_confirmed_by": "项目经理确认人",
    "translator_assignment_time": "译员分配时间",
    "translator_delivery_progress": "译员交付进度",
    "pre_review_qc_progress": "审校前质检进度",
    "review1_progress": "一审进度",
    "review2_progress": "二审进度",
    "post_review_qc_progress": "审校后质检进度",
    "review_progress": "综合审校进度",
    "layout_progress": "排版进度",
    "consolidation_progress": "整合进度",
    "language_pair": "语言对",
    "priority": "优先级",
    "word_count": "项目字数",
    "network_file_path": "网络共享文件路径",
    "major_project_manager_confirmation": "大项目经理确认信息",
    "file_name": "文件名",
    "storage_path": "实际存储路径",
    "file_type": "文件业务类型",
    "file_ext": "扩展名",
    "file_size": "文件大小（字节）",
    "storage_type": "存储介质/类型",
    "uploaded_by": "上传用户",
    "dispatch_path": "派稿环节路径",
    "translation_path": "翻译环节路径",
    "client_delivery_path": "客户交付路径",
    "current_stage_key": "当前工作流阶段键",
    "current_assignee_id": "当前处理人",
    "difficulty": "项目难度",
    "file_editable": "文件是否可编辑",
    "stage_notes": "各阶段备注映射",
    "stage_data": "各阶段扩展数据",
    "group_assign_role": "组内分配所需角色",
    "operator_id": "操作用户",
    "from_stage": "流转前阶段",
    "to_stage": "流转后阶段",
    "direction": "流转方向",
    "next_assignee_id": "下一处理人",
    "requester_id": "交接发起人",
    "target_user_id": "交接目标用户",
    "handover_type": "交接类型",
    "reason_detail": "交接原因",
    "content": "正文内容",
    "content_json": "结构化富文本内容",
    "decision_note": "审批说明",
    "decided_by": "审批人",
    "decided_at": "审批时间",
    "expected_assignee_id": "交接时预期处理人",
    "enabled": "项目群聊是否启用",
    "enabled_by": "启用/停用操作人",
    "enabled_at": "启用时间",
    "sender_user_id": "消息发送用户",
    "sender_name": "发送人姓名快照",
    "message_type": "消息类型",
    "metadata": "消息扩展元数据",
    "mentioned_user_id": "被提及用户",
    "mentioned_user_name": "被提及用户名快照",
    "original_name": "上传时原始文件名",
    "storage_name": "存储系统中的唯一文件名",
    "content_type": "MIME 类型",
    "recipient_user_id": "通知接收用户",
    "title": "标题",
    "notification_type": "通知类型",
    "is_read": "是否已读",
    "read_at": "阅读时间",
    "settlement_method": "结算方式",
    "unit_price_excl_tax": "未税单价",
    "unit_price_incl_tax": "含税单价",
    "total_excl_tax": "未税总额",
    "total_incl_tax": "含税总额",
    "invoice_status": "开票状态",
    "stage_type": "款项阶段：定金/中期/尾款",
    "stage_no": "同阶段序号",
    "planned_amount": "计划收款金额",
    "actual_amount": "实际收款金额",
    "payment_time": "收款时间",
    "payment_method": "收款方式",
    "confirmed_by": "收款确认人",
    "confirmed_at": "确认时间",
    "task_type": "任务类型",
    "task_name": "任务名称",
    "assigner_id": "任务分配人",
    "assignee_id": "任务执行人",
    "assigned_at": "分配时间",
    "planned_completion_at": "计划完成时间",
    "actual_completion_at": "实际完成时间",
    "recurrence_template_id": "来源周期模板",
    "occurrence_date": "周期任务发生日期",
    "source_key": "外部/生成来源幂等键",
    "event_type": "事件类型",
    "from_status": "变更前状态",
    "to_status": "变更后状态",
    "detail": "事件扩展详情",
    "frequency": "重复频率",
    "weekdays": "每周执行日列表",
    "month_day": "每月执行日",
    "default_due_time": "默认截止时刻",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "work_date": "工作日期",
    "progress_content": "工作进展内容",
    "duration_minutes": "投入时长（分钟）",
    "result_content": "工作结果",
    "report_date": "日报日期",
    "supplemental_note": "日报补充说明",
    "generated_at": "日报生成时间",
    "finalized_at": "日报定稿时间",
    "source_id": "来源业务对象 ID",
    "display_metadata": "展示所需扩展快照",
    "sort_order": "显示顺序",
    "shift_table": "值班表 JSON 快照",
    "leave_notes": "请假信息 JSON 快照",
    "urgent_table_zh_en": "中译英紧急任务表",
    "urgent_table_en_zh": "英译中紧急任务表",
    "dept_person_data": "部门人员数据快照",
    "not_scheduled_tasks": "未排期任务快照",
    "pm_rotation_order": "项目经理轮值顺序",
    "updated_by": "最后更新用户；当前无数据库外键",
    "employee_id": "员工 UUID；当前无数据库外键",
    "employee_name": "员工姓名快照",
    "leave_type": "请假类型",
    "reason": "请假原因",
    "entity_type": "业务实体类型：主订单或子订单",
    "order_no_snapshot": "派发时订单号快照",
    "project_name_snapshot": "派发时项目名称快照",
    "translator_name_snapshot": "派发时译员姓名快照",
    "cooperation_type_snapshot": "派发时合作类型快照",
    "recipient_email": "译员收件邮箱",
    "planned_delivery_at": "计划交付时间",
    "manuscript_source_path": "稿件源文件路径",
    "email_subject": "派稿邮件主题",
    "email_body": "派稿邮件正文",
    "created_by_name": "创建人姓名快照",
    "sent_at": "邮件发送成功时间",
    "send_attempted_at": "最近发送尝试时间",
    "delivery_recipient": "实际投递收件人",
    "delivery_mode": "投递模式：测试/正式等",
    "smtp_message_id": "SMTP 服务返回的消息 ID",
    "send_error": "最近发送错误",
    "dispatch_id": "所属派发批次",
    "dimension": "字数统计维度",
    "metric_type": "字数计量口径",
    "count_value": "字数统计值",
    "translation_scope": "翻译范围说明",
    "custom_settlement_method": "自定义结算方式",
    "translator_unit_price": "译员单价",
    "translator_total_price": "译员总价",
    "milestone_type": "节点类型：阶段/最终",
    "name": "节点名称",
    "sequence_no": "节点顺序号",
    "planned_at": "计划节点时间",
    "cancelled_at": "取消时间",
}

TABLE_FIELD_DESCRIPTIONS = {
    ("translator", "direction"): "主要翻译方向",
    ("workflow_log", "direction"): "工作流流转方向",
    ("client_contact", "description"): "本次拜访/沟通说明",
    ("client_contact", "status"): "记录状态",
    ("consultation", "status"): "咨询处理状态",
    ("translator", "status"): "译员资源状态",
    ("translation_sub_order", "status"): "子订单状态",
    ("workflow_handover_request", "status"): "交接审批状态",
    ("non_project_task", "status"): "任务状态",
    ("daily_report", "status"): "日报状态：草稿/已定稿",
    ("manuscript_dispatch", "status"): "派发批次状态",
    ("manuscript_arrangement", "status"): "单个译员安排/邮件状态",
    ("manuscript_dispatch", "remarks"): "派发批次备注",
    ("manuscript_arrangement", "remarks"): "单个译员安排备注",
    ("workflow_log", "description"): "流转动作描述",
    ("workflow_log", "note"): "流转备注",
}


def field_description(table: str, column: str) -> str:
    if (table, column) in TABLE_FIELD_DESCRIPTIONS:
        return TABLE_FIELD_DESCRIPTIONS[(table, column)]
    if column in FIELD_DESCRIPTIONS:
        return FIELD_DESCRIPTIONS[column]
    if column.endswith("_id"):
        return f"关联的 {column[:-3]} ID"
    if column.endswith("_at"):
        return "业务时间"
    if column.endswith("_date"):
        return "业务日期"
    if column == "status":
        return "业务状态"
    if column == "remarks":
        return "备注"
    if column == "description":
        return "描述"
    return column.replace("_", " ")


def clean_default(value: object) -> str:
    if value is None:
        return "—"
    result = str(value)
    result = re.sub(r"::(?:character varying|text|jsonb|boolean)", "", result)
    result = result.replace("CURRENT_TIMESTAMP", "当前时间").replace("now()", "当前时间")
    return f"`{result}`"


def format_type(value: object) -> str:
    return str(value).lower().replace("timestamp without time zone", "timestamp")


def escape_md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def load_schema():
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema="public"))
    schema = {}
    for table in tables:
        schema[table] = {
            "columns": inspector.get_columns(table, schema="public"),
            "pk": inspector.get_pk_constraint(table, schema="public"),
            "fks": inspector.get_foreign_keys(table, schema="public"),
            "uniques": inspector.get_unique_constraints(table, schema="public"),
            "checks": inspector.get_check_constraints(table, schema="public"),
            "indexes": inspector.get_indexes(table, schema="public"),
        }
    return inspector, tables, schema


def module_for(table: str) -> str:
    for module, tables in MODULES.items():
        if table in tables:
            return module
    return "其他"


def column_constraints(table: str, column: dict, meta: dict) -> str:
    name = column["name"]
    labels = []
    if name in (meta["pk"].get("constrained_columns") or []):
        labels.append("PK")
    for fk in meta["fks"]:
        if name in fk["constrained_columns"]:
            target_columns = fk["referred_columns"]
            position = fk["constrained_columns"].index(name)
            target_column = target_columns[min(position, len(target_columns) - 1)]
            labels.append(f"FK → {fk['referred_table']}.{target_column}")
    for unique in meta["uniques"]:
        columns = unique.get("column_names") or []
        if name in columns:
            labels.append("UQ" if len(columns) == 1 else "组合 UQ")
    labels.append("可空" if column["nullable"] else "非空")
    return "；".join(labels)


def generate_dictionary(tables: list[str], schema: dict, snapshot_at: str) -> str:
    lines = [
        "# 数据字典",
        "",
        f"> 结构快照：{snapshot_at}；来源：当前连接的 PostgreSQL `public` schema。",
        "",
        "## 阅读说明",
        "",
        "- `PK`：主键；`FK`：外键；`UQ`：唯一约束；`组合 UQ`：字段参与组合唯一约束。",
        "- 所有 `timestamp` 均为 PostgreSQL `timestamp without time zone`；应用连接会话时区固定为 `Asia/Hong_Kong`。",
        "- JSONB 字段保存结构化快照或可扩展数据，具体 JSON 形状由应用层 schema/服务代码约束。",
        "- 表级 CHECK、组合唯一约束和索引列在每张表字段清单后单独列出。",
        "",
    ]
    for module, module_tables in MODULES.items():
        present = [table for table in module_tables if table in schema]
        if not present:
            continue
        lines.extend([f"## {module}", ""])
        for table in present:
            meta = schema[table]
            lines.extend(
                [
                    f"### `{table}`",
                    "",
                    TABLE_PURPOSES.get(table, "业务数据表") + "。",
                    "",
                    "| 字段 | 类型 | 约束 | 默认值 | 中文说明 |",
                    "|---|---|---|---|---|",
                ]
            )
            for column in meta["columns"]:
                lines.append(
                    "| `{name}` | `{type_}` | {constraints} | {default} | {description} |".format(
                        name=column["name"],
                        type_=format_type(column["type"]),
                        constraints=column_constraints(table, column, meta),
                        default=clean_default(column.get("default")),
                        description=escape_md(field_description(table, column["name"])),
                    )
                )
            lines.append("")
            details = []
            for unique in meta["uniques"]:
                columns = ", ".join(f"`{name}`" for name in unique.get("column_names") or [])
                if len(unique.get("column_names") or []) > 1:
                    details.append(f"组合唯一：{columns}")
            for check in meta["checks"]:
                details.append(f"CHECK：`{escape_md(check.get('sqltext') or '')}`")
            visible_indexes = [
                index
                for index in meta["indexes"]
                if not index.get("duplicates_constraint")
            ]
            for index in visible_indexes:
                columns = ", ".join(f"`{name}`" for name in index.get("column_names") or [])
                prefix = "唯一索引" if index.get("unique") else "索引"
                details.append(f"{prefix} `{index['name']}`：{columns}")
            if details:
                lines.append("表级规则：" + "；".join(details) + "。")
                lines.append("")

    lines.extend(
        [
            "## 视图",
            "",
            "### `v_finance_record_display`",
            "",
            "财务展示视图：以 `finance_record` 为主表，连接 `translation_project` 和 `client`，输出订单号、客户简称、项目名称、项目状态、报价金额、开票状态等列表展示字段。",
            "",
        ]
    )
    return "\n".join(lines)


def generate_design(
    tables: list[str],
    schema: dict,
    views: list[str],
    snapshot_at: str,
    server_version: str,
) -> str:
    fk_count = sum(len(schema[table]["fks"]) for table in tables)
    orm_tables = sorted(Base.metadata.tables)
    only_db = sorted(set(tables) - set(orm_tables))
    only_orm = sorted(set(orm_tables) - set(tables))
    drift_rows = []
    for table_name in sorted(set(tables) & set(orm_tables)):
        actual = schema[table_name]
        orm_table = Base.metadata.tables[table_name]
        actual_columns = {column["name"]: column for column in actual["columns"]}
        orm_columns = {column.name: column for column in orm_table.columns}
        database_only_columns = sorted(set(actual_columns) - set(orm_columns))
        orm_only_columns = sorted(set(orm_columns) - set(actual_columns))
        if database_only_columns:
            drift_rows.append(
                f"| `{table_name}` | 数据库额外字段 | "
                + ", ".join(f"`{column}`" for column in database_only_columns)
                + " |"
            )
        if orm_only_columns:
            drift_rows.append(
                f"| `{table_name}` | ORM 额外字段 | "
                + ", ".join(f"`{column}`" for column in orm_only_columns)
                + " |"
            )
        nullable_differences = []
        for column_name in sorted(set(actual_columns) & set(orm_columns)):
            database_nullable = bool(actual_columns[column_name]["nullable"])
            orm_nullable = bool(orm_columns[column_name].nullable)
            if database_nullable != orm_nullable:
                nullable_differences.append(
                    f"`{column_name}`（库={'可空' if database_nullable else '非空'}，"
                    f"ORM={'可空' if orm_nullable else '非空'}）"
                )
        if nullable_differences:
            drift_rows.append(
                f"| `{table_name}` | 可空性差异 | {', '.join(nullable_differences)} |"
            )
        database_foreign_keys = {
            (
                source,
                foreign_key["referred_table"],
                target,
                (foreign_key.get("options") or {}).get("ondelete"),
            )
            for foreign_key in actual["fks"]
            for source, target in zip(
                foreign_key.get("constrained_columns") or [],
                foreign_key.get("referred_columns") or [],
            )
        }
        orm_foreign_keys = {
            (
                element.parent.name,
                element.column.table.name,
                element.column.name,
                constraint.ondelete,
            )
            for constraint in orm_table.foreign_key_constraints
            for element in constraint.elements
        }
        database_only_foreign_keys = sorted(
            database_foreign_keys - orm_foreign_keys, key=str
        )
        orm_only_foreign_keys = sorted(
            orm_foreign_keys - database_foreign_keys, key=str
        )
        if database_only_foreign_keys:
            formatted = ", ".join(
                f"`{source}` → `{target_table}.{target_column}`"
                for source, target_table, target_column, _ in database_only_foreign_keys
            )
            drift_rows.append(
                f"| `{table_name}` | 仅数据库声明外键 | {formatted} |"
            )
        if orm_only_foreign_keys:
            formatted = ", ".join(
                f"`{source}` → `{target_table}.{target_column}`"
                for source, target_table, target_column, _ in orm_only_foreign_keys
            )
            drift_rows.append(f"| `{table_name}` | 仅 ORM 声明外键 | {formatted} |")
        database_unique = {
            tuple(constraint.get("column_names") or [])
            for constraint in actual["uniques"]
        }
        database_unique |= {
            tuple(index.get("column_names") or [])
            for index in actual["indexes"]
            if index.get("unique")
        }
        orm_unique = {
            tuple(column.name for column in constraint.columns)
            for constraint in orm_table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        orm_unique |= {
            tuple(column.name for column in index.columns)
            for index in orm_table.indexes
            if index.unique
        }
        database_only_unique = sorted(database_unique - orm_unique)
        orm_only_unique = sorted(orm_unique - database_unique)
        if database_only_unique:
            formatted = ", ".join(
                "(" + ", ".join(f"`{column}`" for column in columns) + ")"
                for columns in database_only_unique
            )
            drift_rows.append(
                f"| `{table_name}` | 仅数据库声明唯一 | {formatted} |"
            )
        if orm_only_unique:
            formatted = ", ".join(
                "(" + ", ".join(f"`{column}`" for column in columns) + ")"
                for columns in orm_only_unique
            )
            drift_rows.append(f"| `{table_name}` | 仅 ORM 声明唯一 | {formatted} |")
    dump_path = ROOT / "xinshi_system.sql"
    dump_tables = []
    if dump_path.exists():
        dump_text = dump_path.read_text(encoding="utf-8", errors="ignore")
        dump_tables = sorted(
            set(re.findall(r"^CREATE TABLE public\.([a-zA-Z0-9_]+)", dump_text, re.MULTILINE))
        )
    table_drift_text = (
        "一致：实际库与 ORM 均为 "
        f"{len(tables)} 张表。"
        if not only_db and not only_orm
        else f"存在差异：仅数据库 {only_db or '无'}；仅 ORM {only_orm or '无'}。"
    )
    dump_text = (
        f"根目录旧备份只含 {len(dump_tables)} 张表，比当前结构少 "
        f"{len(set(tables) - set(dump_tables))} 张表，不应作为当前结构的唯一依据。"
        if dump_tables
        else "未检测到根目录数据库备份。"
    )
    module_rows = []
    for module, module_tables in MODULES.items():
        present = [f"`{table}`" for table in module_tables if table in schema]
        module_rows.append(f"| {module} | {len(present)} | {', '.join(present)} |")

    return "\n".join(
        [
            "# 数据库整体设计",
            "",
            f"> 结构快照：{snapshot_at}；数据库：{server_version.split(',')[0]}；schema：`public`。",
            "",
            "## 1. 当前结论",
            "",
            f"- 当前实际数据库包含 **{len(tables)} 张表、{len(views)} 个视图、{fk_count} 条外键关系**。",
            f"- ORM 表集合检查：{table_drift_text}",
            f"- ORM 字段/约束检查：发现 **{len(drift_rows)} 项差异**，详见第 8 节；实际运行约束以数据库为准。",
            f"- SQL 备份时效：{dump_text}",
            "- 主键统一采用 UUID，并由 PostgreSQL `pgcrypto` 的 `gen_random_uuid()` 生成。",
            "- 应用通过 SQLAlchemy + psycopg2 连接；连接池启用 `pool_pre_ping`；数据库会话时区设置为 `Asia/Hong_Kong`。",
            f"- 实际服务版本：`{escape_md(server_version)}`。",
            "",
            "## 2. 结构来源与可信度",
            "",
            "本次按以下优先级还原结构：",
            "",
            "1. 当前 `.env` 指向的实际 PostgreSQL：字段、外键、唯一约束、CHECK、索引、视图和触发器。",
            "2. `models.py`、`workflow_models.py`、`task_models.py`、`manuscript_models.py`：核对 ORM 映射和业务关系。",
            "3. `data/migrations/`：确认近期权限、交接、日报、稿件安排等增量。",
            "4. 根目录 `xinshi_system.sql`：仅用于识别较早的基线结构，不作为当前真相源。",
            "",
            "## 3. 模块划分",
            "",
            "| 模块 | 表数 | 表 |",
            "|---|---:|---|",
            *module_rows,
            "",
            "## 4. 核心业务关系",
            "",
            "```mermaid",
            "flowchart LR",
            "    U[用户与角色] --> P[翻译主订单]",
            "    C[客户/子客户] --> P",
            "    T[译员资源/日程] --> P",
            "    P --> S[翻译子订单]",
            "    P --> W[工作流实例与日志]",
            "    S --> W",
            "    W --> H[交接申请]",
            "    P --> F[文件/群聊/通知]",
            "    P --> M[财务记录与收款]",
            "    P --> D[稿件派发与交付节点]",
            "    S --> D",
            "    W --> E[工作投入/日报]",
            "    N[非项目任务] --> E",
            "```",
            "",
            "完整字段级关系见 [er_diagram.drawio](./er_diagram.drawio)，图中拆为 4 个页面。",
            "",
            "## 5. 关键关系说明",
            "",
            "### 5.1 客户—项目—财务",
            "",
            "- `client` 1:N `translation_project`，删除被项目使用的客户会被 `RESTRICT` 阻止。",
            "- `client` 1:N `sub_client`，子客户随母客户级联删除。",
            "- `translation_project` 1:N `translation_sub_order`；主订单删除时子订单级联删除。",
            "- `translation_project` 1:0..1 `finance_record`；`finance_record.project_id` 唯一。",
            "- `finance_record` 1:N `finance_payment`；同一财务记录的 `(stage_type, stage_no)` 唯一。",
            "",
            "### 5.2 项目—工作流",
            "",
            "- 每个 `workflow_instance` 必须且只能关联主订单或子订单之一，由 XOR CHECK 约束保证。",
            "- 主订单和子订单分别通过唯一索引保证最多一个工作流实例。",
            "- `workflow_log` 保存阶段前后值、操作人、下一处理人和说明，是主要审计轨迹。",
            "- 交接申请通过 `workflow_handover_item` 一次包含多个工作流实例，并可复用项目聊天附件。",
            "",
            "### 5.3 项目协作",
            "",
            "- 每个项目最多一条 `chat_project_enabled` 设置。",
            "- 消息、提及、附件采用实体表 + 关联表设计；删除消息会级联删除提及和消息附件关联，但附件实体可继续被交接使用。",
            "- `app_notification` 随接收用户级联删除；关联项目删除时仅将项目引用置空。",
            "",
            "### 5.4 任务—工时—日报",
            "",
            "- 周期模板生成 `non_project_task`；模板删除时已生成任务保留，并将模板引用置空。",
            "- `work_entry` 必须且只能关联一个工作流实例或一个非项目任务。",
            "- `daily_report` 按 `(user_id, report_date)` 唯一；`daily_report_item` 是定稿时的展示快照。",
            "",
            "### 5.5 稿件派发",
            "",
            "- `manuscript_dispatch` 表示一次主订单/子订单派发批次。",
            "- `manuscript_arrangement` 表示批次内单个译员的安排，保存订单、项目、译员和邮件投递快照。",
            "- `manuscript_delivery_milestone` 通过 `(arrangement_id, sequence_no)` 保证节点顺序唯一。",
            "",
            "## 6. 数据库级规则",
            "",
            "- 删除策略以业务语义区分：明细和关联表多为 `CASCADE`，历史记录引用人员多为 `SET NULL`，关键业务主体多为 `RESTRICT`。",
            "- 财务金额均使用定点 `numeric`，并有非负 CHECK；收款确认人和确认时间必须同时为空或同时存在。",
            "- 状态字段在日报、任务、财务、稿件等新模块中使用 CHECK 限制允许值；较早的项目/咨询状态仍主要由应用层约束。",
            "- `finance_record`、`finance_payment` 使用 `set_updated_at()` 触发器自动刷新 `updated_at`。",
            "- `v_finance_record_display` 连接财务记录、项目与客户，为财务列表提供去外键化展示。",
            "",
            "## 7. JSONB 使用点",
            "",
            "| 表.字段 | 用途 |",
            "|---|---|",
            "| `app_user.fixed_tasks` | 用户固定任务配置 |",
            "| `workflow_instance.stage_notes/stage_data` | 各工作流阶段备注和扩展数据 |",
            "| `chat_project_message.content_json/metadata` | 富文本消息和消息元数据 |",
            "| `workflow_handover_request.content_json` | 富文本交接说明 |",
            "| `non_project_task_recurrence.weekdays` | 周期模板执行日 |",
            "| `non_project_task_event.detail` | 状态事件详情 |",
            "| `daily_report_item.display_metadata` | 日报展示快照 |",
            "| `translator.domain_skills` | 译员领域技能 |",
            "| `work_schedule.*_table/leave_notes/dept_person_data/not_scheduled_tasks` | 每日排班聚合快照 |",
            "",
            "## 8. ORM 与实际库差异",
            "",
            "| 表 | 差异类型 | 详情 |",
            "|---|---|---|",
            *(drift_rows or ["| — | 无 | 当前未发现字段、可空性或唯一约束差异 |"]),
            "",
            "这类差异不代表数据已经损坏，但会让开发期校验、自动建表和生产库行为不完全一致。建议以正式迁移脚本统一两侧定义。",
            "",
            "## 9. 已识别的维护风险",
            "",
            "1. `database.py` 存在默认明文数据库口令。应删除代码内默认口令，强制从环境变量或密钥管理读取，并轮换当前口令。",
            "2. `.env.example` 的中文注释当前出现编码异常，建议统一保存为 UTF-8。",
            "3. `work_schedule.updated_by`、`employee_leave.employee_id` 是 UUID，但当前数据库和 ORM 都没有外键；可能产生孤儿引用。",
            "4. `manuscript_arrangement` 有 `entity_type` 状态检查，但缺少“主订单/子订单二选一”的跨字段 CHECK；其一致性目前依赖应用层。",
            "5. 多处时间字段是无时区 `timestamp`。虽然连接会话固定香港时区，跨时区集成时仍应约定统一解释方式。",
            "6. 根目录 SQL 备份明显早于当前迁移。恢复演练应使用新 `pg_dump`，并验证迁移脚本可重复执行。",
            "",
            "## 10. 文档更新方法",
            "",
            "数据库结构变化后，在项目根目录执行：",
            "",
            "```powershell",
            "python tools/generate_database_docs.py",
            "```",
            "",
            "脚本只读取数据库元数据，不读取业务行数据，也不会把口令或连接串写入文档。",
            "",
        ]
    )


def add_cell(root, cell_id: str, value: str, style: str, parent: str = "1", **geometry):
    cell = ET.SubElement(
        root,
        "mxCell",
        {"id": cell_id, "value": value, "style": style, "vertex": "1", "parent": parent},
    )
    ET.SubElement(
        cell,
        "mxGeometry",
        {
            "x": str(geometry.get("x", 0)),
            "y": str(geometry.get("y", 0)),
            "width": str(geometry.get("width", 280)),
            "height": str(geometry.get("height", 150)),
            "as": "geometry",
        },
    )


def add_edge(
    root,
    cell_id: str,
    source: str,
    target: str,
    value: str,
):
    cell = ET.SubElement(
        root,
        "mxCell",
        {
            "id": cell_id,
            "value": value,
            "style": (
                "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
                "jettySize=auto;html=1;endArrow=ERmany;startArrow=ERone;"
                "startFill=0;endFill=0;strokeColor=#666666;fontSize=9;"
            ),
            "edge": "1",
            "parent": "1",
            "source": source,
            "target": target,
        },
    )
    ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})


def new_graph():
    graph = ET.Element(
        "mxGraphModel",
        {
            "dx": "1422",
            "dy": "794",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "3300",
            "pageHeight": "2400",
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    return graph, root


def table_label(table: str, meta: dict) -> str:
    pk = set(meta["pk"].get("constrained_columns") or [])
    fk_columns = {
        column
        for fk in meta["fks"]
        for column in (fk.get("constrained_columns") or [])
    }
    unique_columns = {
        column
        for unique in meta["uniques"]
        for column in (unique.get("column_names") or [])
    }
    business = [
        column["name"]
        for column in meta["columns"]
        if column["name"] not in pk | fk_columns | unique_columns
        and column["name"] not in {"created_at", "updated_at"}
    ][:3]
    selected = []
    for column in meta["columns"]:
        name = column["name"]
        if name in pk | fk_columns | unique_columns or name in business:
            marks = []
            if name in pk:
                marks.append("PK")
            if name in fk_columns:
                marks.append("FK")
            if name in unique_columns:
                marks.append("UQ")
            prefix = f"[{'/'.join(marks)}] " if marks else ""
            selected.append(f"{prefix}{name}: {format_type(column['type'])}")
    fields = "<br>".join(html.escape(value) for value in selected)
    purpose = html.escape(TABLE_PURPOSES.get(table, "业务数据表"))
    return (
        f"<b style='font-size:14px'>{html.escape(table)}</b>"
        f"<br><span style='color:#555'>{purpose}</span><hr>{fields}"
    )


def build_table_page(page_name: str, page_tables: list[str], schema: dict):
    graph, root = new_graph()
    ids = {}
    for index, table in enumerate(page_tables):
        if table not in schema:
            continue
        module = module_for(table)
        fill, stroke = MODULE_COLORS.get(module, ("#f5f5f5", "#666666"))
        cell_id = f"t{index + 1}"
        ids[table] = cell_id
        columns = schema[table]["columns"]
        height = min(260, max(145, 90 + 17 * min(len(columns), 9)))
        add_cell(
            root,
            cell_id,
            table_label(table, schema[table]),
            (
                "rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
                f"spacing=8;fillColor={fill};strokeColor={stroke};fontSize=11;"
            ),
            x=30 + (index % 4) * 390,
            y=30 + (index // 4) * 300,
            width=340,
            height=height,
        )
    edge_index = 1
    for table in page_tables:
        if table not in schema:
            continue
        for fk in schema[table]["fks"]:
            target = fk["referred_table"]
            if target not in ids:
                continue
            label = ", ".join(fk["constrained_columns"])
            add_edge(root, f"e{edge_index}", ids[target], ids[table], label)
            edge_index += 1
    return graph


def build_overview_page():
    graph, root = new_graph()
    module_ids = {}
    for index, (module, tables) in enumerate(MODULES.items()):
        fill, stroke = MODULE_COLORS[module]
        module_id = f"m{index + 1}"
        module_ids[module] = module_id
        label = (
            f"<b style='font-size:16px'>{html.escape(module)}</b><hr>"
            + "<br>".join(html.escape(table) for table in tables)
        )
        add_cell(
            root,
            module_id,
            label,
            (
                "rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
                f"spacing=10;fillColor={fill};strokeColor={stroke};fontSize=11;"
            ),
            x=40 + (index % 4) * 390,
            y=40 + (index // 4) * 330,
            width=330,
            height=230,
        )
    dependencies = [
        ("身份与权限", "客户与咨询", "人员负责"),
        ("身份与权限", "项目与文件", "创建/确认"),
        ("客户与咨询", "项目与文件", "客户下单"),
        ("译员资源", "项目与文件", "译员承接"),
        ("项目与文件", "工作流与交接", "驱动流程"),
        ("项目与文件", "协作与通知", "项目协作"),
        ("项目与文件", "财务", "项目结算"),
        ("项目与文件", "稿件安排", "派发稿件"),
        ("工作流与交接", "任务与日报", "记录工时"),
        ("排班与请假", "工作流与交接", "触发交接"),
    ]
    for index, (source, target, label) in enumerate(dependencies, 1):
        add_edge(root, f"oe{index}", module_ids[source], module_ids[target], label)
    return graph


def generate_drawio(schema: dict, generated_at: str) -> str:
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "modified": generated_at,
            "agent": "Codex database documentation generator",
            "version": "24.7.17",
            "type": "device",
            "compressed": "false",
        },
    )
    pages = [
        ("系统总览", build_overview_page()),
        (
            "核心业务",
            build_table_page(
                "核心业务",
                [
                    "app_user",
                    "role",
                    "user_role",
                    "role_permission",
                    "client",
                    "sub_client",
                    "client_contact",
                    "consultation",
                    "translator",
                    "translator_schedule",
                    "translation_project",
                    "translation_sub_order",
                    "project_file",
                    "finance_record",
                    "finance_payment",
                ],
                schema,
            ),
        ),
        (
            "工作流与协作",
            build_table_page(
                "工作流与协作",
                [
                    "app_user",
                    "translation_project",
                    "translation_sub_order",
                    "workflow_instance",
                    "workflow_log",
                    "workflow_handover_request",
                    "workflow_handover_item",
                    "workflow_handover_attachment",
                    "chat_project_enabled",
                    "chat_project_message",
                    "chat_project_mention",
                    "chat_project_attachment",
                    "chat_project_message_attachment",
                    "app_notification",
                ],
                schema,
            ),
        ),
        (
            "任务排班与稿件",
            build_table_page(
                "任务排班与稿件",
                [
                    "app_user",
                    "translator",
                    "translation_project",
                    "translation_sub_order",
                    "workflow_instance",
                    "non_project_task_recurrence",
                    "non_project_task",
                    "non_project_task_event",
                    "work_entry",
                    "daily_report",
                    "daily_report_item",
                    "work_schedule",
                    "employee_leave",
                    "manuscript_dispatch",
                    "manuscript_arrangement",
                    "manuscript_delivery_milestone",
                ],
                schema,
            ),
        ),
    ]
    for index, (name, graph) in enumerate(pages, 1):
        diagram = ET.SubElement(mxfile, "diagram", {"id": f"page-{index}", "name": name})
        diagram.append(graph)
    ET.indent(mxfile, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        mxfile, encoding="unicode"
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inspector, tables, schema = load_schema()
    snapshot_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with engine.connect() as connection:
        server_version = connection.execute(text("select version()")).scalar_one()
    views = sorted(inspector.get_view_names(schema="public"))

    (OUTPUT_DIR / "database_design.md").write_text(
        generate_design(tables, schema, views, snapshot_at, server_version),
        encoding="utf-8",
        newline="\n",
    )
    (OUTPUT_DIR / "data_dictionary.md").write_text(
        generate_dictionary(tables, schema, snapshot_at),
        encoding="utf-8",
        newline="\n",
    )
    (OUTPUT_DIR / "er_diagram.drawio").write_text(
        generate_drawio(schema, generated_at),
        encoding="utf-8",
        newline="\n",
    )
    print(f"已生成：{OUTPUT_DIR}")
    print(f"表：{len(tables)}；视图：{len(views)}；外键：{sum(len(schema[t]['fks']) for t in tables)}")


if __name__ == "__main__":
    main()
