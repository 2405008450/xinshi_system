"""按已核对的全表预览补齐开拓进度；默认试跑回滚。"""

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(r"E:\Documents\william代码\管理系统资源\10.26资源开拓统筹.xlsx")
PREVIEW = Path(r"E:\Documents\resource_development_20261028_full_alignment_preview.json")
SOURCE_SHA = "0531706e507e68822f4ee632874db449349f56d122f246cc52dfefbc7b7ae471"
ORIGINAL_BATCH = "resource-development-20261026-03f023c9d650"
BATCH = "resource-development-progress-backfill-20261028-" + SOURCE_SHA[:12]
STATUS_FIELDS = ("已加微信", "已加企微", "已邀进群", "已沟通", "已入项")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system")
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA, "原表已经变化"
    preview = json.loads(PREVIEW.read_text(encoding="utf-8"))
    assert preview["source_sha256"] == SOURCE_SHA and len(preview["rows"]) == 2924
    assert preview["summary"]["structured_candidate_needs_review"] == 5
    assert preview["summary"]["leave_blank_but_existing_action_needs_review"] == 3
    assert preview["summary"]["followup_followup_candidate_needs_review"] == 1

    import main as app_models  # noqa: F401 加载所有 ORM 映射
    from sqlalchemy import text
    from database import SessionLocal, engine
    from models import AppUser
    from resource_development_import_preview import OWNER_ALIASES, source_values
    from resource_development_models import DevelopmentAction as Action, DevelopmentAudit as Audit
    from resource_development_models import DevelopmentFollowUp as FollowUp, DevelopmentRecord as Record
    from resource_development_service import lock_writes, progress_status, refresh_draft, snapshot
    from business_time import business_now, business_iso
    from import_resource_development_20261026 import backup

    assert (engine.url.host, engine.url.port, engine.url.database) == ("43.132.156.72", 15432, "xinshi_system")
    with engine.connect() as connection:
        assert connection.execute(text("select current_database()")).scalar_one() == "xinshi_system"
    backup_manifest = None
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir(), "提交前必须提供空备份目录"
        backup_manifest = backup(engine, args.backup_dir, BATCH)

    report = {"batch": BATCH, "apply": args.apply, "source_sha256": SOURCE_SHA,
              "started_at": business_iso(business_now()), "backup": str(args.backup_dir) if args.apply else None,
              "backup_tables": len(backup_manifest["tables"]) if backup_manifest else 0,
              "counts": Counter(), "changes": []}
    with SessionLocal() as db:
        lock_writes(db)
        users = db.query(AppUser).all()
        by_name = {user.full_name or user.username: user for user in users}
        by_name.update({short: by_name[full] for short, full in OWNER_ALIASES.items() if full in by_name})
        actor = next(user for user in users if user.username == "zhengran" and user.is_active)
        now = business_now()
        touched_owner_days = set()
        touched_records = set()

        for source in preview["rows"]:
            flagged = [(field, source["status_columns"][field]) for field in STATUS_FIELDS
                       if source["status_columns"][field]["handling"] in {
                           "structured_candidate_needs_review", "leave_blank_but_existing_action_needs_review"}]
            follow = source["followup"]
            if not flagged and follow["handling"] != "followup_candidate_needs_review":
                continue
            row_number = source["source_row"]
            record_id = UUID(source["mapped_record"]["record_id"])
            record = db.get(Record, record_id)
            assert record and record.historical_only, f"第 {row_number} 行记录不能安全修改"
            assert record.full_name.strip().casefold() == source["original"]["姓名"].strip().casefold()
            original = source_values(record)
            assert original and original["姓名"] == source["original"]["姓名"], f"第 {row_number} 行原文未保留"
            for field, item in flagged:
                if item["handling"] == "leave_blank_but_existing_action_needs_review":
                    assert item["original"] in (record.remarks or ""), f"第 {row_number} 行撤回操作的原文未保留"
            touched = False
            changed_channels = set()
            record_before = snapshot(record)

            for field, item in flagged:
                channel = item["target_channel"]
                raw = item["original"]
                assert raw
                if item["handling"] == "structured_candidate_needs_review":
                    operator = by_name.get(item["proposed_operator"])
                    assert operator, f"第 {row_number} 行操作人不存在"
                    action_day = date.fromisoformat(item["proposed_action_date"])
                    assert action_day <= date(2026, 10, 26)
                    existing = db.query(Action).filter_by(record_id=record.id, channel=channel,
                        status=item["proposed_status"], action_date=action_day, operator_id=operator.id).first()
                    if existing:
                        report["counts"]["actions_already_present"] += 1
                        continue
                    action_id = uuid5(NAMESPACE_URL, f"{BATCH}:action:{record.id}:{field}:{raw}")
                    assert db.get(Action, action_id) is None, "确定性操作 ID 冲突"
                    action = Action(id=action_id, record_id=record.id, channel=channel,
                        status=item["proposed_status"], request_number=0, action_date=action_day,
                        operator_id=operator.id, account_id=record.account_id,
                        created_by=actor.id, updated_by=actor.id, created_at=now, updated_at=now)
                    db.add(action)
                    db.flush()
                    db.add(Audit(entity_id=action.id, entity_type="action", actor_id=actor.id,
                                 action="create", before={}, after=snapshot(action), created_at=now))
                    report["counts"]["actions_created"] += 1
                    report["changes"].append({"source_row": row_number, "field": field,
                                               "operation": "create_action", "id": str(action.id), "raw": raw})
                    touched = True
                    changed_channels.add(channel)
                else:
                    # 只撤回可用原始导入批次和原文同时证明来源的误解析操作。
                    action_id = uuid5(NAMESPACE_URL, f"{ORIGINAL_BATCH}:action:{record.id}:{field}:{raw}")
                    action = db.get(Action, action_id)
                    if action is None:
                        report["counts"]["incorrect_actions_already_absent"] += 1
                        continue
                    assert action.record_id == record.id and action.channel == channel
                    assert action.status == "已添加" and action.action_date == date.fromisoformat(item["proposed_action_date"])
                    operator = by_name.get(item["proposed_operator"])
                    assert operator and action.operator_id == operator.id
                    before = snapshot(action)
                    db.delete(action)
                    db.flush()
                    db.add(Audit(entity_id=action_id, entity_type="action", actor_id=actor.id,
                                 action="delete", before=before, after={}, created_at=now))
                    report["counts"]["incorrect_actions_removed"] += 1
                    report["changes"].append({"source_row": row_number, "field": field,
                                               "operation": "remove_incorrect_action", "id": str(action_id), "raw": raw})
                    touched = True
                    changed_channels.add(channel)

            if follow["handling"] == "followup_candidate_needs_review":
                raw = follow["original"]
                content = f"【10.26统筹表第{row_number}行】{raw}"
                follow_id = uuid5(NAMESPACE_URL, f"{ORIGINAL_BATCH}:follow:{record.id}:{row_number}:{raw}")
                existing = db.query(FollowUp).filter_by(record_id=record.id, content=content).first()
                if existing:
                    report["counts"]["followups_already_present"] += 1
                else:
                    assert db.get(FollowUp, follow_id) is None, "确定性跟进 ID 冲突"
                    followup = FollowUp(id=follow_id, record_id=record.id, content=content,
                                        operator_id=actor.id, created_at=now)
                    db.add(followup)
                    db.flush()
                    db.add(Audit(entity_id=followup.id, entity_type="follow_up", actor_id=actor.id,
                                 action="create", before={}, after=snapshot(followup), created_at=now))
                    report["counts"]["followups_created"] += 1
                    report["changes"].append({"source_row": row_number, "field": "后续跟进情况",
                                               "operation": "create_followup", "id": str(followup.id), "raw": raw})
                    touched = True

            if touched:
                for channel, field in (("wechat", "wechat_status"), ("enterprise", "enterprise_status")):
                    if channel not in changed_channels:
                        continue
                    actions = db.query(Action).filter_by(record_id=record.id, channel=channel).order_by(Action.created_at, Action.id).all()
                    # 新补的历史操作早于已录入的后续操作时，不覆盖当前展示状态。
                    latest_day = max((action.action_date for action in actions), default=None)
                    imported_days = [date.fromisoformat(item["proposed_action_date"])
                                     for _, item in flagged if item["target_channel"] == channel]
                    if latest_day and imported_days and latest_day > max(imported_days):
                        continue
                    status = (record.historical_markers or {}).get(channel, {}).get("status", "未处理")
                    for action in actions:
                        status = progress_status(action.status, channel)
                    setattr(record, field, status)
                record.updated_by = actor.id
                record.updated_at = now
                record.revision += 1
                db.flush()
                db.add(Audit(entity_id=record.id, entity_type="record", actor_id=actor.id,
                             action="update", before=record_before, after=snapshot(record), created_at=now))
                touched_owner_days.add((record.owner_id, record.work_date))
                touched_records.add(record.id)

        for owner_id, work_date in touched_owner_days:
            refresh_draft(db, owner_id, work_date)
        db.flush()
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA, "原表在执行期间变化"
        report["counts"]["touched_records"] = len(touched_records)
        report["counts"]["touched_owner_days"] = len(touched_owner_days)
        report["finished_at"] = business_iso(business_now())
        if args.apply:
            db.commit()
        else:
            db.rollback()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "counts": report["counts"], "report": str(args.report),
                      "backup": report["backup"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
