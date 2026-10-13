"""核重原资料留存：冻结数据库快照、附件内容副本及受控读取，不依赖当前主档。"""
import copy
import hashlib
import os
from pathlib import Path
import re
import tempfile

from fastapi import HTTPException
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

from business_time import business_iso
from talent_duplicate_models import TalentDuplicateOperation
from talent_duplicate_service import (
    COLLECTIONS, PROFILES, SYSTEM_FIELDS, digest, field_label, operation_result, require_ready, review_ready,
)

RETENTION_POLICY = "来源档案只读归档；包括原主档在内的合并前字段、明细及业务关联按操作保存冻结快照。后续编辑、再次合并和撤销不覆盖该快照；系统上传附件另存按内容散列去重的副本，外部简历路径只保存原引用。"
SYSTEM_LABELS = {"id": "人员 ID", "resource_code": "人才编号", "created_at": "创建时间", "updated_at": "更新时间",
                 "operated_at": "原操作时间", "operated_by": "原操作人 ID", "operator_name": "原操作人",
                 "archived_into_id": "原归档指向", "archived_at": "原归档时间", "idempotency_key": "原导入幂等键",
                 "wechat_accounts_revision": "公司微信账号版本", "wechat_contact_state": "公司账号联系状态"}


def archive_root():
    default = Path(__file__).resolve().parent / "data/talent_review_archives"
    return Path(os.getenv("TALENT_REVIEW_ARCHIVE_DIR", str(default))).resolve()


def _blob_path(checksum):
    if not re.fullmatch(r"[a-f0-9]{64}", str(checksum or "")):
        raise HTTPException(409, "附件留存校验标识无效")
    return archive_root() / "blobs" / checksum[:2] / (checksum + ".bin")


