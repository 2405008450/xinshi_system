"""生成客户姓名规则的只读预览；无执行选项，不调用模型，不修改业务库。"""
import json
from pathlib import Path
import re
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main  # 仅注册 ORM 模型，不启动应用或迁移。
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from database import engine
from resource_models import ResourcePerson
from resource_service import _person_options, get_talent_project_situations
from talent_duplicate_schemas import NameMergePreviewRequest
from talent_duplicate_service import active_query, archive_options, contact_identifiers
from talent_name_merge_service import list_groups, preview_group, _version
from talent_privacy import RESOURCE_CONTACT_FIELDS


def run():
    if socket.gethostname().upper() != "PC" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("只允许在 PC 的项目目录生成只读预览")
    output = ROOT / "outputs/talent-name-merge-preview"
    output.mkdir(parents=True, exist_ok=True)
    with engine.connect() as connection, Session(bind=connection) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        summary = list_groups(db, limit=20)
        summary["sample_note"] = "统计覆盖全库；示例列表仅前 20 组。当前脚本未执行合并。"
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        # 以用户之前指出的同名组展示完整规则预览；联系方式及附件签名链接不输出明文。
        key = "张小真"
        people = active_query(db, db.query(ResourcePerson)).filter(
            func.resource_person_duplicate_name_key(ResourcePerson.full_name) == key
        ).options(*_person_options(), *archive_options(db)).all()
        if len(people) >= 2:
            situations = get_talent_project_situations(db, [p.id for p in people])
            proposed = preview_group(db, NameMergePreviewRequest(group_key=key, group_version=_version(people, situations)))
            tokens = set()
            for person in people:
                for field in RESOURCE_CONTACT_FIELDS:
                    value = str(getattr(person, field, None) or "").strip()
                    if len(value) > 2:
                        tokens.add(value)
                for values in contact_identifiers(person).values():
                    tokens.update(value for value in values if len(value) > 2)
            pattern = re.compile("|".join(re.escape(value) for value in sorted(tokens, key=len, reverse=True)), re.I) if tokens else None
            def redact(value):
                if isinstance(value, dict):
                    if value.get("key") in RESOURCE_CONTACT_FIELDS:
                        value = {**value, "value": "******" if value.get("value") else value.get("value"),
                                 "before_value": "******" if value.get("before_value") else value.get("before_value"),
                                 "options": [{**option, "value": "******" if option.get("value") else option.get("value")}
                                             for option in value.get("options", [])]}
                    return {key: item if key in {"id", "person_id", "target_id", "archive_ids", "value_hash"} else redact(item)
                            for key, item in value.items()}
                if isinstance(value, list):
                    return [redact(item) for item in value]
                if isinstance(value, str):
                    value = re.sub(r"https?://\S+", "[附件链接已脱敏]", value)
                    value = pattern.sub("******", value) if pattern else value
                    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "******", value)
                    return re.sub(r"\+?\d[\d ()-]{5,}\d", "******", value)
                return value
            example = {"created_at": summary["created_at"], "group_key": key, "preview_only": True,
                       "audit": redact(proposed["audit"])}
            (output / "example.json").write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
        db.rollback()
    print(json.dumps({key: summary[key] for key in ("total", "counts", "archive_count", "created_at")}, ensure_ascii=False))


if __name__ == "__main__":
    run()
