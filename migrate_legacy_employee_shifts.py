"""把 work_schedule.shift_table 转换为员工单日班次覆盖。

默认只输出预览；确认报告后使用：
    python migrate_legacy_employee_shifts.py --commit
脚本不会覆盖 employee_shift_override 中已经存在的记录。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, time

from sqlalchemy import text

from database import engine


PERSON_COLUMNS = ("layoutIt", "client", "hr", "translationProject")
PRESET_TIMES = {
    (time(8, 30), time(18, 0)): "early_early",
    (time(9, 0), time(18, 30)): "early",
    (time(10, 30), time(20, 0)): "late",
    (time(13, 30), time(21, 30)): "late_late",
}


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def split_names(value) -> list[str]:
    return [part.strip() for part in re.split(r"[、，,；;\/]+", str(value or "")) if part.strip()]


def parse_shift(value: str, schedule_day: date):
    match = re.search(r"(\d{1,2}):?(\d{2})\s*[~～\-—至]\s*(\d{1,2}):?(\d{2})", str(value or ""))
    if not match:
        return None
    start_value = time(int(match.group(1)), int(match.group(2)))
    end_value = time(int(match.group(3)), int(match.group(4)))
    if end_value <= start_value:
        return None
    if schedule_day.isoweekday() in (6, 7) and (start_value, end_value) == (time(9, 30), time(18, 0)):
        code = "weekend_duty"
    else:
        code = PRESET_TIMES.get((start_value, end_value), "custom")
    return code, start_value, end_value


def run(commit: bool):
    connection_context = engine.begin() if commit else engine.connect()
    with connection_context as connection:
        users = connection.execute(text("SELECT id, username, full_name FROM app_user")).mappings().all()
        user_map = defaultdict(list)
        for user in users:
            for candidate in {user["username"], user["full_name"]}:
                if candidate:
                    user_map[normalize_name(candidate)].append(user)
        schedules = connection.execute(text(
            "SELECT schedule_date, shift_table FROM work_schedule "
            "WHERE jsonb_typeof(shift_table) = 'array' AND jsonb_array_length(shift_table) > 0 "
            "ORDER BY schedule_date"
        )).mappings().all()

        report = {"mode": "commit" if commit else "dry-run", "candidates": 0, "inserted": 0, "unmatched": [], "ambiguous": [], "invalid_shifts": []}
        seen = set()
        for schedule in schedules:
            schedule_day = schedule["schedule_date"]
            for shift_row in schedule["shift_table"] or []:
                parsed = parse_shift(shift_row.get("shift", ""), schedule_day)
                if not parsed:
                    report["invalid_shifts"].append({"date": schedule_day.isoformat(), "shift": shift_row.get("shift", "")})
                    continue
                shift_code, start_value, end_value = parsed
                for column in PERSON_COLUMNS:
                    for raw_name in split_names(shift_row.get(column)):
                        matches = user_map.get(normalize_name(raw_name), [])
                        if not matches:
                            report["unmatched"].append({"date": schedule_day.isoformat(), "name": raw_name})
                            continue
                        unique_matches = {str(item["id"]): item for item in matches}
                        if len(unique_matches) != 1:
                            report["ambiguous"].append({"date": schedule_day.isoformat(), "name": raw_name})
                            continue
                        user = next(iter(unique_matches.values()))
                        key = (str(user["id"]), schedule_day)
                        if key in seen:
                            continue
                        seen.add(key)
                        report["candidates"] += 1
                        if commit:
                            result = connection.execute(text("""
                                INSERT INTO employee_shift_override (
                                    user_id, schedule_date, shift_code, start_time, end_time, note
                                ) VALUES (
                                    :user_id, :schedule_date, :shift_code, :start_time, :end_time, :note
                                )
                                ON CONFLICT (user_id, schedule_date) DO NOTHING
                            """), {
                                "user_id": user["id"], "schedule_date": schedule_day,
                                "shift_code": shift_code, "start_time": start_value, "end_time": end_value,
                                "note": "由旧版 shift_table 转换",
                            })
                            report["inserted"] += result.rowcount
        for key in ("unmatched", "ambiguous", "invalid_shifts"):
            report[key] = report[key][:200]
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="转换旧版员工班次 JSON")
    parser.add_argument("--commit", action="store_true", help="确认后写入；不传则仅预览")
    run(parser.parse_args().commit)
