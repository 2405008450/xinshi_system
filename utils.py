import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import TranslationProject

def generate_order_no(db: Session) -> str:
    """
    生成订单流水号
    格式: PRJ-YYYYMMDD-0001
    """
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    prefix = f"PRJ-{today_str}-"
    
    # 查询今天最大的订单号
    last_project = (
        db.query(TranslationProject)
        .filter(TranslationProject.order_no.like(f"{prefix}%"))
        .order_by(TranslationProject.order_no.desc())
        .first()
    )
    
    if last_project and last_project.order_no:
        try:
            last_seq = int(last_project.order_no.split("-")[-1])
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1
        
    return f"{prefix}{new_seq:04d}"
