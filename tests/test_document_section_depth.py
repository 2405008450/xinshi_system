import pytest
from uuid import uuid4
from sqlalchemy import event
from test_chat_participant_access import environment
from annotation_notice_schemas import AnnotationNoticeSectionCreate

@pytest.mark.parametrize('family',['company','annotation','translation','interpretation','recruitment'])
def test_three_levels_create_search_and_reject_fourth(environment,monkeypatch,family):
 db,_=environment
 if family=='company':
  import company_management_service as svc
  from company_management_models import CompanyManagementSection as Model
  create=lambda payload:svc.create_company_management_section(db,payload)
  tree=lambda:svc.list_company_management_tree(db)
  search=lambda:svc.search_company_management_sections(db,'末级')
 elif family=='annotation':
  import annotation_notice_service as svc
  from annotation_notice_models import AnnotationNoticeSection as Model
  monkeypatch.setattr(svc,'ensure_annotation_notice_sections',lambda db:None)
  create=lambda payload:svc.create_annotation_notice_section(db,payload)
  tree=lambda:svc.list_annotation_notice_tree(db)
  search=lambda:svc.search_annotation_notice_sections(db,'末级')
 else:
  import project_notice_service as svc
  from project_notice_models import ProjectNoticeSection as Model
  monkeypatch.setattr(svc,'_lock_structure',lambda *a:None)
  create=lambda payload:svc.create_section(db,family,payload)
  tree=lambda:svc.list_tree(db,family)
  search=lambda:svc.search_sections(db,family,'末级')
 def assign_id(mapper,connection,target):
  if target.id is None:target.id=uuid4()
 event.listen(Model,'before_insert',assign_id)
 try:
  root=create(AnnotationNoticeSectionCreate(title='一级'))
  second=create(AnnotationNoticeSectionCreate(title='二级',parent_id=root['id']))
  third=create(AnnotationNoticeSectionCreate(title='末级',parent_id=second['id']))
  assert tree()[0]['children'][0]['children'][0]['id']==third['id']
  assert search()['items'][0]['breadcrumb']=='一级 / 二级 / 末级'
  from annotation_notice_schemas import AnnotationNoticeReorder
  payload=AnnotationNoticeReorder(placements=[dict(id=row.id,parent_id=row.parent_id,sort_order=row.sort_order,expected_structure_updated_at=row.structure_updated_at) for row in db.query(Model).all()])
  if family=='company':result=svc.reorder_company_management_sections(db,payload)
  elif family=='annotation':result=svc.reorder_annotation_notice_sections(db,payload)
  else:result=svc.reorder_sections(db,family,payload)
  assert result[0]['children'][0]['children'][0]['id']==third['id']
  with pytest.raises(ValueError,match='三级'):
   create(AnnotationNoticeSectionCreate(title='第四级',parent_id=third['id']))
 finally:event.remove(Model,'before_insert',assign_id)


def test_depth_validation_rejects_cycles_and_fourth_level():
 from types import SimpleNamespace
 from document_section_tree import validate_section_depths
 with pytest.raises(ValueError,match='循环'):
  validate_section_depths({'a':SimpleNamespace(parent_id='b'),'b':SimpleNamespace(parent_id='a')})
 with pytest.raises(ValueError,match='三级'):
  validate_section_depths({str(i):SimpleNamespace(parent_id=str(i-1) if i else None) for i in range(4)})
