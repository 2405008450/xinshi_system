"""跨项目类型共享语种目录。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from interpretation_models import InterpretationLanguage
from interpretation_schemas import InterpretationLanguageCreate, InterpretationLanguageResponse
from language_catalog import get_searchable_language_variants
from models import AppUser
from routers.auth import get_current_user, require_any_permission


router = APIRouter(
    prefix="/projects/languages",
    tags=["project_languages"],
)


class ProjectLanguageResponse(InterpretationLanguageResponse):
    """共享语种及其业务简称；自定义语种没有固定代码或简称。"""

    code: str | None = None
    aliases: list[str] = Field(default_factory=list)
    shortcuts: list[str] = Field(default_factory=list)


READ_LANGUAGE_DEPENDENCY = Depends(require_any_permission(
    "projects:read", "projects:write", "consultations:read", "consultations:write"
))


@router.get("", response_model=List[ProjectLanguageResponse], dependencies=[READ_LANGUAGE_DEPENDENCY])
@router.get("/", response_model=List[ProjectLanguageResponse], dependencies=[READ_LANGUAGE_DEPENDENCY], include_in_schema=False)
def read_languages(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(InterpretationLanguage)
    if not include_inactive:
        query = query.filter(InterpretationLanguage.is_active.is_(True))
    languages = query.order_by(
        InterpretationLanguage.is_custom.asc(), InterpretationLanguage.label.asc()
    ).all()
    variants = {item["label"]: item for item in get_searchable_language_variants()}
    return [
        {
            **InterpretationLanguageResponse.model_validate(language).model_dump(),
            "code": variants.get(language.label, {}).get("code"),
            "aliases": variants.get(language.label, {}).get("aliases", []),
            "shortcuts": variants.get(language.label, {}).get("shortcuts", []),
        }
        for language in languages
    ]


@router.post(
    "", response_model=InterpretationLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
@router.post(
    "/", response_model=InterpretationLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
    include_in_schema=False,
)
def create_language(
    payload: InterpretationLanguageCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    existing = db.query(InterpretationLanguage).filter(
        func.lower(func.trim(InterpretationLanguage.label)) == payload.label.lower()
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该语种已存在")
    language = InterpretationLanguage(
        label=payload.label, is_custom=True, created_by=current_user.id
    )
    db.add(language)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该语种已存在")
    db.refresh(language)
    return language
