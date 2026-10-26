"""总结快捷筛选、实际通知对象：仅使用隔离内存数据库。"""
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_chat_participant_access import environment  # noqa: F401
from test_resource_issue_visibility import issue


def test_multiple_department_notifications_creator_and_visibility(environment, monkeypatch):
    db, (creator, actor, other) = environment
    import resource_issue_service as service
    import resource_summary_service as summary
    import routers.resource_issues as route
    from department_models import Department, DepartmentMember
    from resource_issue_models import DevelopmentIssueAudience as Audience
    from resource_issue_schemas import SummaryFields
    import crud
    monkeypatch.setattr(service, 'can_delegate', lambda *args: False)
    monkeypatch.setattr(service, 'can_collect', lambda *args: False)
    monkeypatch.setattr(service, 'is_admin', lambda *args: False)
    monkeypatch.setattr(crud, 'create_notifications_for_users', lambda *args, **kwargs: [])

    own = issue(db, actor, view_all=True)
    own.proposer_id, own.proposer_name = creator.id, creator.username
    proposed = issue(db, creator, view_all=True)
    proposed.proposer_id, proposed.proposer_name = actor.id, actor.username
    multiple = issue(db, creator, view_all=True)
    summary.write_summary(db, multiple, SummaryFields(view_all=True, notify_user_ids=[actor.id, other.id]))
    # 部门通知将当时的实际接收人落在 Audience，人员以后调部门不改变该记录。
    department = Department(id=uuid4(), name='通知测试部门', aliases=[], revision=1)
    db.add(department); db.flush()
    db.add(DepartmentMember(department_id=department.id, user_id=actor.id)); db.flush()
    grouped = issue(db, actor, view_all=True)
    summary.write_summary(db, grouped, SummaryFields(view_all=True, notify_department_ids=[department.id]))
    follower = issue(db, creator, view_all=True)
    db.add(Audience(issue_id=follower.id, kind='follower', target_id=actor.id))
    inaccessible = issue(db, creator, view_all=False, view_user_ids=[])
    db.add(Audience(issue_id=inaccessible.id, kind='notify_user', target_id=actor.id))
    db.commit()
    db.query(DepartmentMember).delete(); db.commit()

    app = FastAPI(); app.include_router(route.router)
    app.dependency_overrides[route.ready] = lambda: db
    app.dependency_overrides[route.user] = lambda: actor
    client = TestClient(app)
    url = '/resource-development/issues'
    def listing(**params):
        response = client.get(url, params=params)
        assert response.status_code == 200, response.text
        return response.json()
    notified = listing(notified_me=True)
    assert notified['total'] == 2
    assert {row['id'] for row in notified['items']} == {str(multiple.id), str(grouped.id)}
    assert next(row for row in notified['items'] if row['id'] == str(multiple.id))['notified_user_names'] == ['member', 'outsider']
    assert next(row for row in notified['items'] if row['id'] == str(grouped.id))['notified_user_names'] == ['member']
    mine = listing(created_by_me=True)
    assert {row['id'] for row in mine['items']} == {str(own.id), str(grouped.id)}
    proposed_by_me = listing(proposer_id=str(actor.id))
    assert {row['id'] for row in proposed_by_me['items']} == {str(proposed.id), str(grouped.id)}
    assert listing(proposer_id=str(actor.id), created_by_me=True)['items'][0]['id'] == str(grouped.id)
    assert listing(proposer_id=str(actor.id), notified_me=True)['total'] == 1
    combined = listing(notified_me=True, created_by_me=True)
    assert combined['total'] == 1 and combined['items'][0]['id'] == str(grouped.id)
    first, second = listing(notified_me=True, limit=1), listing(notified_me=True, skip=1, limit=1)
    assert first['total'] == second['total'] == 2
    assert first['items'][0]['id'] != second['items'][0]['id']
    assert listing(notified_me=True, keyword='不存在的关键词')['total'] == 0
    assert listing()['total'] == 5  # 清除快捷条件恢复可见全集，私密记录仍被隔离。
