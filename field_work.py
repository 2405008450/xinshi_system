"""员工外勤记录和客户管理视图共用的数据。"""
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, LargeBinary, String, Text, Uuid, or_, select
from sqlalchemy.orm import Mapped, mapped_column
from typing import Annotated

from chat_time import api_time, now
from models import AppUser, Base, Client
from permission_service import user_has_permission
from search_matching import keyword_ilike, keyword_or


CATEGORIES = [
    {"value": "customer", "label": "客户类", "children": [
        {"value": "visit", "label": "拜访客户"},
        {"value": "bidding", "label": "招投标", "children": [
            {"value": "tender", "label": "正式投标"},
            {"value": "accompany", "label": "陪标"},
        ]},
    ]},
    {"value": "administration", "label": "行政类"},
    {"value": "bank", "label": "银行类"},
    {"value": "supplier", "label": "供应商走访"},
    {"value": "site", "label": "项目现场服务"},
    {"value": "recruitment", "label": "招聘外勤"},
    {"value": "event", "label": "展会与会议"},
    {"value": "delivery", "label": "文件与物资交接"},
]


def leaf_labels(options, prefix=(), labels=()):
    for option in options:
        path = (*prefix, option["value"])
        names = (*labels, option["label"])
        if option.get("children"):
            yield from leaf_labels(option["children"], path, names)
        else:
            yield path, " / ".join(names)


TYPE_LABELS = dict(leaf_labels(CATEGORIES))
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
CustomerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class FieldWork(Base):
    __tablename__ = "attendance_field_work"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_attendance_field_work_time"),
        CheckConstraint("revision >= 1", name="ck_attendance_field_work_revision"),
        Index("ix_attendance_field_work_owner_start", "user_id", "start_at"),
        Index("ix_attendance_field_work_category_start", "category", "start_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(24))
    type_path: Mapped[list] = mapped_column(JSON)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(255))
    companions: Mapped[list] = mapped_column(JSON)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("client.id", ondelete="SET NULL"))
    client_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str] = mapped_column(Text)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    photo_type: Mapped[str | None] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FieldWorkWrite(BaseModel):
    id: UUID
    revision: int = Field(default=0, ge=0)
    type_path: list[str] = Field(min_length=1, max_length=3)
    start_at: AwareDatetime
    end_at: AwareDatetime
    location: Location
    companion_ids: list[UUID] = Field(default_factory=list, max_length=200)
    client_id: UUID | None = None
    client_name: CustomerName | None = None
    notes: str = Field(default="", max_length=4000)
    remove_photo: bool = False

    @model_validator(mode="after")
    def validate_fields(self):
        if tuple(self.type_path) not in TYPE_LABELS:
            raise ValueError("请选择有效的外勤类型")
        if self.end_at <= self.start_at:
            raise ValueError("结束时间必须晚于开始时间")
        if self.type_path[0] == "customer" and not (self.client_id or self.client_name):
            raise ValueError("请填写客户名称")
        return self


def people_query(db):
    return db.query(AppUser.id, AppUser.full_name, AppUser.username).filter(
        AppUser.is_active.is_(True), AppUser.is_deleted.is_(False),
    )


def person_option(row):
    return {"id": str(row.id), "name": row.full_name or row.username, "username": row.username}


def view(row, owner_name):
    return {
        "id": row.id, "revision": row.revision, "owner_name": owner_name,
        "type_path": row.type_path, "type_label": TYPE_LABELS.get(tuple(row.type_path), row.category),
        "start_at": api_time(row.start_at), "end_at": api_time(row.end_at),
        "location": row.location, "companions": row.companions,
        "client_id": row.client_id, "client_name": row.client_name,
        "notes": row.notes, "has_photo": bool(row.photo_type),
    }


def list_records(db, user, *, customer_view=False, keyword="", page=1, limit=20):
    query = db.query(FieldWork, AppUser.full_name, AppUser.username).join(AppUser, AppUser.id == FieldWork.user_id)
    query = query.filter(FieldWork.category == "customer" if customer_view else FieldWork.user_id == user.id)
    if keyword.strip():
        query = query.filter(keyword_or(lambda part: or_(*(
            keyword_ilike(column, part) for column in (
                FieldWork.client_name, FieldWork.location, FieldWork.notes, AppUser.full_name, AppUser.username,
            )
        )), f"%{keyword.strip()}%"))
    total = query.count()
    rows = query.order_by(FieldWork.start_at.desc(), FieldWork.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [view(row, name or username) for row, name, username in rows], "total": total}


def save_record(db, user, payload, image=None):
    # 锁定同一员工的写入，确保重复提交同一新增记录只创建一次。
    db.execute(select(AppUser.id).where(AppUser.id == user.id).with_for_update()).scalar_one()
    row = db.get(FieldWork, payload.id)
    if row and row.user_id != user.id:
        raise HTTPException(404, "外勤记录不存在")
    if row and payload.revision == 0:
        return view(row, user.full_name or user.username)
    if (row and row.revision != payload.revision) or (not row and payload.revision):
        raise HTTPException(409, "外勤记录已更新，请刷新后重新编辑")

    existing_people = {UUID(person["id"]): person for person in row.companions} if row else {}
    ids = list(dict.fromkeys(payload.companion_ids))
    if user.id in ids:
        raise HTTPException(422, "陪同人不能包含本人")
    people = {person.id: person_option(person) for person in people_query(db).filter(AppUser.id.in_(ids)).all()}
    if any(uid not in people and uid not in existing_people for uid in ids):
        raise HTTPException(422, "部分陪同人已不可选，请重新选择")

    category = payload.type_path[0]
    client_id, client_name = None, None
    if category == "customer":
        if payload.client_id:
            if (not row or row.client_id != payload.client_id) and not (
                user_has_permission(db, user.id, "clients:read")
                or user_has_permission(db, user.id, "clients:write")
            ):
                raise HTTPException(403, "无权关联客户档案，请直接填写客户名称")
            client = db.get(Client, payload.client_id)
            if not client:
                raise HTTPException(422, "客户已不存在，请重新选择")
            client_id, client_name = client.id, client.client_name
        else:
            client_name = payload.client_name

    if row is None:
        row = FieldWork(id=payload.id, user_id=user.id, revision=1)
        db.add(row)
    else:
        row.revision += 1
    row.category = category
    row.type_path = payload.type_path
    row.start_at = api_time(payload.start_at)
    row.end_at = api_time(payload.end_at)
    row.location = payload.location
    row.companions = [people.get(uid) or existing_people[uid] for uid in ids]
    row.client_id, row.client_name = client_id, client_name
    row.notes = payload.notes.strip()
    row.updated_at = now()
    if image:
        row.photo, row.photo_type = image
    elif payload.remove_photo:
        row.photo, row.photo_type = None, None
    result = view(row, user.full_name or user.username)
    db.commit()
    return result
