import main
from database import engine
from sqlalchemy import text

with engine.begin() as conn:
    result = conn.execute(text("DELETE FROM push_subscription WHERE endpoint LIKE '%permanently-removed.invalid%'"))
    print(f"✅ 假地址已被彻底强杀！共清理了 {result.rowcount} 条记录。")