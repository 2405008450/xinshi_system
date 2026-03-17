"""
数据迁移脚本：将已知译员的可用性/产能/领域能力数据按新字段结构更新
运行方式：python migrate_translator_data.py
"""
import json
from datetime import datetime
from database import engine
from sqlalchemy import text


TRANSLATOR_DATA = [
    {
        "name": "高超",
        "status": "active",
        "available_time_slot": "全天",
        "daily_accept_count": 5,
        "hourly_speed": 1000,
        "daily_word_capacity": 8000,
        "can_cloud_edit": True,
        "can_revision": True,
        "domain_skills": [
            {"domain": "银行", "level": "擅长"},
            {"domain": "法律", "level": "需审改"},
        ],
        "default_priority": 1,
        "remarks": "大概仅适合银行。法律类需审改。其他中英要求不是很高的可基本检查，少量、要求不高的（如鲲鹏洛素）可直接给客户专员",
    },
    {
        "name": "王婷",
        "status": "active",
        "available_time_slot": "中午12点后",
        "daily_accept_count": 5,
        "hourly_speed": 1000,
        "daily_word_capacity": 8000,
        "can_cloud_edit": None,
        "can_revision": None,
        "domain_skills": [
            {"domain": "法律", "level": "需审改"},
        ],
        "default_priority": 2,
        "remarks": "法律类需审改，其他中英要求不是很高的可以基本检查，少量的可直接给客户专员",
    },
    {
        "name": "王邃玲",
        "status": "active",
        "available_time_slot": "傍晚5点后",
        "daily_accept_count": 5,
        "hourly_speed": 1000,
        "daily_word_capacity": 6000,
        "can_cloud_edit": True,
        "can_revision": True,
        "domain_skills": [
            {"domain": "法律", "level": "需审改"},
        ],
        "default_priority": 3,
        "remarks": "法律类需安排审改。",
    },
]


def migrate():
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        for t in TRANSLATOR_DATA:
            result = conn.execute(
                text("SELECT id FROM translator WHERE translator_name = :name"),
                {"name": t["name"]},
            )
            row = result.fetchone()
            if row:
                conn.execute(
                    text("""
                        UPDATE translator SET
                            status = :status,
                            available_time_slot = :available_time_slot,
                            daily_accept_count = :daily_accept_count,
                            hourly_speed = :hourly_speed,
                            daily_word_capacity = :daily_word_capacity,
                            can_cloud_edit = :can_cloud_edit,
                            can_revision = :can_revision,
                            domain_skills = :domain_skills,
                            default_priority = :default_priority,
                            remarks = :remarks,
                            availability_updated_at = :now
                        WHERE translator_name = :name
                    """),
                    {
                        "name": t["name"],
                        "status": t["status"],
                        "available_time_slot": t["available_time_slot"],
                        "daily_accept_count": t["daily_accept_count"],
                        "hourly_speed": t["hourly_speed"],
                        "daily_word_capacity": t["daily_word_capacity"],
                        "can_cloud_edit": t["can_cloud_edit"],
                        "can_revision": t["can_revision"],
                        "domain_skills": json.dumps(t["domain_skills"], ensure_ascii=False),
                        "default_priority": t["default_priority"],
                        "remarks": t["remarks"],
                        "now": now,
                    },
                )
                print(f"Updated: {t['name']}")
            else:
                print(f"Skipped (not found): {t['name']}")

    print("Data migration completed.")


if __name__ == "__main__":
    migrate()
