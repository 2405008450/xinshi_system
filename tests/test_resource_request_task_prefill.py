from uuid import uuid4
from test_chat_participant_access import environment


def test_annotation_versions_copy_task_not_potential_demand(environment):
    db,(owner,*_)=environment
    from annotation_models import AnnotationProject
    from resource_request_service import get_resource_request_source_prefill
    from resource_request_schemas import ResourceRequestSourcePrefillResponse,ResourceDetailVersion
    project=AnnotationProject(id=uuid4(),order_no='AP-TEST-COPY',project_name='任务复制测试',created_by=owner.id,task_description='具体任务正文\n![截图](screenshot://test)',potential_demand='这是总体需求，不是具体任务',project_status='initial_consultation')
    db.add(project);db.commit()
    payload=ResourceRequestSourcePrefillResponse.model_validate(get_resource_request_source_prefill(db,'annotation',project.id))
    assert payload.request_detail=='这是总体需求，不是具体任务'
    assert [v.name for v in payload.request_content.versions]==['发帖','询问']
    assert all(v.content==project.task_description and v.copied_from_task for v in payload.request_content.versions)
    assert ResourceDetailVersion(name='自定义',content='人工内容').copied_from_task is False
