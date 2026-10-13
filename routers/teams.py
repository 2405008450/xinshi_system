"""团队资源接口，读取及写入边界沿用人才总库。"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from permission_service import user_has_permission
from routers.auth import get_current_user, require_any_permission
from team_resource_schemas import ResourceType, TeamType, TeamWrite
from team_resource_service import TEAM_TYPES, RESOURCE_TYPES, ensure_schema, get_team, list_teams, people_options, save_team, serialize_many
from talent_privacy import can_view_talent_contacts
import team_attachment_service as attachments

router = APIRouter(prefix="/teams", tags=["teams"], dependencies=[Depends(get_current_user)])
write = Depends(require_any_permission("talents:write", "translators:write"))


def initialized_db(db: Session = Depends(get_db)):
    ensure_schema(db)
    return db


@router.get("/options")
def options(db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    return {"team_types": TEAM_TYPES, "resource_types": RESOURCE_TYPES, "people": people_options(db), "user_id": str(user.id),
            "can_view_contacts": can_view_talent_contacts(db, user),
            "can_write": user_has_permission(db, user.id, "talents:write") or user_has_permission(db, user.id, "translators:write")}


@router.get("")
def read_list(keyword: str | None = Query(None, max_length=255), team_type: TeamType | None = None,
              resource_types: list[ResourceType] | None = Query(None, max_length=5), contact_user_id: UUID | None = None,
              follow_up_user_id: UUID | None = None, contact_start: date | None = None, contact_end: date | None = None,
              skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    return list_teams(db, skip, limit, contacts_visible=can_view_talent_contacts(db, user), keyword=keyword, team_type=team_type, resource_types=resource_types,
                      contact_user_id=contact_user_id, follow_up_user_id=follow_up_user_id, contact_start=contact_start, contact_end=contact_end)


@router.get("/{team_id}")
def detail(team_id: UUID, db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    return serialize_many(db, [get_team(db, team_id)], contacts_visible=can_view_talent_contacts(db, user))[0]


@router.post("", dependencies=[write], status_code=201)
def create(payload: TeamWrite, db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    result = save_team(db, user, payload)
    db.commit()
    return result


@router.put("/{team_id}", dependencies=[write])
def update(team_id: UUID, payload: TeamWrite, db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    result = save_team(db, user, payload, team_id)
    db.commit()
    return result


@router.delete("/{team_id}", dependencies=[write], status_code=204)
def delete(team_id: UUID, revision: int = Query(..., ge=1), db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    attachments.delete_team_with_attachments(db, user, team_id, revision)
    return Response(status_code=204)


@router.get("/{team_id}/attachments")
def read_attachments(team_id: UUID, db: Session = Depends(initialized_db)):
    return attachments.list_attachments(db, team_id)


@router.post("/{team_id}/attachments", dependencies=[write], status_code=201)
async def upload_attachment(team_id: UUID, file: UploadFile = File(...), db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    return await attachments.save_attachment(db, team_id, file, user)


@router.get("/{team_id}/attachments/{attachment_id}")
def download_attachment(team_id: UUID, attachment_id: UUID, db: Session = Depends(initialized_db)):
    row = attachments.get_attachment(db, team_id, attachment_id)
    path = attachments.attachment_path(row.storage_name)
    if not path.is_file():
        raise HTTPException(404, "团队附件文件不存在")
    return FileResponse(path, filename=row.original_name, media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.delete("/{team_id}/attachments/{attachment_id}", dependencies=[write], status_code=204)
def remove_attachment(team_id: UUID, attachment_id: UUID, db: Session = Depends(initialized_db), user=Depends(get_current_user)):
    attachments.delete_attachment(db, team_id, attachment_id, user)
    return Response(status_code=204)
