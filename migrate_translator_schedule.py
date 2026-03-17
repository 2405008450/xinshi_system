"""
迁移脚本：新增 translator_schedule 表
运行方式：python migrate_translator_schedule.py
"""
from database import engine
from sqlalchemy import text


def migrate():
    ddl = """
    CREATE TABLE IF NOT EXISTS translator_schedule (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        translator_id UUID NOT NULL REFERENCES translator(id) ON DELETE CASCADE,
        schedule_date DATE NOT NULL,
        available_time_slot VARCHAR(100),
        remaining_capacity INTEGER,
        source_type VARCHAR(30) DEFAULT 'manual',
        source_ref VARCHAR(100),
        last_confirmed_at TIMESTAMP,
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_translator_schedule_date UNIQUE (translator_id, schedule_date)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print("Migration completed: translator_schedule table created.")


if __name__ == "__main__":
    migrate()
