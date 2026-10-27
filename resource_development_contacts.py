"""扩展资源账号的保存、审计与权限遮罩。"""
from uuid import uuid4

from resource_development_models import DevelopmentResourceContact as Contact, DevelopmentAudit
from business_time import business_now


def contact_data(db, record_id, allowed=True):
    row = db.get(Contact, record_id)
    whatsapp = row.whatsapp if row else ""
    accounts = [dict(item) for item in (row.custom_accounts or [])] if row else []
    if not allowed:
        whatsapp = "******" if whatsapp else ""
        accounts = [{"name": item["name"], "value": "******"} for item in accounts]
    return {"whatsapp": whatsapp, "custom_accounts": accounts,
            "custom_accounts_text": "；".join(f'资源{item["name"]}号：{item["value"]}' for item in accounts)}


def save_contacts(db, user, record_id, payload):
    fields = payload.model_fields_set & {"whatsapp", "custom_accounts"}
    if not fields:
        return
    row = db.get(Contact, record_id)
    before = contact_data(db, record_id)
    values = {"whatsapp": before["whatsapp"], "custom_accounts": before["custom_accounts"]}
    if "whatsapp" in fields:
        values["whatsapp"] = payload.whatsapp
    if "custom_accounts" in fields:
        values["custom_accounts"] = [item.model_dump() for item in payload.custom_accounts]
    if all(values[key] == before[key] for key in values):
        return
    if row is None:
        row = Contact(record_id=record_id)
        db.add(row)
    row.whatsapp, row.custom_accounts = values["whatsapp"], values["custom_accounts"]
    db.add(DevelopmentAudit(id=uuid4(), entity_id=record_id, entity_type="record_contacts",
                            actor_id=user.id, action="update" if before["whatsapp"] or before["custom_accounts"] else "create",
                            before=before, after=values, created_at=business_now()))
