from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment,project
from chat_personal_folders import validate_nodes,save,get,Write,ChatPersonalFolders

def folder(parent=None,**extra):return dict(id=str(uuid4()),parentId=parent,name='个人目录',**extra)

def test_depth_cycle_and_invalid_parent():
    nodes=[];parent=None
    for _ in range(5):
        row=folder(parent);nodes.append(row);parent=row['id']
    assert len(validate_nodes(nodes))==5
    with pytest.raises(ValueError):validate_nodes(nodes+[folder(parent)])
    nodes[0]['parentId']=parent
    with pytest.raises(ValueError):validate_nodes(nodes)
    with pytest.raises(ValueError):validate_nodes([folder(str(uuid4()))])

def test_private_revision_and_member_boundary(environment):
    db,(owner,member,outsider)=environment
    from models import AnnotationChatMember
    p=project(db,owner);db.add(AnnotationChatMember(project_id=p.id,user_id=owner.id));db.commit()
    node=folder(session=dict(projectType='annotation',projectId=str(p.id)))
    result=save(Write(revision=0,nodes=[node]),db,owner)
    assert result['revision']==1 and len(get(db,owner)['nodes'])==1
    assert get(db,member)==dict(revision=0,nodes=[])
    with pytest.raises(HTTPException) as err:save(Write(revision=0,nodes=[node]),db,outsider)
    assert err.value.status_code==403
    with pytest.raises(HTTPException) as err:save(Write(revision=0,nodes=[]),db,owner)
    assert err.value.status_code==409
    db.query(AnnotationChatMember).filter_by(project_id=p.id,user_id=owner.id).delete();db.commit()
    assert get(db,owner)['nodes']==[]

def test_migration_only_new_table(environment):
    from sqlalchemy import text,inspect
    from tools.apply_chat_personal_folders_migration import apply_migration
    db,users=environment;db.execute(text('DROP TABLE chat_personal_folders'))
    apply_migration(db.connection());apply_migration(db.connection())
    assert inspect(db.connection()).has_table('chat_personal_folders')
    assert db.execute(text('SELECT count(*) FROM app_user')).scalar()==3


def test_snake_case_request_transport():
    root=folder();cid=str(uuid4())
    child=dict(id=str(uuid4()),parent_id=root['id'],name='会话',session=dict(project_type='direct',project_id=cid))
    result=validate_nodes([root,child])
    assert result[1]['parentId']==root['id'] and result[1]['session']['projectId']==cid
