"""招聘项目接口。"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import AppUser
from recruitment_models import RecruitmentCandidate, RecruitmentProjectProgress
from recruitment_schemas import (
    RecruitmentCandidateCreate,
    RecruitmentCandidateCommunicationCreate,
    RecruitmentCandidateCommunicationResponse,
    RecruitmentCandidateCommunicationUpdate,
    RecruitmentCandidatePatch,
    RecruitmentCandidateResponse,
    RecruitmentCandidateUpdate,
    RecruitmentNamePreviewRequest,
    RecruitmentNamePreviewResponse,
    RecruitmentProgressCreate,
    RecruitmentProgressResponse,
    RecruitmentProjectCreate,
    RecruitmentProjectResponse,
    RecruitmentProjectStatusUpdate,
    RecruitmentProjectUpdate,
    RecruitmentResumeSourceCreate,
    RecruitmentResumeSourceResponse,
)
from recruitment_service import (
    add_manual_progress,
    count_recruitment_projects,
    create_candidate,
    create_candidate_communication,
    create_or_get_resume_source,
    create_recruitment_project,
    delete_candidate,
    delete_recruitment_project,
    get_recruitment_project,
    get_recruitment_projects,
    get_resume_sources,
    patch_candidate,
    preview_recruitment_project_name,
    update_candidate,
    update_candidate_communication,
    update_recruitment_project,
    update_recruitment_project_status,
)
from resource_service import TalentDuplicateError
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/projects/recruitment",
    tags=["recruitment_projects"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


def _filters(
    keyword=None,
    project_status=None,
    client_id=None,
    sub_client_id=None,
    language_id=None,
    client_manager_id=None,
    employment_date_start=None,
    employment_date_end=None,
    target_onboard_date_start=None,
    target_onboard_date_end=None,
    created_date_start=None,
    created_date_end=None,
):
    return dict(
        keyword=keyword,
        project_status=project_status,
        client_id=client_id,
        sub_client_id=sub_client_id,
        language_id=language_id,
        client_manager_id=client_manager_id,
        employment_date_start=employment_date_start,
        employment_date_end=employment_date_end,
        target_onboard_date_start=target_onboard_date_start,
        target_onboard_date_end=target_onboard_date_end,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
    )


@router.get("/", response_model=List[RecruitmentProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    language_id: Optional[UUID] = None,
    client_manager_id: Optional[UUID] = None,
    employment_date_start: Optional[date] = None,
    employment_date_end: Optional[date] = None,
    target_onboard_date_start: Optional[date] = None,
    target_onboard_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return get_recruitment_projects(
        db, skip=skip, limit=limit,
        **_filters(
            keyword=keyword,
            project_status=project_status,
            client_id=client_id,
            sub_client_id=sub_client_id,
            language_id=language_id,
            client_manager_id=client_manager_id,
            employment_date_start=employment_date_start,
            employment_date_end=employment_date_end,
            target_onboard_date_start=target_onboard_date_start,
            target_onboard_date_end=target_onboard_date_end,
            created_date_start=created_date_start,
            created_date_end=created_date_end,
        ),
    )


@router.get("/count")
def read_project_count(
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    language_id: Optional[UUID] = None,
    client_manager_id: Optional[UUID] = None,
    employment_date_start: Optional[date] = None,
    employment_date_end: Optional[date] = None,
    target_onboard_date_start: Optional[date] = None,
    target_onboard_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return {"total": count_recruitment_projects(
        db, **_filters(
            keyword=keyword,
            project_status=project_status,
            client_id=client_id,
            sub_client_id=sub_client_id,
            language_id=language_id,
            client_manager_id=client_manager_id,
            employment_date_start=employment_date_start,
            employment_date_end=employment_date_end,
            target_onboard_date_start=target_onboard_date_start,
            target_onboard_date_end=target_onboard_date_end,
            created_date_start=created_date_start,
            created_date_end=created_date_end,
        )
    )}


@router.post("/name-preview", response_model=RecruitmentNamePreviewResponse)
def preview_name(payload: RecruitmentNamePreviewRequest, db: Session = Depends(get_db)):
    try:
        return {"project_name": preview_recruitment_project_name(db, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/resume-sources", response_model=List[RecruitmentResumeSourceResponse],
    dependencies=[Depends(require_any_permission("recruitment_talents:read"))],
)
def read_resume_sources(db: Session = Depends(get_db)):
    return get_resume_sources(db)


@router.post(
    "/resume-sources", response_model=RecruitmentResumeSourceResponse,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def create_resume_source(
    payload: RecruitmentResumeSourceCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return create_or_get_resume_source(db, payload.label, current_user.id)


@router.post(
    "/", response_model=RecruitmentProjectResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_project(
    payload: RecruitmentProjectCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return create_recruitment_project(db, payload, current_user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/candidate/{candidate_id}", response_model=RecruitmentCandidateResponse,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def update_candidate_endpoint(
    candidate_id: UUID, payload: RecruitmentCandidateUpdate, db: Session = Depends(get_db)
):
    try:
        candidate = update_candidate(db, candidate_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return candidate


@router.patch(
    "/candidate/{candidate_id}", response_model=RecruitmentCandidateResponse,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def patch_candidate_endpoint(
    candidate_id: UUID, payload: RecruitmentCandidatePatch, db: Session = Depends(get_db)
):
    try:
        candidate = patch_candidate(db, candidate_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return candidate


@router.post(
    "/candidate/{candidate_id}/communications",
    response_model=RecruitmentCandidateCommunicationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def create_candidate_communication_endpoint(
    candidate_id: UUID,
    payload: RecruitmentCandidateCommunicationCreate,
    db: Session = Depends(get_db),
):
    record = create_candidate_communication(db, candidate_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return record


@router.put(
    "/candidate/communication/{communication_id}",
    response_model=RecruitmentCandidateCommunicationResponse,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def update_candidate_communication_endpoint(
    communication_id: UUID,
    payload: RecruitmentCandidateCommunicationUpdate,
    db: Session = Depends(get_db),
):
    record = update_candidate_communication(db, communication_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="沟通记录不存在")
    return record


@router.delete(
    "/candidate/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def delete_candidate_endpoint(candidate_id: UUID, db: Session = Depends(get_db)):
    if not delete_candidate(db, candidate_id):
        raise HTTPException(status_code=404, detail="候选人不存在")
    return None


@router.get("/{project_id}/progress", response_model=List[RecruitmentProgressResponse])
def read_progress(project_id: UUID, db: Session = Depends(get_db)):
    if not get_recruitment_project(db, project_id):
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return (
        db.query(RecruitmentProjectProgress)
        .options(selectinload(RecruitmentProjectProgress.operator))
        .filter(RecruitmentProjectProgress.project_id == project_id)
        .order_by(RecruitmentProjectProgress.occurred_at.desc())
        .all()
    )


@router.post(
    "/{project_id}/progress", response_model=RecruitmentProgressResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_progress(
    project_id: UUID,
    payload: RecruitmentProgressCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    record = add_manual_progress(db, project_id, payload, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return record


@router.get(
    "/{project_id}/candidates", response_model=List[RecruitmentCandidateResponse],
    dependencies=[Depends(require_any_permission("recruitment_talents:read"))],
)
def read_candidates(project_id: UUID, db: Session = Depends(get_db)):
    if not get_recruitment_project(db, project_id):
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return (
        db.query(RecruitmentCandidate)
        .options(
            selectinload(RecruitmentCandidate.owner),
            selectinload(RecruitmentCandidate.resume_source),
            selectinload(RecruitmentCandidate.communications),
            selectinload(RecruitmentCandidate.interviews),
        )
        .filter(RecruitmentCandidate.project_id == project_id)
        .order_by(RecruitmentCandidate.created_at.desc())
        .all()
    )


@router.post(
    "/{project_id}/candidates", response_model=RecruitmentCandidateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("recruitment_talents:write"))],
)
def create_candidate_endpoint(
    project_id: UUID, payload: RecruitmentCandidateCreate, db: Session = Depends(get_db)
):
    try:
        candidate = create_candidate(db, project_id, payload)
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_talent", "message": str(exc), "duplicates": exc.duplicates,
        })
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not candidate:
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return candidate


@router.get("/{project_id}", response_model=RecruitmentProjectResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    project = get_recruitment_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return project


@router.put(
    "/{project_id}", response_model=RecruitmentProjectResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project(
    project_id: UUID,
    payload: RecruitmentProjectUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        project = update_recruitment_project(db, project_id, payload, current_user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not project:
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return project


@router.patch(
    "/{project_id}/status", response_model=RecruitmentProjectResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_status(
    project_id: UUID,
    payload: RecruitmentProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    project = update_recruitment_project_status(
        db, project_id, payload.project_status, current_user.id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return project


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    if not delete_recruitment_project(db, project_id):
        raise HTTPException(status_code=404, detail="招聘项目不存在")
    return None
