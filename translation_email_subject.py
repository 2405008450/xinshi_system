"""笔译邮件主题由业务信息生成，不从项目名称或文件名拼接。"""

from datetime import datetime

from language_catalog import compact_translation_direction


def build_translation_email_subject(source: dict) -> dict:
    deadline = source.get("customer_deadline_time")
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            deadline = None
    deadline_text = f"{deadline.month}月{deadline.day}日{deadline.hour}点回稿" if deadline else ""
    direction = compact_translation_direction(source.get("language_pair"))
    fields = [
        ("标题前缀", source.get("subject_prefix")),
        ("订单号", source.get("order_no")),
        ("客户简称", source.get("client_short_name")),
        ("客户经理联系方式", source.get("manager_contact")),
        ("翻译方向", direction),
        ("客户交稿时间", deadline_text),
    ]
    count = max(0, int(source.get("sub_order_count") or 0))
    if count:
        fields.append(("批次", f"{count}批"))
    parts = [str(value).strip() for _, value in fields if str(value or "").strip()]
    optional = {"标题前缀", "客户经理联系方式", "批次"}
    missing = [label for label, value in fields if label not in optional and not str(value or "").strip()]
    return {"parts": parts, "subject": "，".join(parts), "missing_fields": missing}
