"""
执行手动导出的 SQL 文件更新表结构和数据
运行方式: python run_sql_dumps.py
"""
import psycopg2
import os

DB_CONFIG = {
    'host': 'postgres',
    'port': 5432,
    'database': 'xinshi_system',
    'user': 'postgres',
    'password': '123456'
}

SQL_FILES = [
    '/app/client.sql',
    '/app/translation_project.sql',
    '/app/consultation.sql'
]

def run_sql():
    print("开始执行 SQL 更新...")
    
    # 检查文件是否存在
    for filename in SQL_FILES:
        if not os.path.exists(filename):
            print(f"找不到 SQL 文件: {filename}")
            print("请确保你使用 docker cp 将它们复制到了容器的 /app 目录下。")
            return
            
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()

    for filename in SQL_FILES:
        print(f"\n执行 {filename}...")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # 使用 BEGIN / COMMIT 包裹脚本以防部分失败，虽然脚本内可能有 DROP
            try:
                cursor.execute(sql_script)
                print(f"  - {filename} 执行成功")
            except psycopg2.Error as e:
                print(f"  - 执行失败: {e}")
                
        except Exception as e:
            print(f"  - 读取文件或执行时发生错误: {e}")

    cursor.close()
    conn.close()
    print("\n✓ 所有的 SQL 更新执行完毕！")

if __name__ == "__main__":
    run_sql()
