"""把切换日及未来排班 JSON 中的非项目任务迁移为结构化任务。

默认只预览；确认异常清单后使用：
    python migrate_schedule_non_project_tasks.py --cutover-date 2026-07-28 --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date

from sqlalchemy.orm import Session

from database import engine
from models import AppUser, WorkSchedule
from task_models import NonProjectTask
from task_service import business_now


MIGRATABLE_CATEGORIES = {"非直接项目任务", "固定任务", "其他"}


def source_key(schedule_date: date, user_id, category: str, content: str, index: int) -> str:
    raw = f"{schedule_date}|{user_id}|{category}|{content}|{index}"
    return "schedule:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def build_user_index(users: list[AppUser]) -> dict[str, list[AppUser]]:
    index: dict[str, list[AppUser]] = {}
    for user in users:
        for name in {user.username.strip(), (user.full_name or "").strip()} - {""}:
            index.setdefault(name, []).append(user)
    return index


def run(cutover_date: date, apply_changes: bool) -> dict:
    result = {"created": 0, "skipped_existing": 0, "exceptions": []}
    with Session(engine) as db:
        users = db.query(AppUser).filter(AppUser.is_active == True).all()
        user_index = build_user_index(users)
        schedules = (
            db.query(WorkSchedule)
            .filter(WorkSchedule.schedule_date >= cutover_date)
            .order_by(WorkSchedule.schedule_date)
            .all()
        )
        for schedule in schedules:
            assigner_id = schedule.updated_by
            for person in schedule.dept_person_data or []:
                name = str(person.get("name") or "").strip()
                matches = user_index.get(name, [])
                if len(matches) != 1:
                    result["exceptions"].append(
                        {
                            "schedule_date": str(schedule.schedule_date),
                            "name": name,
                            "reason": "未找到唯一用户",
                        }
                    )
                    continue
                assignee = matches[0]
                effective_assigner = (
                    assigner_id
                    if assigner_id and db.query(AppUser.id).filter(AppUser.id == assigner_id).first()
                    else assignee.id
                )
                candidates = []
                for item in person.get("tasks") or []:
                    category = str(item.get("category") or "").strip()
                    if category in MIGRATABLE_CATEGORIES:
                        candidates.append(
                            (
                                category,
                                str(item.get("content") or "").strip(),
                                {
                                    "deadline": item.get("deadline"),
                                    "projectNo": item.get("projectNo"),
                                },
                            )
                        )
                candidates.extend(
                    ("固定任务", str(content).strip(), {})
                    for content in (person.get("fixedTasks") or [])
                )
                for index, (category, content, metadata) in enumerate(candidates):
                    if not content:
                        continue
                    key = source_key(
                        schedule.schedule_date, assignee.id, category, content, index
                    )
                    if db.query(NonProjectTask.id).filter(NonProjectTask.source_key == key).first():
                        result["skipped_existing"] += 1
                        continue
                    remark_parts = [
                        f"{label}：{value}"
                        for label, value in (
                            ("原截止说明", metadata.get("deadline")),
                            ("原项目编号", metadata.get("projectNo")),
                        )
                        if value
                    ]
                    now = business_now()
                    db.add(
                        NonProjectTask(
                            task_type=category,
                            task_name=content,
                            assigner_id=effective_assigner,
                            assignee_id=assignee.id,
                            assigned_at=now,
                            status="pending",
                            remark="；".join(remark_parts) or None,
                            occurrence_date=schedule.schedule_date,
                            source_key=key,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    result["created"] += 1
        if apply_changes:
            db.commit()
        else:
            db.rollback()
    result["mode"] = "applied" if apply_changes else "preview"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移排班中的非项目任务")
    parser.add_argument(
        "--cutover-date",
        type=date.fromisoformat,
        default=date.today(),
        help="迁移该日期及之后的数据，格式 YYYY-MM-DD",
    )
    parser.add_argument("--apply", action="store_true", help="实际写入；不指定时仅预览")
    args = parser.parse_args()
    print(json.dumps(run(args.cutover_date, args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
