"""跨项目类型共享语种目录。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from interpretation_models import InterpretationLanguage
from interpretation_schemas import InterpretationLanguageCreate, InterpretationLanguageResponse
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/projects/languages",
    tags=["project_languages"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


@router.get("", response_model=List[InterpretationLanguageResponse])
@router.get("/", response_model=List[InterpretationLanguageResponse], include_in_schema=False)
def read_languages(db: Session = Depends(get_db)):
    return db.query(InterpretationLanguage).order_by(
        InterpretationLanguage.is_custom.asc(), InterpretationLanguage.label.asc()
    ).all()


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
