import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import TranslationProject

def generate_order_no(db: Session) -> str:
    """
    生成主订单流水号
    格式: TP-YYMMDD-NNN (如 TP-260304-007)
    """
    # 日期格式改为 YYMMDD (6位)
    today_str = datetime.datetime.now().strftime("%y%m%d")
    prefix = f"TP-{today_str}-"

    # 查询今天最大的订单号（匹配新格式，排除子订单）
    last_project = (
        db.query(TranslationProject)
        .filter(TranslationProject.order_no.like(f"TP-{today_str}-%"))
        .filter(~TranslationProject.order_no.like("%.%"))
        .order_by(TranslationProject.order_no.desc())
        .first()
    )

    if last_project and last_project.order_no:
        try:
            # 提取流水号部分（TP-YYMMDD-NNN）
            seq_str = last_project.order_no.split("-")[-1]
            last_seq = int(seq_str)
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:03d}"


def generate_sub_order_no(db: Session, parent_order_no: str) -> str:
    """
    生成子订单流水号
    格式: TP-YYMMDD-NNN.X (如 TP-260304-007.1)

    Args:
        db: 数据库会话
        parent_order_no: 主订单号，如 TP-260304-007
    """
    # 查询该主订单下的最大子订单序号
    sub_pattern = f"{parent_order_no}.%"
    last_sub = (
        db.query(TranslationProject)
        .filter(TranslationProject.order_no.like(sub_pattern))
        .order_by(TranslationProject.order_no.desc())
        .first()
    )

    if last_sub and last_sub.order_no:
        try:
            # 提取子订单序号 .X 中的 X
            last_seq = int(last_sub.order_no.split(".")[-1])
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    return f"{parent_order_no}.{new_seq}"
