from test_chat_participant_access import environment,project
from uuid import uuid4


def test_nested_internal_rooms_survive_explicit_null_root_location(environment):
    from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder
    from discussion_chat_models import DiscussionMember
    from routers.chat_sessions import sessions
    db, (owner, member, outsider) = environment
    root = Category(id=uuid4(), name='内部管理群', updated_by=owner.id, active=True)
    children = [Category(id=uuid4(), name=name, updated_by=owner.id, active=True)
                for name in ('新媒体 新技术', '催款追款群')]
    db.add_all([root, *children]); db.flush()
    db.add(Folder(category_id=root.id, parent_key=None))
    for child in children:
        db.add(Folder(category_id=child.id, parent_key=str(root.id)))
        db.add(DiscussionMember(room_id=child.id, user_id=member.id, last_read_id=0))
    db.commit()
    rows = sessions(db, member)['items']
    assert {str(row['project_id']) for row in rows if row['kind'] == 'discussion'} == {str(child.id) for child in children}
    assert all(row['category_ids'] == [str(row['project_id'])] for row in rows if row['kind'] == 'discussion')
    assert not [row for row in sessions(db, outsider)['items'] if row['kind'] == 'discussion']


def test_favorites_are_per_account(environment):
    from models import AnnotationChatMember
    from routers.annotation_chat import follow, FollowRequest
    from routers.chat_sessions import sessions
    db, (owner, member, outsider) = environment
    row = project(db, owner, 'AP-FAVORITES-ISOLATION')
    db.add_all([AnnotationChatMember(project_id=row.id, user_id=user.id, following=True, last_read_sequence=0)
                for user in (owner, member)])
    db.commit()
    follow(row.id, FollowRequest(following=False), db, owner)
    assert db.get(AnnotationChatMember, (row.id, member.id)).following is True
    assert not [item for item in sessions(db, owner)['items'] if item['kind'] == 'annotation' and item['following']]
    assert [item for item in sessions(db, member)['items'] if item['kind'] == 'annotation' and item['following']]


def test_annotation_session_manager_flag_uses_current_assigned_role(environment):
    from models import AnnotationChatMember
    from routers.chat_sessions import sessions
    from workflow_models import ProjectWorkbenchResponsibility

    db, (owner, manager, other_manager) = environment
    managed = project(db, owner, 'AP-MANAGED-001')
    assisted = project(db, owner, 'AP-ASSISTED-001')
    for row in (managed, assisted):
        db.add(AnnotationChatMember(project_id=row.id, user_id=manager.id, following=True, last_read_sequence=0))
    for row, role, assignee in [
        (managed, 'project_manager', other_manager), (managed, 'project_manager', manager),
        (assisted, 'project_assistant', manager), (assisted, 'project_manager', other_manager),
    ]:
        db.add(ProjectWorkbenchResponsibility(id=uuid4(), annotation_project_id=row.id, role_code=role, assignee_id=assignee.id))
    db.commit()
    flags = {row['project_id']: row['is_project_manager'] for row in sessions(db, manager)['items'] if row['kind'] == 'annotation'}
    assert flags == {managed.id: True, assisted.id: False}

def test_counts_are_scoped_to_each_conversation_and_update_when_members_change(environment):
 db,(owner,member,outsider)=environment
 from models import AnnotationChatMember
 from routers.chat_sessions import decorate_member_counts
 parent=project(db,owner,'AP-COUNT-001');child=project(db,owner,'AP-COUNT-001.001')
 for pid,uid in [(parent.id,owner.id),(parent.id,member.id),(child.id,owner.id)]:
  db.add(AnnotationChatMember(project_id=pid,user_id=uid,following=True,last_read_sequence=0))
 db.commit()
 rows=[{'kind':'annotation','project_id':p.id} for p in [parent,child]]
 decorate_member_counts(db,rows)
 assert [row['member_count'] for row in rows]==[2,1]
 db.query(AnnotationChatMember).filter_by(project_id=parent.id,user_id=member.id).delete();db.commit()
 decorate_member_counts(db,rows)
 assert [row['member_count'] for row in rows]==[1,1]

def test_session_catalog_does_not_lazy_load_flags_for_each_project(environment):
    from sqlalchemy import event
    from models import AnnotationChatMember
    from routers.chat_sessions import sessions

    db, (owner, member, outsider) = environment
    projects = [project(db, owner, f'AP-BATCH-{index:03d}') for index in range(8)]
    for index, row in enumerate(projects):
        db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=True,
            pinned=index == 0, starred=index == 1, last_read_sequence=0))
    db.commit()
    db.expire_all()
    lazy_queries = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith(('SELECT annotation_chat_member.pinned AS', 'SELECT annotation_chat_member.starred AS')):
            lazy_queries.append(statement)
    event.listen(db.get_bind(), 'before_cursor_execute', collect)
    try:
        rows = [row for row in sessions(db, member)['items'] if row['kind'] == 'annotation']
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', collect)
    assert len(rows) == 8
    assert sum(bool(row['pinned']) for row in rows) == 1
    assert sum(bool(row['starred']) for row in rows) == 1
    assert lazy_queries == []
