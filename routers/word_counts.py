"""多维字数统计统一接口。"""
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission
from word_count_schemas import WordCountMatrixPatch, WordCountMatrixResponse
from word_count_service import get_word_count_matrix, patch_word_count_matrix


router = APIRouter(
    prefix="/word-count-matrices",
    tags=["word_count_matrices"],
    dependencies=[Depends(require_any_permission("projects:read", "projects:write"))],
)


@router.get("/{entity_type}/{entity_id}", response_model=WordCountMatrixResponse)
def read_word_count_matrix(
    entity_type: Literal["project", "suborder"],
    entity_id: UUID,
    dispatch_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    return get_word_count_matrix(db, entity_type, entity_id, dispatch_id)


@router.patch("/{entity_type}/{entity_id}", response_model=WordCountMatrixResponse)
def update_word_count_matrix(
    entity_type: Literal["project", "suborder"],
    entity_id: UUID,
    payload: WordCountMatrixPatch,
    dispatch_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return patch_word_count_matrix(
        db,
        entity_type,
        entity_id,
        payload,
        updated_by=current_user.id,
        dispatch_id=dispatch_id,
    )
