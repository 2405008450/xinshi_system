from test_chat_participant_access import environment,project
from annotation_customer_progress_schemas import CustomerProgressWrite
from annotation_progress_time import business_now

def test_annotator_records_shared_by_entrypoints_and_scoped_by_order(environment):
 db,(owner,*_)=environment
 from annotation_annotator_progress_service import create_progress,list_progress
 from routers.annotation_annotator_progress import AnnotatorProgressResponse
 from annotation_customer_progress_service import list_customer_progress
 parent=project(db,owner,'AP-ANNOTATOR-001');child=project(db,owner,'AP-ANNOTATOR-001.001')
 record=create_progress(db,child.id,CustomerProgressWrite(change_note='人员安排及反馈\n![截图](screenshot://example)',effective_on=business_now()),owner.id)
 result=AnnotatorProgressResponse.model_validate(record)
 assert result.track=='annotator' and result.project_id==child.id
 assert result.effective_on.utcoffset().total_seconds()==28800
 assert list_progress(db,parent.id)==[]
 assert list_progress(db,child.id)[0]['change_note']==result.change_note
 assert list_customer_progress(db,child.id)==[]

def test_uninitialized_annotator_table_does_not_disable_customer_progress(environment):
 db,(owner,*_)=environment
 from annotation_annotator_progress_models import AnnotationAnnotatorProgress
 from annotation_annotator_progress_service import list_progress
 from annotation_customer_progress_service import list_customer_progress
 from fastapi import HTTPException
 import pytest
 row=project(db,owner,'AP-ANNOTATOR-002')
 AnnotationAnnotatorProgress.__table__.drop(db.connection());db.commit()
 with pytest.raises(HTTPException) as result:list_progress(db,row.id)
 assert result.value.status_code==503
 assert list_customer_progress(db,row.id)==[]