def _hash_file(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _preserve_file(attachment):
    from talent_attachment_service import attachment_path
    source = attachment_path(attachment["storage_name"])
    result = {"attachment_id": attachment["id"], "original_name": attachment.get("original_name"),
              "content_type": attachment.get("content_type"), "original_size": attachment.get("file_size")}
    if not source.is_file():
        return {**result, "state": "missing_at_merge", "message": "合并时原附件文件已缺失；保留原记录，未生成文件副本"}
    temporary = None
    try:
        directory = archive_root() / "blobs"
        directory.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=directory, prefix="retain-", delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as input_file:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                    output.write(chunk); checksum.update(chunk); size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        hashed = checksum.hexdigest()
        destination = _blob_path(hashed)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _hash_file(destination) != hashed:
                raise HTTPException(409, "已有留存附件校验不一致，请先检查留存存储")
        else:
            # 只写新内容，绝不覆盖已有留存副本；共用人才写锁防止同内容并发发布。
            temporary.replace(destination)
            temporary = None
        return {**result, "state": "archived", "sha256": hashed, "file_size": size,
                **({"message": "原记录大小与实际文件不同；保留实际读取的文件副本"} if size != result["original_size"] else {})}
    except OSError as exc:
        raise HTTPException(503, "原附件副本留存失败，本组合并未提交") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_retention(db, proposed, *, people=None):
    """在修改人员前制作留存；数据库失败可能留下未引用内容副本，不自动删除共享文件。"""
    from talent_duplicate_service import _load_people
    from uuid import UUID
    labels, attachments = {}, []
    if people is None:
        people = _load_people(db, [UUID(identifier) for identifier in proposed["before_snapshot"]["people"]])
    for identifier, snapshot in proposed["before_snapshot"]["people"].items():
        person = people[UUID(identifier)]
        # 语种等目录名称只在本次留存时读取；以后查看历史不按新目录重写旧名称。
        for key in COLLECTIONS:
            for row in getattr(person, key):
                frozen_labels = {}
                for field in ("language_label", "source_language_label", "target_language_label", "display"):
                    if hasattr(type(row), field):
                        try:
                            frozen_labels[field] = getattr(row, field)
                        except AttributeError:
                            # 旧数据目录引用异常时保留原 ID，不伪造历史名称，也不修改原记录。
                            frozen_labels[field] = None
                labels[str(row.id)] = frozen_labels
        for attachment in snapshot.get("attachments", []):
            attachments.append({"person_id": identifier, **_preserve_file(attachment)})
    return {"format_version": 1, "policy": RETENTION_POLICY,
            "before_sha256": digest(proposed["before_snapshot"]), "catalog_labels": labels, "attachments": attachments}


def _operation(db, operation_id):
    require_ready(db)
    op = db.get(TalentDuplicateOperation, operation_id)
    if op is None:
        raise HTTPException(404, "核重操作不存在")
    retention = op.decisions.get("retention") or {}
    if retention.get("before_sha256") and retention["before_sha256"] != digest(op.before_snapshot):
        raise HTTPException(409, "原始资料快照校验失败，暂停读取与导出")
    if retention.get("after_sha256") and retention["after_sha256"] != digest(op.after_snapshot):
        raise HTTPException(409, "合并结果快照校验失败，暂停读取与导出")
    return op, retention


def _people(op):
    return [{"id": identifier, "name": row["person"].get("full_name"), "code": row["person"].get("resource_code"),
             "role": "原主档" if identifier == str(op.target_id) else "本次来源档案" if identifier in op.person_ids else "已有归档来源",
             "attachment_count": len(row.get("attachments", []))}
            for identifier, row in op.before_snapshot.get("people", {}).items()]


def _attachment_states(op, retention):
    if retention:
        return copy.deepcopy(retention.get("attachments", []))
    return [{"person_id": identifier, "attachment_id": row["id"], "original_name": row.get("original_name"),
             "state": "legacy_reference_only", "message": "旧操作只保存原附件记录，未制作独立文件副本"}
            for identifier, snapshot in op.before_snapshot.get("people", {}).items() for row in snapshot.get("attachments", [])]


def _external_references(op):
    return [{"person_id": identifier, "field": "resume_path", "value": row["person"]["resume_path"],
             "state": "reference_only", "message": "外部简历路径／链接仅保留原引用，未生成文件副本；链接可能过期或失效"}
            for identifier, row in op.before_snapshot.get("people", {}).items() if row["person"].get("resume_path")]


def original_data(db, operation_id, person_id=None):
    op, retention = _operation(db, operation_id)
    result = {"operation": operation_result(op), "policy": RETENTION_POLICY, "people": _people(op),
              "frozen_at": business_iso(op.created_at), "snapshot_sha256": digest(op.before_snapshot),
              "integrity_recorded": bool(retention.get("before_sha256")),
              "reference_counts": {table: len(rows) for table, rows in op.before_snapshot.get("references", {}).items()},
              "attachments": _attachment_states(op, retention), "external_references": _external_references(op)}
    if person_id is not None:
        identifier = str(person_id)
        snapshot = op.before_snapshot.get("people", {}).get(identifier)
        if snapshot is None:
            raise HTTPException(404, "此人员不在本次合并前快照中")
        fields = [{"key": key, "label": SYSTEM_LABELS.get(key, field_label(key)), "value": value}
                  for key, value in snapshot["person"].items()]
        for key in PROFILES:
            for field, value in (snapshot.get(key) or {}).items():
                if field not in SYSTEM_FIELDS:
                    fields.append({"key": key + "." + field, "label": field_label(key + "." + field), "value": value})
        for key in COLLECTIONS:
            values = [{**row, **retention.get("catalog_labels", {}).get(row["id"], {})} for row in snapshot.get(key, [])]
            fields.append({"key": key, "label": field_label(key), "value": values})
        result.update({"person_id": identifier, "fields": copy.deepcopy(fields), "snapshot": copy.deepcopy(snapshot)})
    return result


def export_original_data(db, operation_id):
    op, retention = _operation(db, operation_id)
    return {"format_version": 1, "operation": operation_result(op), "policy": RETENTION_POLICY,
            "snapshot_sha256": digest(op.before_snapshot), "integrity_recorded": bool(retention.get("before_sha256")),
            "before_snapshot": copy.deepcopy(op.before_snapshot), "after_snapshot": copy.deepcopy(op.after_snapshot),
            "field_decisions": copy.deepcopy(op.decisions.get("fields", {})),
            "merge_audit": copy.deepcopy(op.decisions.get("merge_audit")), "retention": copy.deepcopy(retention),
            "attachments": _attachment_states(op, retention), "external_references": _external_references(op)}


def original_attachment(db, operation_id, attachment_id):
    op, retention = _operation(db, operation_id)
    item = next((row for row in _attachment_states(op, retention) if row["attachment_id"] == str(attachment_id)), None)
    if item is None:
        raise HTTPException(404, "此附件不在本次留存资料中")
    if item["state"] != "archived":
        raise HTTPException(409, item["message"])
    path = _blob_path(item["sha256"])
    if not path.is_file():
        raise HTTPException(404, "留存附件副本缺失；原附件记录仍保留")
    if _hash_file(path) != item["sha256"]:
        raise HTTPException(409, "留存附件内容校验失败，暂停下载")
    return path, item


def ensure_attachment_retained(db, person_id, attachment_id):
    """新操作有独立副本可移除当前附件；旧记录无副本时禁止破坏其唯一原文件。"""
    if not review_ready(db):
        return
    query = db.query(TalentDuplicateOperation).filter(
        cast(TalentDuplicateOperation.before_snapshot["people"][str(person_id)]["attachments"], JSONB).contains([{"id": str(attachment_id)}])
    )
    for operation in query.all():
        original_attachment(db, operation.id, attachment_id)
