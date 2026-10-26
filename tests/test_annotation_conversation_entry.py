from test_chat_participant_access import environment,project

def test_imported_default_members_do_not_mean_created(environment):
    db,(owner,*_)=environment
    from models import AnnotationChatMember
    from routers.annotation_chat import start,conversation_status,ConversationStatusRequest
    from annotation_chat_conversation import AnnotationChatConversation
    row=project(db,owner,'AP-DEFAULT-SEED')
    db.add(AnnotationChatMember(project_id=row.id,user_id=owner.id,following=True,last_read_sequence=0));db.commit()
    payload=ConversationStatusRequest(project_ids=[row.id])
    before=conversation_status(payload,db,owner)['items'][0]
    assert not before['created'] and not before['joined']
    start(row.id,db,owner)
    assert db.get(AnnotationChatConversation,row.id).created_by==owner.id
    assert conversation_status(payload,db,owner)['items'][0]['joined']


def test_department_member_can_join_existing_and_status_is_accurate(environment):
    db,(owner,member,outsider)=environment
    from department_models import Department,DepartmentMember
    from routers.annotation_chat import start,conversation_status,ConversationStatusRequest
    from models import AnnotationChatMember
    from uuid import uuid4
    row=project(db,owner)
    dept=Department(id=uuid4(),name='标注项目部',aliases=[],revision=1)
    db.add(dept);db.flush();db.add(DepartmentMember(department_id=dept.id,user_id=outsider.id,position='项目助理'));db.commit()
    payload=ConversationStatusRequest(project_ids=[row.id])
    assert conversation_status(payload,db,outsider)['items'][0]['created'] is False
    start(row.id,db,owner)
    before=conversation_status(payload,db,outsider)['items'][0]
    assert before['created'] and before['can_join'] and not before['joined']
    start(row.id,db,outsider)
    after=conversation_status(payload,db,outsider)['items'][0]
    assert after['joined'] and db.get(AnnotationChatMember,(row.id,outsider.id))
    start(row.id,db,outsider)
    assert db.query(AnnotationChatMember).filter_by(project_id=row.id,user_id=outsider.id).count()==1
