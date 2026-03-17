"""
迁移脚本：为 translator 表新增可用性/产能/领域能力相关字段
运行方式：python migrate_translator_availability.py
"""
from database import engine
from sqlalchemy import text


def migrate():
    ddl = """
    ALTER TABLE translator
        ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'standby',
        ADD COLUMN IF NOT EXISTS available_time_slot VARCHAR(100),
        ADD COLUMN IF NOT EXISTS daily_accept_count INTEGER,
        ADD COLUMN IF NOT EXISTS hourly_speed INTEGER,
        ADD COLUMN IF NOT EXISTS daily_word_capacity INTEGER,
        ADD COLUMN IF NOT EXISTS can_cloud_edit BOOLEAN,
        ADD COLUMN IF NOT EXISTS can_revision BOOLEAN,
        ADD COLUMN IF NOT EXISTS domain_skills JSONB DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS availability_updated_at TIMESTAMP;
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print("Migration completed: translator availability fields added.")


if __name__ == "__main__":
    migrate()
