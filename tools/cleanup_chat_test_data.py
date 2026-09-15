# -*- coding: utf-8 -*-
"""清理聊天小窗验收期间写入共享库的测试数据（两个项目 + 相关通知/提及）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

env = {}
for line in open(".env", encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

url = f"postgresql+psycopg2://{env['DB_USER']}:{quote_plus(env['DB_PASSWORD'])}@{env['DB_HOST']}:{env['DB_PORT']}/{env['DB_NAME']}"
eng = create_engine(url)

AP_ID = "86cc568e-dc3c-41e7-a125-976c21fc8855"
TP_ID = "30540abb-4476-4887-a012-ca734637629f"
TEST_DATE = "2026-09-15"

with eng.begin() as c:
    msgs = c.execute(
        text(
            """
            SELECT id, sender_name, left(content, 30), created_at
            FROM chat_project_message
            WHERE (annotation_project_id = :ap OR project_id = :tp)
              AND created_at::date = :d
            ORDER BY created_at
            """
        ),
        {"ap": AP_ID, "tp": TP_ID, "d": TEST_DATE},
    ).fetchall()
    print("messages to delete:", len(msgs))
    for m in msgs[:5]:
        print("  sample:", m[1], "|", m[2])
    older = c.execute(
        text(
            """
            SELECT count(*) FROM chat_project_message
            WHERE (annotation_project_id = :ap OR project_id = :tp)
              AND created_at::date < :d
            """
        ),
        {"ap": AP_ID, "tp": TP_ID, "d": TEST_DATE},
    ).scalar()
    print("older messages kept:", older)

    ids = [str(m[0]) for m in msgs]
    if not ids:
        print("nothing to do")
        sys.exit(0)

    del_mentions = c.execute(
        text("DELETE FROM chat_project_mention WHERE message_id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": ids},
    ).rowcount
    del_msgs = c.execute(
        text("DELETE FROM chat_project_message WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": ids},
    ).rowcount

    notifs = c.execute(
        text(
            """
            DELETE FROM app_notification
            WHERE notification_type IN ('project_chat', 'project_chat_mention', 'annotation_project_chat_mention')
              AND created_at::date = :d
              AND (related_entity_id::text IN (:ap, :tp) OR related_project_id::text IN (:ap, :tp))
            """
        ),
        {"ap": AP_ID, "tp": TP_ID, "d": TEST_DATE},
    ).rowcount

    # 恢复笔译项目沟通开关为关闭
    c.execute(
        text("UPDATE chat_project_enabled SET enabled = false WHERE project_id = :tp"),
        {"tp": TP_ID},
    )

    print(f"deleted mentions={del_mentions} messages={del_msgs} notifications={notifs}")
