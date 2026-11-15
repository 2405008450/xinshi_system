"""验证外勤记录、客户视图、照片隔离和幂等保存，使用内存 SQLite。"""
import json
from io import BytesIO
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import inspect

from database import get_db
from field_work import FieldWork
from models import Client
from routers.auth import get_current_user
from routers.field_work import customer_reader, router
from test_chat_participant_access import environment
from tools.apply_field_work_migration import apply_migration


def test_field_work_routes_and_repeatable_migration(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    monkeypatch.setattr("field_work.user_has_permission", lambda db, uid, code: uid == owner.id)
    connection = db.connection()
    FieldWork.__table__.drop(connection)
    apply_migration(connection)
    apply_migration(connection)
    assert inspect(connection).has_table("attendance_field_work")
    client = Client(id=uuid4(), client_code="FW001", client_name="外勤客户", client_short_name="外勤")
    db.add(client)
    db.commit()

    app = FastAPI()
    app.include_router(router)
    current = [owner]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current[0]
    url = "/attendance/field-work"
    record_id = str(uuid4())
    draft = {
        "id": record_id, "type_path": ["customer", "bidding", "accompany"],
        "start_at": "2026-11-13T09:00:00+08:00", "end_at": "2026-11-13T10:17:00+08:00",
        "location": "客户会议室", "companion_ids": [str(member.id)], "client_id": str(client.id),
        "notes": "整理投标材料",
    }
    def write(data, files=None):
        response = http.put(url, data={"payload": json.dumps(data)}, files=files)
        if response.status_code >= 400:
            db.rollback()
        return response

    with TestClient(app) as http:
        people = http.get(url + "/options").json()["people"]
        assert {person["id"] for person in people} == {str(member.id), str(outsider.id)}
        assert write({**draft, "client_id": None}).status_code == 422
        assert write({**draft, "end_at": draft["start_at"]}).status_code == 422
        assert write(draft, {"photo": ("invalid.png", b"invalid", "image/png")}).status_code == 400
        image = BytesIO()
        Image.new("RGB", (20, 20)).save(image, "PNG")
        response = write(draft, {"photo": ("check-in.png", image.getvalue(), "image/png")})
        assert response.status_code == 200, response.text
        row = response.json()
        assert row["revision"] == 1 and row["has_photo"] and row["client_name"] == "外勤客户"
        assert row["start_at"].endswith("+08:00")
        assert write(draft).json()["revision"] == 1
        assert http.get(url + f"/{record_id}/photo").headers["content-type"] == "image/png"
        assert http.get(url, params={"keyword": "外勤 整理"}).json()["total"] == 1

        current[0] = outsider
        assert http.get(url).json()["total"] == 0
        assert http.get(url + f"/{record_id}/photo").status_code == 404
        assert http.get(url + "/customers").status_code == 403
        assert write({**draft, "revision": 1}).status_code == 404
        assert write({**draft, "id": str(uuid4()), "companion_ids": []}).status_code == 403

        app.dependency_overrides[customer_reader] = lambda: outsider
        assert http.get(url + "/customers").json()["items"][0]["id"] == record_id
        assert http.get(url + f"/customers/{record_id}/photo").status_code == 200
        current[0] = owner
        changed = write({**draft, "revision": 1, "type_path": ["bank"], "remove_photo": True}).json()
        assert changed["revision"] == 2 and changed["client_name"] is None and not changed["has_photo"]
        assert http.get(url + "/customers").json()["total"] == 0
        assert http.get(url + f"/customers/{record_id}/photo").status_code == 404
        assert write({**draft, "revision": 1}).status_code == 409
