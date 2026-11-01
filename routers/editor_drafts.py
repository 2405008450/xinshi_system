from fastapi import APIRouter,Depends,Query
from database import get_db
from routers.auth import get_current_user
import editor_drafts as service

router=APIRouter(prefix='/editor-drafts',tags=['editor-drafts'])


@router.get('')
def read_draft(namespace:str=Query(min_length=1,max_length=80),key:str=Query(min_length=1,max_length=220),db=Depends(get_db),user=Depends(get_current_user)):
    return service.read(db,user,namespace,key)


@router.post('/batch')
def save_drafts(payload:service.DraftBatch,db=Depends(get_db),user=Depends(get_current_user)):
    return service.save_batch(db,user,payload.drafts)
