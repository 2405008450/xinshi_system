"""
暴力同步数据脚本 - 忽略外键约束强制更新数据
运行方式: python force_sync_data.py
"""
import psycopg2
import re
import os

DB_CONFIG = {
    'host': 'postgres',
    'port': 5432,
    'database': 'xinshi_system',
    'user': 'postgres',
    'password': '123456'
}

# 必须按顺序排列，先插 client (被引用者)，再插 project (引用者)
SQL_FILES = [
    '/app/client.sql',
    '/app/translation_project.sql',
    '/app/consultation.sql'
]

def force_sync():
    print("开始暴力数据同步...")
    
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()
 
    try:
        # 1. 第一步：强行清空旧数据及其所有依赖项 (CASCADE)
        # 注意：这会清空 workflow_instance 和 workflow_log，因为它们引用了这些表
        print("\n[1] 正在清空现有表及其关联数据 (CASCADE)...")
        cursor.execute("TRUNCATE TABLE client, translation_project, consultation RESTART IDENTITY CASCADE;")
        print("  - 数据已清空")

        # 2. 第二步：从 SQL 文件中提取并执行 INSERT 语句
        for filename in SQL_FILES:
            if not os.path.exists(filename):
                print(f"\n⚠️ 找不到文件: {filename}，跳过")
                continue
                
            print(f"\n[2] 正在处理 {filename}...")
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则匹配所有的 INSERT INTO 语句
            inserts = re.findall(r"INSERT INTO.*?;", content, re.DOTALL | re.IGNORECASE)
            
            if not inserts:
                print(f"  - 未在该文件中找到 INSERT 语句")
                continue
                
            print(f"  - 找到 {len(inserts)} 条插入语句，开始执行...")
            success_count = 0
            for sql in inserts:
                try:
                    cursor.execute(sql)
                    success_count += 1
                except Exception as e:
                    print(f"  - 其中一条执行出错: {e}")
            
            print(f"  - {filename} 同步完成，成功执行 {success_count} 条。")

    except Exception as e:
        print(f"\n❌ 同步过程中发生严重错误: {e}")
    finally:
        cursor.close()
        conn.close()

    print("\n✓ 数据同步任务结束。请重启后端服务以确保数据读取正常。")

if __name__ == "__main__":
    force_sync()
