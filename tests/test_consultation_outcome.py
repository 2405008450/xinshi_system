"""未成交状态必须有原因；现有 JSONB 元数据可持久化且不能经售前字段伪造。"""
import pytest
from pydantic import ValidationError

from test_consultation_contacts import contact_data
from test_chat_participant_access import environment
from consultation_outcome import DETAIL_REQUIRED, FAILURE_KEY, FAILURE_REASONS, FailureReasonInput


@pytest.mark.parametrize('reason', FAILURE_REASONS)
def test_all_builtin_reasons_and_required_details(reason):
    if reason in DETAIL_REQUIRED:
        with pytest.raises(ValidationError): FailureReasonInput(reason=reason)
    value = FailureReasonInput(reason=reason, details='客户具体情况' if reason in DETAIL_REQUIRED else '')
    assert value.reason == reason


def test_state_transition_requires_reason_and_keeps_metadata(contact_data):
    import crud
    from schemas import ConsultationCreate, ConsultationUpdate
    db, client, _, _ = contact_data
    with pytest.raises(ValueError, match='未成交原因'):
        crud.create_consultation(db, ConsultationCreate(client_id=client.id, status='failed'))
    db.rollback()
    row = crud.create_consultation(db, ConsultationCreate(client_id=client.id, status='following', project_intake={'service_content': '保留售前信息'}))
    with pytest.raises(ValueError, match='未成交原因'):
        crud.update_consultation(db, row.id, ConsultationUpdate(status='failed'))
    db.rollback()
    assert crud.get_consultation(db, row.id).status == 'following'
    reason = FailureReasonInput(reason='无法满足客户要求', details='无法提供客户指定格式')
    row = crud.update_consultation(db, row.id, ConsultationUpdate(status='failed', failure_reason=reason))
    assert row.failure_reason == reason.model_dump()
    assert row.project_intake['service_content'] == '保留售前信息'
    row = crud.update_consultation(db, row.id, ConsultationUpdate(project_intake={'service_content': '新售前信息', FAILURE_KEY: {'reason': '伪造'}}))
    assert row.failure_reason == reason.model_dump()
    row = crud.update_consultation(db, row.id, ConsultationUpdate(status='following'))
    assert row.failure_reason == reason.model_dump()
    db.expire_all()
    assert crud.get_consultation(db, row.id).failure_reason['details'] == '无法提供客户指定格式'


def test_new_failed_consultation_custom_reason_and_analytics(contact_data):
    import crud
    from schemas import ConsultationCreate, ConsultationResponse
    from customer_source_analysis import records
    db, client, _, _ = contact_data
    reason = FailureReasonInput(reason='付款周期不合适', details='客户要求180天账期')
    row = crud.create_consultation(db, ConsultationCreate(client_id=client.id, status='failed', failure_reason=reason))
    assert ConsultationResponse.model_validate(row).failure_reason.reason == reason.reason
    assert records(db)['items'][0]['failure_reason'] == reason.model_dump()
    for invalid in ['', '   ', 'x' * 101]:
        with pytest.raises(ValidationError): FailureReasonInput(reason=invalid)
