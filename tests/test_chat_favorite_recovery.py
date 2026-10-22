"""收藏恢复仅使用隔离 SQLite，不操作业务库。"""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from test_chat_participant_access import environment, project  # noqa: F401


def test_catalog_only_exposes_own_explicitly_unfollowed_memberships(environment):
    from models import AnnotationChatMember
    from routers.annotation_chat import unfollowed_projects
    db, (owner, member, outsider) = environment
    rows = [project(db, owner, f'AP-261022-{index:03}') for index in range(1, 5)]
    db.add_all([
        AnnotationChatMember(project_id=rows[0].id,user_id=owner.id,following=False,explicit_unfollow=True),
        AnnotationChatMember(project_id=rows[1].id,user_id=owner.id,following=True,explicit_unfollow=False),
        AnnotationChatMember(project_id=rows[2].id,user_id=owner.id,following=False,explicit_unfollow=False),
        AnnotationChatMember(project_id=rows[3].id,user_id=member.id,following=False,explicit_unfollow=True),
    ]);db.commit()
    data=unfollowed_projects(0,10,db,owner)
    assert data['total']==1
    assert data['items'][0]['project_id']==rows[0].id
    assert unfollowed_projects(0,10,db,outsider)['total']==0


def test_batch_recovery_preserves_unread_and_reports_unauthorized_without_joining(environment):
    from models import AnnotationChatMember
    from routers.annotation_chat import RestoreFavoritesRequest, restore_favorites, unfollowed_projects
    db, (owner, member, outsider)=environment
    own=project(db,owner,'AP-261022-001'); other=project(db,member,'AP-261022-002')
    db.add(AnnotationChatMember(project_id=own.id,user_id=owner.id,following=False,explicit_unfollow=True,last_read_sequence=4));db.commit()
    data=restore_favorites(RestoreFavoritesRequest(project_ids=[other.id,own.id,own.id]),db,owner)
    assert data['restored']==[own.id]
    assert len(data['failed'])==1 and data['failed'][0]['project_id']==other.id
    restored=db.get(AnnotationChatMember,(own.id,owner.id))
    assert restored.following and not restored.explicit_unfollow and restored.last_read_sequence==4
    assert db.get(AnnotationChatMember,(other.id,owner.id)) is None
    assert unfollowed_projects(0,10,db,owner)['total']==0
    assert restore_favorites(RestoreFavoritesRequest(project_ids=[own.id]),db,owner)['restored']==[own.id]


def test_batch_recovery_accepts_ten_and_rejects_eleven_and_empty():
    from routers.annotation_chat import RestoreFavoritesRequest
    assert len(RestoreFavoritesRequest(project_ids=[uuid4() for _ in range(10)]).project_ids)==10
    for ids in ([],[uuid4() for _ in range(11)]):
        with pytest.raises(ValidationError):RestoreFavoritesRequest(project_ids=ids)
