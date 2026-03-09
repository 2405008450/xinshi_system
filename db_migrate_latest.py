"""
数据库迁移脚本 - 同步本地新增的表和字段到云服务器
运行方式: python db_migrate_latest.py
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 数据库配置
DB_CONFIG = {
    'host': 'postgres', # 由于脚本将在包含数据库的服务器内运行或可直接连通，先用 localhost，如果不行换成 'postgres' (docker compose service name)
    'port': 5432,
    'database': 'xinshi_system',
    'user': 'postgres',
    'password': '123456'
}

def migrate():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    print("开始数据库最新变更的迁移...")

    # 1. client 表的 english_name 和 english_short_name (在之前的 db_migrate_consultation.py 里已经有了，但安全起见加上 IF NOT EXISTS)
    print("\n[1] 检查并添加 client 表的新字段...")
    fields_to_add = [
        ("client", "english_name", "VARCHAR(255)"),
        ("client", "english_short_name", "VARCHAR(100)"),
    ]
    for table, col, type_ in fields_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {type_};")
            print(f"  - {table}.{col} 字段已就绪")
        except Exception as e:
            print(f"  - {table}.{col} 添加失败: {e}")

    # 2. app_user 表的 department 和 fixed_tasks
    print("\n[2] 检查并添加 app_user 表的新字段...")
    fields_to_add = [
        ("app_user", "department", "VARCHAR"),
        ("app_user", "fixed_tasks", "JSONB DEFAULT '[]'::jsonb"),
    ]
    for table, col, type_ in fields_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {type_};")
            print(f"  - {table}.{col} 字段已就绪")
        except Exception as e:
            print(f"  - {table}.{col} 添加失败: {e}")

    # 3. translation_project 表的 language_pair, priority, word_count
    print("\n[3] 检查并添加 translation_project 表的新字段...")
    fields_to_add = [
        ("translation_project", "language_pair", "VARCHAR"),
        ("translation_project", "priority", "VARCHAR"),
        ("translation_project", "word_count", "BIGINT"),
    ]
    for table, col, type_ in fields_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {type_};")
            print(f"  - {table}.{col} 字段已就绪")
        except Exception as e:
            print(f"  - {table}.{col} 添加失败: {e}")

    # 4. 创建 consultation 表
    print("\n[4] 检查并创建 consultation 表...")
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
        print("  - consultation 表已就绪")
        
        # 顺便创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consultation_client_id ON consultation(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consultation_consultation_code ON consultation(consultation_code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consultation_status ON consultation(status);")
    except Exception as e:
        print(f"  - consultation 表创建失败: {e}")

    # 5. 对于 translator 等可能新增的其他字段 (由于之前有个 translator 的 createdAt, updatedAt 的修正，通过 IF NOT EXISTS 保障兼容)
    print("\n[5] 检查 translator 表字段...")
    try:
        cursor.execute("ALTER TABLE translator ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE translator ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        print("  - translator 表时间字段检查完毕")
    except Exception as e:
        pass


    cursor.close()
    conn.close()
    print("\n✓ 所有增量结构迁移执行完毕！")
    print("  你可以将本项目代码推送到云端后，直接在 Docker 环境中执行：")
    print("  docker exec -it <postgres_container_name> python db_migrate_latest.py")
    print("  或者如果你已经做了端口映射并在宿主机装了 psycopg2，也可在宿主机直接执行。")

if __name__ == "__main__":
    migrate()
