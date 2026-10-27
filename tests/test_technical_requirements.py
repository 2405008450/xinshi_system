from uuid import UUID,uuid4
import pytest
from fastapi import HTTPException
from test_chat_mentions_all import chat_env
from test_chat_participant_access import environment


def setup(db,people,monkeypatch):
    from models import AppUser,AnnotationChatMember
    from annotation_models import AnnotationProject
    from department_models import Department,DepartmentMember
    import technical_requirements as service
    for name,usernames in service.DEFAULT_PEOPLE:
        db.add(AppUser(id=uuid4(),username=next(iter(usernames)),full_name=name,password_hash='disabled',is_active=True))
    department=Department(id=uuid4(),name='IT部',aliases=[],revision=1)
    db.add(department);db.flush()
    db.add(DepartmentMember(department_id=department.id,user_id=people[1].id))
    project=AnnotationProject(id=uuid4(),order_no='AP-TECH-001',project_name='技术需求项目',created_by=people[0].id)
    db.add(project);db.flush()
    db.add(AnnotationChatMember(project_id=project.id,user_id=people[0].id,following=True,last_read_sequence=0))
    monkeypatch.setattr(AnnotationProject,'role_assignments',property(lambda self:[dict(role_code='project_manager',assignee_id=people[1].id)]))
    db.commit()
    return project


def test_default_members_scope_idempotency_document_and_search(chat_env,monkeypatch):
    db,(actor,it_member,outsider)=chat_env
    import technical_requirements as service
    from technical_requirement_models import TechnicalRoom,TechnicalAppend
    from discussion_chat_models import DiscussionMember
    from routers.discussion_chat import MessageCreate
    from discussion_chat_service import send
    from routers.technical_requirements import listing
    project=setup(db,[actor,it_member,outsider],monkeypatch)
    data=service.open_room(db,actor,project.id,[]);room=data['room_id']
    assert data['title'].startswith('技术需求') and data['order_no']=='AP-TECH-001'
    assert db.query(DiscussionMember).filter_by(room_id=room).count()==6
    assert service.open_room(db,actor,project.id,[])['room_id']==room
    assert db.query(TechnicalRoom).count()==1
    with pytest.raises(HTTPException):service.get_room(db,outsider,room)
    first=send(db,actor,room,MessageCreate(content='技术要求一',client_message_id=uuid4()))
    request_id=uuid4()
    result=service.append(db,actor,room,int(first['id']),request_id)
    assert result['requirements']=='技术要求一'
    assert service.append(db,actor,room,int(first['id']),request_id)['revision']==result['revision']
    assert db.query(TechnicalAppend).count()==1
    second=send(db,it_member,room,MessageCreate(content='技术要求二',client_message_id=uuid4()))
    result=service.append(db,it_member,room,int(second['id']),uuid4())
    assert result['requirements']=='技术要求一\n\n技术要求二'
    with pytest.raises(HTTPException):service.save(db,actor,room,'过期覆盖',revision=1)
    saved=service.save(db,actor,room,'人工整理后的需求',result['revision'])
    assert saved['requirements']=='人工整理后的需求'
    assert listing(keyword='AP-TECH 技术需求',offset=0,limit=50,db=db,user=actor)['total']==1
    assert listing(keyword='',offset=0,limit=50,db=db,user=outsider)['total']==0
    service.open_room(db,actor,project.id,[outsider.id])
    assert service.get_room(db,outsider,room).room_id==room


def test_technical_migration_is_create_only_repeatable(chat_env):
    db,_=chat_env
    from technical_requirement_models import TechnicalAppend,TechnicalRoom
    from tools.apply_technical_requirements_migration import apply_migration
    for model in (TechnicalAppend,TechnicalRoom):model.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
