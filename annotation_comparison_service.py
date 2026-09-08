"""标注项目比较组查询与维护服务。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from annotation_comparison_models import (
    AnnotationProjectComparisonGroup,
    AnnotationProjectComparisonMember,
)
from annotation_comparison_schemas import (
    AnnotationComparisonGroupCreate,
    AnnotationComparisonGroupUpdate,
)
from annotation_models import AnnotationProject
from concurrency import assert_fresh


def _query(db: Session):
    return db.query(AnnotationProjectComparisonGroup).options(
        joinedload(AnnotationProjectComparisonGroup.creator),
        selectinload(AnnotationProjectComparisonGroup.members).joinedload(
            AnnotationProjectComparisonMember.project
        ),
    )


def _project_manager_name(project: AnnotationProject) -> str | None:
    assignment = next(
        (item for item in project.role_assignments if item["role_code"] == "project_manager"),
        None,
    )
    return assignment["assignee_name"] if assignment else None


def _preview(member: AnnotationProjectComparisonMember) -> dict:
    project = member.project
    return {
        "project_id": member.project_id,
        "sequence_no": member.sequence_no,
        "order_no": project.order_no,
        "project_name": project.project_name,
    }


def serialize_group(group: AnnotationProjectComparisonGroup, *, detail: bool = False) -> dict:
    members = sorted(group.members, key=lambda item: item.sequence_no)
    payload = {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_by": group.created_by,
        "created_by_name": group.created_by_name,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "member_count": len(members),
        "members": [_preview(member) for member in members],
    }
    if detail:
        payload["projects"] = [
            {
                **_preview(member),
                "client_short_name": member.project.client_short_name,
                "client_full_name": member.project.client_full_name,
                "project_types": member.project.project_types or [],
                "language_items_display": member.project.language_items_display,
                "customer_price_summary": member.project.customer_price_summary,
                "client_manager_name": member.project.client_manager_name,
                "project_manager_name": _project_manager_name(member.project),
                "project_status": member.project.project_status,
                "potential_demand": member.project.potential_demand,
            }
            for member in members
        ]
    return payload


def list_comparison_groups(
    db: Session, *, skip: int = 0, limit: int = 20, keyword: str | None = None
) -> list[dict]:
    query = _query(db)
    normalized = str(keyword or "").strip()
    if normalized:
        pattern = f"%{normalized}%"
        query = query.filter(or_(
            AnnotationProjectComparisonGroup.name.ilike(pattern),
            AnnotationProjectComparisonGroup.description.ilike(pattern),
        ))
    rows = query.order_by(
        AnnotationProjectComparisonGroup.created_at.desc(),
        AnnotationProjectComparisonGroup.id.desc(),
    ).offset(skip).limit(limit).all()
    return [serialize_group(row) for row in rows]


def count_comparison_groups(db: Session, *, keyword: str | None = None) -> int:
    query = db.query(AnnotationProjectComparisonGroup)
    normalized = str(keyword or "").strip()
    if normalized:
        pattern = f"%{normalized}%"
        query = query.filter(or_(
            AnnotationProjectComparisonGroup.name.ilike(pattern),
            AnnotationProjectComparisonGroup.description.ilike(pattern),
        ))
    return query.count()


def get_comparison_group(db: Session, group_id: UUID) -> dict | None:
    row = _query(db).filter(AnnotationProjectComparisonGroup.id == group_id).first()
    return serialize_group(row, detail=True) if row else None


def _validated_projects(db: Session, project_ids: list[UUID]) -> list[AnnotationProject]:
    rows = db.query(AnnotationProject).filter(AnnotationProject.id.in_(project_ids)).all()
    by_id = {row.id: row for row in rows}
    missing = [project_id for project_id in project_ids if project_id not in by_id]
    if missing:
        raise ValueError("所选标注项目不存在或已被删除")
    return [by_id[project_id] for project_id in project_ids]


def _replace_members(
    db: Session, group: AnnotationProjectComparisonGroup, project_ids: list[UUID]
) -> None:
    _validated_projects(db, project_ids)
    group.members.clear()
    db.flush()
    group.members = [
        AnnotationProjectComparisonMember(project_id=project_id, sequence_no=index)
        for index, project_id in enumerate(project_ids, start=1)
    ]


def create_comparison_group(
    db: Session, payload: AnnotationComparisonGroupCreate, creator_id: UUID
) -> dict:
    row = AnnotationProjectComparisonGroup(
        name=payload.name,
        description=payload.description,
        created_by=creator_id,
    )
    db.add(row)
    _replace_members(db, row, payload.project_ids)
    db.commit()
    return get_comparison_group(db, row.id)


def update_comparison_group(
    db: Session, group_id: UUID, payload: AnnotationComparisonGroupUpdate
) -> dict | None:
    row = db.get(AnnotationProjectComparisonGroup, group_id)
    if not row:
        return None
    assert_fresh(row, payload.expected_updated_at)
    if payload.name is not None:
        row.name = payload.name
    if payload.description is not None:
        row.description = payload.description
    if payload.project_ids is not None:
        _replace_members(db, row, payload.project_ids)
    row.updated_at = datetime.now()
    db.commit()
    return get_comparison_group(db, row.id)


def delete_comparison_group(db: Session, group_id: UUID) -> bool:
    row = db.get(AnnotationProjectComparisonGroup, group_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
