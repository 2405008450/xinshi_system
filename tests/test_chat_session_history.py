from test_chat_participant_access import environment, project


def test_directory_pins_before_pagination_and_isolates_accounts(environment):
    from models import AnnotationChatMember
    from chat_session_history import list_sessions
    db, (owner, member, outsider) = environment
    rows = [project(db, owner, f'AP-PIN-{i}') for i in range(3)]
    for i, row in enumerate(rows):
        row.project_name = f'{i}排序测试'
        for person in (member, outsider):
            db.add(AnnotationChatMember(project_id=row.id, user_id=person.id,
                following=True, last_read_sequence=0, pinned=person == member and i == 2, starred=False))
    db.commit()
    first = list_sessions(db, member, 'AP-PIN', limit=1)
    assert first['total'] == 3
    assert first['items'][0]['project_id'] == str(rows[2].id)
    assert first['items'][0]['pinned'] is True
    assert list_sessions(db, member, 'AP-PIN', offset=1, limit=1)['items'][0]['project_id'] == str(rows[0].id)
    assert list_sessions(db, outsider, 'AP-PIN', limit=1)['items'][0]['project_id'] == str(rows[0].id)
    db.get(AnnotationChatMember, (rows[2].id, member.id)).pinned = False
    db.commit()
    assert list_sessions(db, member, 'AP-PIN', limit=1)['items'][0]['project_id'] == str(rows[0].id)


def test_all_sessions_include_unfollowed_membership_but_exclude_other_people(environment):
    from models import AnnotationChatMember
    from chat_session_history import list_sessions
    db, (owner, member, outsider) = environment
    allowed = project(db, owner, 'AP-HISTORY-001')
    hidden = project(db, owner, 'AP-HISTORY-002')
    db.add_all([
        AnnotationChatMember(project_id=allowed.id, user_id=member.id, following=False, last_read_sequence=0),
        AnnotationChatMember(project_id=hidden.id, user_id=outsider.id, following=True, last_read_sequence=0),
    ])
    db.commit()
    result = list_sessions(db, member, 'AP-HISTORY')
    assert result['total'] == 1
    assert result['items'][0]['project_id'] == str(allowed.id)
    assert result['items'][0]['key'] == f'annotation:{allowed.id}'


def test_directory_search_and_pages_share_filters(environment):
    from models import AnnotationChatMember
    from chat_session_history import list_sessions
    db, (owner, member, outsider) = environment
    for index in range(3):
        row = project(db, owner, f'AP-PAGE-{index:03d}')
        db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=False, last_read_sequence=0))
    db.commit()
    first = list_sessions(db, member, 'PAGE 隔离', limit=2)
    second = list_sessions(db, member, '隔离 PAGE', offset=2, limit=2)
    assert first['total'] == second['total'] == 3
    assert len(first['items']) == 2 and len(second['items']) == 1
    assert not ({item['key'] for item in first['items']} & {item['key'] for item in second['items']})
    assert list_sessions(db, member, 'PAGE%')['total'] == 0
    member.is_active = False
    assert list_sessions(db, member) == dict(items=[], total=0)


def test_my_projects_match_managers_not_creators_and_keep_access_boundary(environment):
    from uuid import uuid4
    from models import AnnotationChatMember
    from workflow_models import ProjectWorkbenchResponsibility as Role
    from chat_session_history import list_sessions
    db, (owner, member, outsider) = environment
    pm = project(db, owner, 'AP-MINE-PM')
    customer = project(db, owner, 'AP-MINE-CUSTOMER')
    customer.client_manager_id = member.id
    only_creator = project(db, member, 'AP-MINE-CREATOR')
    hidden = project(db, owner, 'AP-MINE-HIDDEN')
    for row in (pm, customer, only_creator):
        db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=False, last_read_sequence=0))
    for row, role in ((pm, 'project_manager'), (hidden, 'project_manager'), (only_creator, 'project_assistant')):
        db.add(Role(id=uuid4(), annotation_project_id=row.id, role_code=role, assignee_id=member.id))
    db.commit()
    result = list_sessions(db, member, mine=True, limit=1)
    second = list_sessions(db, member, mine=True, limit=1, offset=1)
    assert result['total'] == second['total'] == 2
    assert {row['project_id'] for row in result['items'] + second['items']} == {str(pm.id), str(customer.id)}


