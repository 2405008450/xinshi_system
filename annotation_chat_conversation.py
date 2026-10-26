"""显式创建登记；默认成员记录不能代替会话创建。"""
from sqlalchemy import DateTime, ForeignKey, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base,ChatProjectMessage,AnnotationChatMember
from chat_time import now

class AnnotationChatConversation(Base):
    __tablename__='annotation_chat_conversation'
    project_id=mapped_column(Uuid,ForeignKey('annotation_project.id',ondelete='CASCADE'),primary_key=True)
    created_by=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=now)

def ready(db):
    return inspect(db.connection()).has_table(AnnotationChatConversation.__tablename__)

def created_ids(db,ids):
    ids=set(ids)
    result={pid for pid, in db.query(ChatProjectMessage.annotation_project_id).filter(ChatProjectMessage.annotation_project_id.in_(ids)).distinct()}
    if ready(db):
        result.update(pid for pid, in db.query(AnnotationChatConversation.project_id).filter(AnnotationChatConversation.project_id.in_(ids)))
    else:
        # 独立迁移未执行前保持现有目录口径，不在服务启动时补建或改历史。
        result.update(pid for pid, in db.query(AnnotationChatMember.project_id).filter(AnnotationChatMember.project_id.in_(ids)).distinct())
    return result
