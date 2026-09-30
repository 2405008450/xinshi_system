"""显式迁移人才操作溯源字段，不回填无法确认的历史操作。"""

from sqlalchemy import text

from tools.run_runtime_migrations import require_local_migration_environment


def migrate(engine):
    with engine.begin() as connection:
        connection.execute(text("""
            ALTER TABLE resource_person
                ADD COLUMN IF NOT EXISTS operated_by UUID,
                ADD COLUMN IF NOT EXISTS operator_name VARCHAR(255),
                ADD COLUMN IF NOT EXISTS operated_at TIMESTAMP WITHOUT TIME ZONE
        """))


def main():
    require_local_migration_environment()
    from database import engine

    migrate(engine)
    print("人才操作溯源字段迁移完成")


if __name__ == "__main__":
    main()
