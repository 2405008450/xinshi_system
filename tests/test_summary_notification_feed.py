"""会话通知同时展示总结与需求；只使用内存隔离库。"""
from uuid import uuid4
from datetime import timedelta
from test_chat_participant_access import environment


def test_summary_and_request_share_pagination_and_unread_count(environment):
    db,(owner,member,other)=environment
    from models import AppNotification
    from crud import get_notifications,count_unread_notifications
    from business_time import business_now
    now=business_now().replace(tzinfo=None)
    def add(kind,user,offset,read=False):
        row=AppNotification(id=uuid4(),recipient_user_id=user.id,title=kind,content='隔离测试',notification_type=kind,is_read=read,created_at=now+timedelta(seconds=offset))
        db.add(row);return row
    summary=add('chat_summary',member,3)
    request=add('resource_request_dispatch',member,2)
    read_summary=add('chat_summary',member,1,True)
    add('workflow',member,4);add('chat_summary',other,5)
    db.flush()
    filters=dict(channel='business',notification_types=['resource_request_dispatch','chat_summary'])
    first=get_notifications(db,member.id,limit=2,**filters)
    assert [row.id for row in first]==[summary.id,request.id]
    assert [row.id for row in get_notifications(db,member.id,skip=2,limit=2,**filters)]==[read_summary.id]
    assert count_unread_notifications(db,member.id,**filters)==2
    summary.is_read=True;db.flush()
    assert count_unread_notifications(db,member.id,**filters)==1
    assert [row.id for row in get_notifications(db,member.id,notification_type='resource_request_dispatch')]==[request.id]
