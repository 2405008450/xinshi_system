"""仅创建外勤记录表及其索引、约束。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target

TABLE = "attendance_field_work"


def apply_migration(connection):
    from field_work import FieldWork

    FieldWork.__table__.create(connection, checkfirst=True)


def run():
    from sqlalchemy import inspect, text

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-target", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    engine = verify_target(args)
    with engine.begin() as connection:
        print(f"{TABLE}_before={inspect(connection).has_table(TABLE)}")
        if args.check_only:
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    with engine.connect() as connection:
        print(f"{TABLE}_ready={inspect(connection).has_table(TABLE)}")


if __name__ == "__main__":
    run()
