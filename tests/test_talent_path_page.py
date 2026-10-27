"""路径窗口分页、筛选与联系方式权限，只使用内存隔离数据库。"""
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_chat_participant_access import environment


def test_path_page_lists_regions_paths_paginates_and_masks_contacts(environment, monkeypatch):
    db, users = environment
    from resource_models import ResourcePerson
    from routers import talents
    from routers.auth import get_current_user
    from database import get_db
    for index, path in enumerate([None, '', ' \t\n', r'\\server\简历\a.pdf', 'D:/简历/b.pdf']):
        db.add(ResourcePerson(id=uuid4(), full_name=f'路径人才{index}', status='active', resource_code=f'PATH-{index}', resume_path=path,
                              ancestral_home='籍贯独立值', native_place='成长地独立值', residence_address='所在地独立值',
                              primary_phone='123456789', wechat='wechat-private', whatsapp='wa-private'))
    db.commit()
    app = FastAPI()
    app.include_router(talents.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    monkeypatch.setattr(talents, 'can_view_talent_contacts', lambda *args: False)
    with TestClient(app) as client:
        result = client.get('/talents/path-page', params={'registered': 'false', 'skip': 0, 'limit': 2})
        assert result.status_code == 200, result.text
        data = result.json()
        assert data['total'] == 3 and len(data['items']) == 2
        row = data['items'][0]
        assert row['ancestral_home'] == '籍贯独立值'
        assert row['native_place'] == '成长地独立值'
        assert row['residence_address'] == '所在地独立值'
        assert row['primary_phone'] == row['wechat'] == row['whatsapp'] == '******'
        assert row['contact_restricted'] is True
        second = client.get('/talents/path-page', params={'registered': 'false', 'skip': 2, 'limit': 2}).json()
        assert second['total'] == 3 and len(second['items']) == 1
        assert not ({row['id'] for row in data['items']} & {row['id'] for row in second['items']})
        monkeypatch.setattr(talents, 'can_view_talent_contacts', lambda *args: True)
        registered = client.get('/talents/path-page', params={'registered': 'true'}).json()
        assert registered['total'] == 2
        assert all(row['resume_path'] for row in registered['items'])
        assert registered['items'][0]['whatsapp'] == 'wa-private'
        assert client.get('/talents/path-page').json()['total'] == 5
        for params in [{'skip':-1}, {'limit':101}, {'registered':'invalid'}]:
            assert client.get('/talents/path-page', params=params).status_code == 422
