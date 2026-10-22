"""新建标注项目的结构化会话通知。"""
from annotation_progress_chat import enqueue
from annotation_task_images import chat_attachments
from annotation_schemas import ANNOTATION_PROJECT_STATUS_LABELS, ANNOTATION_PROJECT_TYPE_LABELS
from business_time import business_iso


def creation_card(project):
    pairs=[('订单号',project.order_no),('项目名称',project.project_name),
        ('项目类型','、'.join(ANNOTATION_PROJECT_TYPE_LABELS.get(code,code) for code in project.project_types or [])),
        ('项目状态/进度',ANNOTATION_PROJECT_STATUS_LABELS.get(project.project_status,project.project_status)),
        ('客户简称',project.client_short_name),('语言方向',project.language_items_display),
        ('任务提交时间',business_iso(project.task_submitted_at) if project.task_submitted_at else '待定'),
        ('客户单价',project.customer_price_summary),('具体任务',project.task_description)]
    return {'type':'annotation_creation','title':'新建标注项目','fields':[{'label':label,'value':str(value or '-')} for label,value in pairs]}


def send_creation(db,project,user_id,delivery):
    if not delivery or not delivery.send_to_chat:return
    card=creation_card(project)
    content='新建标注项目\n'+'\n'.join(f"{row['label']}：{row['value']}" for row in card['fields'])
    enqueue(db,project.id,user_id,delivery,track='creation',note=content,effective_on=project.created_at,
        attachment_ids=chat_attachments(db,project,user_id),content_json=card)
