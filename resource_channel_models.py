"""渠道账号归属；原平台账号和业务外键保持不变。"""
from sqlalchemy import CheckConstraint, ForeignKey, Index, Uuid
from sqlalchemy.orm import mapped_column

from models import Base


class ChannelAccountLink(Base):
    __tablename__ = "resource_channel_account_link"
    __table_args__ = (
        CheckConstraint("parent_id <> account_id", name="ck_channel_account_not_self"),
        Index("ix_channel_account_parent", "parent_id"),
    )
    # 账号只有一个归属平台，删除归属关系不会删除账号。
    account_id = mapped_column(Uuid, ForeignKey("resource_development_option.id", ondelete="RESTRICT"), primary_key=True)
    parent_id = mapped_column(Uuid, ForeignKey("resource_development_option.id", ondelete="RESTRICT"), nullable=False)
