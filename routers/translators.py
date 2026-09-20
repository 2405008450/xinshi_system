from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    count_translators, get_translator, get_translators,
    create_translator, update_translator, delete_translator
)
from schemas import TranslatorCreate, TranslatorUpdate, TranslatorResponse
from routers.auth import get_current_user, require_permission
from talent_privacy import (
    LEGACY_TRANSLATOR_CONTACT_FIELDS,
    can_view_talent_contacts,
    has_contact_values,
    preserve_contact_fields,
    serialize_with_contact_access,
)

router = APIRouter(
    prefix="/translators",
    tags=["translators"],
    dependencies=[Depends(get_current_user)],
)
translator_write_dependencies = [Depends(require_permission("translators:write"))]

@router.post(
    "/", response_model=TranslatorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=translator_write_dependencies,
)
def create_translator_endpoint(
    translator: TranslatorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    if not contacts_visible and has_contact_values(
        translator, LEGACY_TRANSLATOR_CONTACT_FIELDS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以录入译员联系方式",
        )
    created = create_translator(db=db, translator=translator)
    return serialize_with_contact_access(
        created, TranslatorResponse, LEGACY_TRANSLATOR_CONTACT_FIELDS,
        contacts_visible=contacts_visible,
    )

@router.get("/", response_model=List[TranslatorResponse])
def read_translators(
    skip: int = 0,
    limit: int = 100,
    capability_type: Optional[str] = Query(None),
    translator_code: Optional[str] = Query(None),
    translator_name: Optional[str] = Query(None),
    cooperation_type: Optional[str] = Query(None),
    languages: Optional[str] = Query(None),
    translation_type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    available_time_slot: Optional[str] = Query(None),
    domain_keyword: Optional[str] = Query(None),
    contact_keyword: Optional[str] = Query(None),
    quality_score: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    nationality: Optional[str] = Query(None),
    can_cloud_edit: Optional[bool] = Query(None),
    can_revision: Optional[bool] = Query(None),
    default_priority_min: Optional[int] = Query(None, ge=0),
    default_priority_max: Optional[int] = Query(None, ge=0),
    daily_word_capacity_min: Optional[int] = Query(None, ge=0),
    daily_word_capacity_max: Optional[int] = Query(None, ge=0),
    stale_only: bool = Query(False),
    stale_days: int = Query(4, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    if contact_keyword and not contacts_visible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="联系方式搜索仅超级管理员可用",
        )
    translators = get_translators(
        db,
        skip=skip,
        limit=limit,
        capability_type=capability_type,
        translator_code=translator_code,
        translator_name=translator_name,
        cooperation_type=cooperation_type,
        languages=languages,
        translation_type=translation_type,
        direction=direction,
        status=status,
        available_time_slot=available_time_slot,
        domain_keyword=domain_keyword,
        contact_keyword=contact_keyword,
        quality_score=quality_score,
        gender=gender,
        nationality=nationality,
        can_cloud_edit=can_cloud_edit,
        can_revision=can_revision,
        default_priority_min=default_priority_min,
        default_priority_max=default_priority_max,
        daily_word_capacity_min=daily_word_capacity_min,
        daily_word_capacity_max=daily_word_capacity_max,
        stale_only=stale_only,
        stale_days=stale_days,
    )
    return [
        serialize_with_contact_access(
            item, TranslatorResponse, LEGACY_TRANSLATOR_CONTACT_FIELDS,
            contacts_visible=contacts_visible,
        )
        for item in translators
    ]

@router.get("/count")
def read_translator_count(
    capability_type: Optional[str] = Query(None),
    translator_code: Optional[str] = Query(None),
    translator_name: Optional[str] = Query(None),
    cooperation_type: Optional[str] = Query(None),
    languages: Optional[str] = Query(None),
    translation_type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    available_time_slot: Optional[str] = Query(None),
    domain_keyword: Optional[str] = Query(None),
    contact_keyword: Optional[str] = Query(None),
    quality_score: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    nationality: Optional[str] = Query(None),
    can_cloud_edit: Optional[bool] = Query(None),
    can_revision: Optional[bool] = Query(None),
    default_priority_min: Optional[int] = Query(None, ge=0),
    default_priority_max: Optional[int] = Query(None, ge=0),
    daily_word_capacity_min: Optional[int] = Query(None, ge=0),
    daily_word_capacity_max: Optional[int] = Query(None, ge=0),
    stale_only: bool = Query(False),
    stale_days: int = Query(4, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if contact_keyword and not can_view_talent_contacts(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="联系方式搜索仅超级管理员可用",
        )
    return {
        "total": count_translators(
            db,
            capability_type=capability_type,
            translator_code=translator_code,
            translator_name=translator_name,
            cooperation_type=cooperation_type,
            languages=languages,
            translation_type=translation_type,
            direction=direction,
            status=status,
            available_time_slot=available_time_slot,
            domain_keyword=domain_keyword,
            contact_keyword=contact_keyword,
            quality_score=quality_score,
            gender=gender,
            nationality=nationality,
            can_cloud_edit=can_cloud_edit,
            can_revision=can_revision,
            default_priority_min=default_priority_min,
            default_priority_max=default_priority_max,
            daily_word_capacity_min=daily_word_capacity_min,
            daily_word_capacity_max=daily_word_capacity_max,
            stale_only=stale_only,
            stale_days=stale_days,
        )
    }

@router.get("/{translator_id}", response_model=TranslatorResponse)
def read_translator(
    translator_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db_translator = get_translator(db, translator_id=translator_id)
    if not db_translator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="译员不存在")
    return serialize_with_contact_access(
        db_translator, TranslatorResponse, LEGACY_TRANSLATOR_CONTACT_FIELDS,
        contacts_visible=can_view_talent_contacts(db, current_user),
    )

@router.put(
    "/{translator_id}", response_model=TranslatorResponse,
    dependencies=translator_write_dependencies,
)
def update_translator_endpoint(
    translator_id: UUID,
    translator_update: TranslatorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    if not contacts_visible:
        existing = get_translator(db, translator_id=translator_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="译员不存在"
            )
        translator_update = preserve_contact_fields(
            translator_update, existing, LEGACY_TRANSLATOR_CONTACT_FIELDS
        )
    db_translator = update_translator(db, translator_id=translator_id, translator_update=translator_update)
    if not db_translator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="译员不存在")
    return serialize_with_contact_access(
        db_translator, TranslatorResponse, LEGACY_TRANSLATOR_CONTACT_FIELDS,
        contacts_visible=contacts_visible,
    )

@router.delete(
    "/{translator_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=translator_write_dependencies,
)
def delete_translator_endpoint(translator_id: UUID, db: Session = Depends(get_db)):
    success = delete_translator(db, translator_id=translator_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="译员不存在")
    return None
