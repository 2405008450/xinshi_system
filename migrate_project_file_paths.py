"""
迁移脚本：为 project_file 表新增 3 个路径字段

新增字段：
  - dispatch_path          : TEXT  派稿文路径
  - translation_path       : TEXT  译文路径
  - client_delivery_path   : TEXT  发客户路径

原 storage_path 字段保留，前端显示名改为"原文路径"。
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

ALTER_STATEMENTS = [
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS dispatch_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS translation_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS client_delivery_path TEXT",
]

def run():
    with engine.begin() as conn:
        for stmt in ALTER_STATEMENTS:
            print(f"执行: {stmt}")
            conn.execute(text(stmt))
    print("迁移完成！")

if __name__ == "__main__":
    run()
