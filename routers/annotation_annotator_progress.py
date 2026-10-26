from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission
from annotation_customer_progress_schemas import CustomerProgressWrite,CustomerProgressResponse
from annotation_annotator_progress_service import list_progress,create_progress

class AnnotatorProgressResponse(CustomerProgressResponse):
    track: Literal['annotator']='annotator'

router=APIRouter(prefix='/projects/annotation',tags=['annotation_annotator_progress'])

@router.get('/{project_id}/annotator-progress',response_model=list[AnnotatorProgressResponse],dependencies=[Depends(require_any_permission('projects:read'))])
def read(project_id:UUID,db:Session=Depends(get_db)):
    return list_progress(db,project_id)

@router.post('/{project_id}/annotator-progress',response_model=AnnotatorProgressResponse,dependencies=[Depends(require_any_permission('projects:write'))])
def create(project_id:UUID,payload:CustomerProgressWrite,db:Session=Depends(get_db),user:AppUser=Depends(get_current_user)):
    return create_progress(db,project_id,payload,user.id)
