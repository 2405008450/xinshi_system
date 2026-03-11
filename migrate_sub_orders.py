"""
迁移脚本：同步 translation_sub_order 表字段与 translation_project 对齐

新增字段：
  - file_type_secondary  : VARCHAR(100)
  - priority             : VARCHAR(50)
  - customer_deadline_time : TIMESTAMP
  - sent_to_client_time  : TIMESTAMP
  - client_feedback      : TEXT
  - expected_translator_stats_method : VARCHAR(100)
  - expected_translator_word_count   : BIGINT
  - pre_review_qc_progress : VARCHAR(20)
  - review1_progress     : VARCHAR(20)
  - review2_progress     : VARCHAR(20)
  - post_review_qc_progress : VARCHAR(20)
  - consolidation_progress : VARCHAR(20)
  - created_by           : UUID（外键 -> app_user.id）

同时将旧字段 review_progress 保留（若已有数据不做删除）
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db, engine
from sqlalchemy import text

ALTER_STATEMENTS = [
    # 文件/优先级
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS file_type_secondary VARCHAR(100);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS priority VARCHAR(50);",

    # 时间节点
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS customer_deadline_time TIMESTAMP;",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS sent_to_client_time TIMESTAMP;",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS client_feedback TEXT;",

    # 译员扩展
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS expected_translator_stats_method VARCHAR(100);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS expected_translator_word_count BIGINT;",

    # 进度字段（与母订单对齐，旧 review_progress 保留不删）
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS pre_review_qc_progress VARCHAR(20);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS review1_progress VARCHAR(20);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS review2_progress VARCHAR(20);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS post_review_qc_progress VARCHAR(20);",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS consolidation_progress VARCHAR(20);",

    # 创建人（外键）
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS created_by UUID;",
    """DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_sub_order_creator'
    ) THEN
        ALTER TABLE translation_sub_order
            ADD CONSTRAINT fk_sub_order_creator
            FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;
END $$;""",
]


def run_migration():
    print("🚀 开始执行子订单表迁移...")
    with engine.connect() as conn:
        for stmt in ALTER_STATEMENTS:
            try:
                conn.execute(text(stmt))
                conn.commit()
                # 打印前 60 个字符作摘要
                print(f"  ✅ {stmt[:60].strip()}...")
            except Exception as e:
                print(f"  ⚠️  执行失败（可忽略已存在错误）: {e}")
    print("✅ 迁移完成！")


if __name__ == "__main__":
    run_migration()
