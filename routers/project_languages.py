"""跨项目类型共享语种目录。"""

from difflib import SequenceMatcher
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from database import get_db
from interpretation_models import InterpretationLanguage, InterpretationLanguageAlias
from interpretation_schemas import InterpretationLanguageCreate, InterpretationLanguageResponse
from language_catalog import get_searchable_language_variants, normalize_language_search_text
from models import AppUser
from routers.auth import get_current_user, require_any_permission
from talent_overview_service import get_talent_overview, resolve_overview_for_language, resolve_overview_for_text


router = APIRouter(
    prefix="/projects/languages",
    tags=["project_languages"],
)


class ProjectLanguageResponse(InterpretationLanguageResponse):
    """共享语种及其业务简称；自定义语种没有固定代码或简称。"""

    code: str | None = None
    aliases: list[str] = Field(default_factory=list)
    shortcuts: list[str] = Field(default_factory=list)
    matched_alias: str | None = None
    match_type: str | None = None


class LanguageAliasWrite(BaseModel):
    alias: str = Field(min_length=1, max_length=100)
    alias_type: Literal["zh_alias", "en_name", "abbreviation", "business_shortcut", "historical", "other"] = "other"
    priority: int = Field(default=0, ge=0, le=999)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value):
        return " ".join(value.split())


READ_LANGUAGE_DEPENDENCY = Depends(require_any_permission(
    "projects:read", "projects:write", "consultations:read", "consultations:write",
    "talents:read", "talents:write",
))


@router.get("", response_model=List[ProjectLanguageResponse], dependencies=[READ_LANGUAGE_DEPENDENCY])
@router.get("/", response_model=List[ProjectLanguageResponse], dependencies=[READ_LANGUAGE_DEPENDENCY], include_in_schema=False)
def read_languages(
    include_inactive: bool = False,
    keyword: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=500, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(InterpretationLanguage)
    if not include_inactive:
        query = query.filter(InterpretationLanguage.is_active.is_(True))
    languages = query.order_by(
        InterpretationLanguage.is_custom.asc(), InterpretationLanguage.label.asc()
    ).all()
    variants = {item["label"]: item for item in get_searchable_language_variants()}
    normalized_query = normalize_language_search_text(keyword)
    ranked = []
    for language in languages:
        fallback = variants.get(language.label, {})
        db_aliases = [item.alias for item in language.aliases if item.is_active]
        aliases = list(dict.fromkeys([*db_aliases, *fallback.get("aliases", [])]))
        shortcuts = list(dict.fromkeys([
            *[item.alias for item in language.aliases if item.is_active and item.alias_type in {"business_shortcut", "abbreviation"}],
            *fallback.get("shortcuts", []),
        ]))
        candidates = [
            (language.code or fallback.get("code") or "", "code"),
            (language.name_zh or language.label, "name"),
            (language.name_en or "", "name"),
            (language.short_name_zh or "", "short_name"),
            (language.short_name_en or "", "short_name"),
            *[(value, "alias") for value in aliases],
        ]
        score, matched_alias, match_type = 0.0, None, None
        if normalized_query:
            for candidate, candidate_type in candidates:
                normalized_candidate = normalize_language_search_text(candidate)
                if not normalized_candidate:
                    continue
                if normalized_candidate == normalized_query:
                    candidate_score = 100
                elif normalized_candidate.startswith(normalized_query):
                    candidate_score = 80
                elif normalized_query in normalized_candidate:
                    candidate_score = 60
                elif len(normalized_query) >= 3:
                    candidate_score = SequenceMatcher(None, normalized_query, normalized_candidate).ratio() * 50
                else:
                    candidate_score = 0
                if candidate_score > score:
                    score, matched_alias, match_type = candidate_score, candidate, candidate_type
            if score < 25:
                continue
        ranked.append((score, language.is_custom, language.label, {
            **InterpretationLanguageResponse.model_validate(language).model_dump(),
            "code": language.code or fallback.get("code"),
            "aliases": aliases,
            "shortcuts": shortcuts,
            "matched_alias": matched_alias if normalized_query else None,
            "match_type": match_type if normalized_query else None,
        }))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in ranked[:limit]]


@router.post(
    "", response_model=InterpretationLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write", "consultations:write", "talents:write"))],
)
@router.post(
    "/", response_model=InterpretationLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write", "consultations:write", "talents:write"))],
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
    overview_data = get_talent_overview(db)
    overview_row, _ = resolve_overview_for_text(payload.label, data=overview_data)
    if overview_row:
        candidates = (
            db.query(InterpretationLanguage)
            .options(selectinload(InterpretationLanguage.aliases))
            .filter(InterpretationLanguage.is_active.is_(True))
            .all()
        )
        mapped = next((
            language for language in candidates
            if (
                language.talent_overview_key == overview_row["overview_key"]
                or (resolve_overview_for_language(language, data=overview_data)[0] or {}).get("overview_key")
                == overview_row["overview_key"]
            )
        ), None)
        if mapped:
            raise HTTPException(status_code=409, detail={
                "code": "language_alias_conflict",
                "message": f"该名称对应已有规范语种“{overview_row['language']}”，请直接选择已有语种",
                "canonical_label": overview_row["language"],
                "existing_language_id": str(mapped.id),
                "existing_language_label": mapped.label,
            })
    language = InterpretationLanguage(
        **payload.model_dump(), is_custom=True, created_by=current_user.id
    )
    db.add(language)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该语种已存在")
    db.refresh(language)
    return language


@router.post(
    "/{language_id}/aliases", response_model=ProjectLanguageResponse,
    dependencies=[Depends(require_any_permission("projects:write", "consultations:write", "talents:write"))],
)
def create_language_alias(
    language_id: str,
    payload: LanguageAliasWrite,
    db: Session = Depends(get_db),
):
    language = db.query(InterpretationLanguage).filter(InterpretationLanguage.id == language_id).first()
    if not language:
        raise HTTPException(status_code=404, detail="语种不存在")
    normalized = normalize_language_search_text(payload.alias)
    existing = next((item for item in language.aliases if item.normalized_alias == normalized), None)
    if existing:
        existing.alias = payload.alias
        existing.alias_type = payload.alias_type
        existing.priority = payload.priority
        existing.is_active = True
    else:
        language.aliases.append(InterpretationLanguageAlias(
            **payload.model_dump(), normalized_alias=normalized,
        ))
    db.commit()
    db.refresh(language)
    return read_languages(keyword=language.label, limit=1, db=db)[0]


@router.delete(
    "/{language_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_permission("projects:write", "consultations:write", "talents:write"))],
)
def delete_language_alias(language_id: str, alias_id: str, db: Session = Depends(get_db)):
    row = db.query(InterpretationLanguageAlias).filter(
        InterpretationLanguageAlias.id == alias_id,
        InterpretationLanguageAlias.language_id == language_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="语言别名不存在")
    db.delete(row)
    db.commit()
