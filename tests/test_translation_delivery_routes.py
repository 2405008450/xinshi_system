def test_frontend_proxy_stripped_path_reaches_settings_without_sending(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db
    from routers.auth import get_current_user
    from routers import translation_delivery
    monkeypatch.setattr(translation_delivery.service,'catalog',lambda db,user:{'audience':[{'value':'all','label':'全体'}]})
    saved=dict(app.dependency_overrides)
    app.dependency_overrides[get_db]=lambda:None
    app.dependency_overrides[get_current_user]=lambda:object()
    try:
        client=TestClient(app)
        for path in ('/translation-delivery/settings','/api/translation-delivery/settings'):
            response=client.get(path)
            assert response.status_code==200 and response.json()['audience'][0]['value']=='all'
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(saved)