def test_project_discussions_share_source_status_and_my_project_filter(environment):
    from models import AnnotationChatMember
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder
    from technical_requirement_models import TechnicalRoom
    from discussion_chat_models import DiscussionMember
    from uuid import uuid4
    from chat_session_history import list_sessions
    from chat_project_views import decorate_sessions
    db, (owner, member, outsider) = environment
    source = project(db, owner, 'AP-SOURCE-001')
    source.client_manager_id = member.id; source.project_status = 'trial_passed'
    category = ChatSessionCategory(id=uuid4(), name='技术需求 · 已打开会话', active=True, updated_by=owner.id)
    db.add(category); db.flush()
    db.add_all([TechnicalRoom(project_id=source.id, room_id=category.id, created_by=owner.id, updated_by=owner.id),
        ChatSessionCategoryFolder(category_id=category.id, parent_key='dcb1f917-6000-4000-8000-000000000002'),
        DiscussionMember(room_id=category.id, user_id=member.id, last_read_id=0)])
    db.commit()
    result = list_sessions(db, member, mine=True)
    assert result['total'] == 1 and result['items'][0]['project_id'] == str(category.id)
    rows = [dict(key=f'discussion:{category.id}', kind='discussion', project_id=category.id)]
    decorate_sessions(db, member, rows)
    assert rows[0]['project_module'] == 'annotation'
    assert rows[0]['project_status'] == 'trial_passed' and rows[0]['is_my_project'] is True
    assert list_sessions(db, outsider, mine=True)['total'] == 0


def test_translation_manager_change_overrides_legacy_client_name(environment):
    from uuid import uuid4
    from models import Client, TranslationProject
    from project_client_manager import ProjectClientManagerChange
    from chat_project_views import mine_condition
    db, (owner, member, outsider) = environment
    client = Client(id=uuid4(), client_name='隔离客户', client_manager=member.full_name)
    db.add(client); db.flush()
    projects = [TranslationProject(id=uuid4(), order_no=f'TP-MINE-{index}', project_name='负责人测试', client_id=client.id,
        created_by=member.id, project_manager_id=member.id if index == 2 else None) for index in range(3)]
    db.add_all(projects); db.flush()
    for row in projects[1:]:
        db.add(ProjectClientManagerChange(id=uuid4(), project_type='translation', project_id=row.id, revision=1,
            new_manager_id=outsider.id, new_manager_name=outsider.full_name))
    db.commit()
    owned = {pid for pid, in db.query(TranslationProject.id).filter(mine_condition(db, 'translation', TranslationProject, member))}
    assert owned == {projects[0].id, projects[2].id}


def test_groups_only_excludes_direct_from_total_and_pages(environment):
    from uuid import uuid4
    from models import ChatDirectConversation,ChatDirectMember,AnnotationChatMember
    from chat_session_history import list_sessions
    db,(owner,member,outsider)=environment
    group=project(db,owner,'AP-GROUPS-001')
    db.add(AnnotationChatMember(project_id=group.id,user_id=owner.id))
    room=ChatDirectConversation(id=uuid4(),user_low_id=owner.id,user_high_id=member.id)
    db.add(room);db.flush();db.add(ChatDirectMember(conversation_id=room.id,user_id=owner.id));db.commit()
    all_rows=list_sessions(db,owner)
    assert any(row['kind']=='direct' for row in all_rows['items'])
    groups=list_sessions(db,owner,groups_only=True,limit=1)
    assert groups['total']==all_rows['total']-1
    assert all(row['kind']!='direct' for row in groups['items'])
