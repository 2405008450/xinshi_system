"""
数据库迁移脚本 - 创建 Consultation 表和 Client 英文名字段
使用方法: python db_migrate_consultation.py
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'xinshi_system',
    'user': 'postgres',
    'password': '123456'
}

def get_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def migrate():
    conn = get_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    print("开始数据库迁移...")

    # 1. 为 Client 表添加英文名字段
    print("\n[1/3] 检查并添加 client 表的 english_name 字段...")
    try:
        cursor.execute("""
            ALTER TABLE client
            ADD COLUMN IF NOT EXISTS english_name VARCHAR(255);
        """)
        print("  - english_name 字段已添加")
    except Exception as e:
        print(f"  - english_name 字段添加失败: {e}")

    try:
        cursor.execute("""
            ALTER TABLE client
            ADD COLUMN IF NOT EXISTS english_short_name VARCHAR(100);
        """)
        print("  - english_short_name 字段已添加")
    except Exception as e:
        print(f"  - english_short_name 字段添加失败: {e}")

    # 2. 创建 Consultation 表
    print("\n[2/3] 创建 consultation 表...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consultation (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                consultation_code VARCHAR(50) NOT NULL UNIQUE,
                client_id UUID,
                consultation_time TIMESTAMP,
                consultation_method VARCHAR(50),
                client_source VARCHAR(100),
                source_keyword VARCHAR(255),
                consultation_description TEXT,
                remarks TEXT,
                customer_service_id UUID,
                sales_person_id UUID,
                status VARCHAR(20) DEFAULT 'pending',
                consultation_type VARCHAR(50),
                handling_method VARCHAR(100),
                editor_id UUID,
                follow_up_count INTEGER DEFAULT 0,
                follow_up_time TIMESTAMP,
                follow_up_status VARCHAR(20),
                follow_up_remarks TEXT,
                follow_up_person_id UUID,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_consultation_client FOREIGN KEY (client_id)
                    REFERENCES client(id) ON DELETE SET NULL,
                CONSTRAINT fk_consultation_customer_service FOREIGN KEY (customer_service_id)
                    REFERENCES app_user(id) ON DELETE SET NULL,
                CONSTRAINT fk_consultation_sales_person FOREIGN KEY (sales_person_id)
                    REFERENCES app_user(id) ON DELETE SET NULL,
                CONSTRAINT fk_consultation_editor FOREIGN KEY (editor_id)
                    REFERENCES app_user(id) ON DELETE SET NULL,
                CONSTRAINT fk_consultation_follow_up_person FOREIGN KEY (follow_up_person_id)
                    REFERENCES app_user(id) ON DELETE SET NULL
            );
        """)
        print("  - consultation 表已创建")
    except Exception as e:
        print(f"  - consultation 表创建失败: {e}")

    # 3. 创建索引
    print("\n[3/3] 创建索引...")
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_consultation_client_id
            ON consultation(client_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_consultation_consultation_code
            ON consultation(consultation_code);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_consultation_status
            ON consultation(status);
        """)
        print("  - 索引已创建")
    except Exception as e:
        print(f"  - 索引创建失败: {e}")

    cursor.close()
    conn.close()

    print("\n✓ 数据库迁移完成!")
    print("\n迁移内容:")
    print("  1. client 表新增字段: english_name, english_short_name")
    print("  2. 新建 consultation 表，包含完整的咨询功能字段")

if __name__ == "__main__":
    migrate()
