"""Alter app_user and translator tables to add schedule-related columns."""
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # app_user: add department, fixed_tasks
    conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS department VARCHAR(50)"))
    conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS fixed_tasks JSONB DEFAULT '[]'::jsonb"))
    # translator: add 7 new fields
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS translation_type VARCHAR(255)"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS quality_score VARCHAR(10)"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS cloud_revision VARCHAR(50)"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS daily_rate VARCHAR(100)"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS direction VARCHAR(20)"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS default_priority INTEGER DEFAULT 0"))
    conn.execute(text("ALTER TABLE translator ADD COLUMN IF NOT EXISTS schedule_remarks TEXT"))
    conn.commit()
    print("All columns added successfully")
