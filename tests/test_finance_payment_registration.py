"""价格与付款统一保存分期记录；仅使用隔离 SQLite。"""
from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance
import translation_payment_service as payments
import translation_payment_confirmation as confirmation


def save(db,actor,row,current,details,amount=300,**extra):
    return finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,
        pricing_mode='fixed',adjusted_total=amount,payment_version=current['payment']['version'],
        payment_draft=details,payment_confirmation={**current['payment']['confirmation'],'is_paid':True,'payment_option':'deposit',**extra}))


def test_price_and_installments_save_together_and_reload(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'INSTALLMENTS',fixed=True)
    current=finance.read(db,row.id)
    saved=save(db,actor,row,current,[{'stage_type':'deposit','planned_amount':100,'actual_amount':50,
        'payment_time':'2026-11-10T09:30:00+08:00','payment_method':'测试账户'}],proofs='定金备注')
    assert saved['item']['totals_excl_tax']=={'CNY':'300.00'}
    assert saved['payment']['payments'][0]['actual_amount']=='50.00'
    assert saved['payment']['payments'][0]['payment_time'].endswith('+08:00')
    assert saved['payment']['confirmation']['proofs']=='定金备注'
    assert payments.read(db,row)['payments']==saved['payment']['payments']
    details=saved['payment']['payments']+[{'stage_type':'final','actual_amount':250}]
    final=save(db,actor,row,saved,details,full_payment_total_key='billing:CNY')
    assert final['payment']['confirmation']['full_payment_source']=='details'
    assert final['payment']['confirmation']['full_match_status']=='matched'
    assert final['payment']['confirmation']['full_payment_amount']=='300.00'
    db.expire_all()
    assert len(finance.read(db,row.id)['payment']['payments'])==2


def test_stale_payment_draft_rolls_back_price_changes(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'CONCURRENT',fixed=True)
    current=finance.read(db,row.id)
    saved=save(db,actor,row,current,[{'stage_type':'deposit','actual_amount':50}])
    payments.save(db,row,[payments.ProjectPayment(stage_type='deposit',actual_amount=60)],saved['payment']['version'],actor.id,
        confirmation.PaymentConfirmationWrite(**saved['payment']['confirmation']))
    db.commit()
    latest=finance.read(db,row.id)
    stale={**latest,'payment':saved['payment']}
    with pytest.raises(HTTPException) as error:
        save(db,actor,row,stale,[{'stage_type':'deposit','actual_amount':80}],amount=400)
    assert error.value.status_code==409
    db.rollback();db.expire_all()
    reloaded=finance.read(db,row.id)
    assert reloaded['item']['totals_excl_tax']=={'CNY':'300.00'}
    assert reloaded['payment']['payments'][0]['actual_amount']=='60.00'


def test_aggregate_documents_save_and_duplicate_stages(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'DOCUMENTS',fixed=True)
    current=finance.read(db,row.id)
    saved=finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,documents_only=True,
        payment_version=current['payment']['version'],payment_draft=[{'stage_type':'deposit','actual_amount':25}],
        payment_confirmation={'is_paid':True,'payment_option':'deposit'}))
    assert saved['payment']['payments'][0]['actual_amount']=='25.00'
    with pytest.raises(HTTPException) as error:
        save(db,actor,row,saved,[{'stage_type':'deposit','actual_amount':10},{'stage_type':'deposit','actual_amount':20}])
    assert error.value.status_code==422
    db.rollback()


def test_each_installment_proofs_persist_and_archive(context):
    from io import BytesIO
    from PIL import Image
    import editor_screenshot_service as screenshots
    from editor_screenshot_models import EditorScreenshot
    _,db,clients,_,actor=context;row=project(db,clients[0],'DETAIL-PROOFS',fixed=True)
    content=BytesIO();Image.new('RGB',(2,2),'blue').save(content,format='PNG')
    picture=screenshots.save_image(db,actor.id,content.getvalue(),'image/png',retention='chat')
    current=finance.read(db,row.id)
    saved=save(db,actor,row,current,[{'stage_type':'deposit','actual_amount':50,'proofs':'定金凭证'},
        {'stage_type':'mid','actual_amount':50,'proofs':'中期凭证 '+picture['reference']},
        {'stage_type':'final','actual_amount':200,'proofs':'尾款凭证'}],full_payment_total_key='billing:CNY')
    by_stage={item['stage_type']:item for item in saved['payment']['payments']}
    assert by_stage['deposit']['proofs']=='定金凭证'
    assert picture['reference'] in by_stage['mid']['proofs']
    assert by_stage['final']['proofs']=='尾款凭证'
    from uuid import UUID
    image=db.get(EditorScreenshot,UUID(picture['id']))
    assert image.retention_kind=='business' and image.expires_at is None
    # 修改与删除单条凭证后，原内容仍留在历史快照中。
    details=saved['payment']['payments']
    for item in details:
        if item['stage_type']=='mid':item['proofs']='中期更正备注'
    changed=save(db,actor,row,saved,details,full_payment_total_key='billing:CNY')
    history=confirmation.history(db,row.id)['items'][0]
    assert any(picture['reference'] in item['proofs'] for item in history['before']['payment_details'])
    assert any(item['proofs']=='中期更正备注' for item in history['after']['payment_details'])
    reduced=[item for item in changed['payment']['payments'] if item['stage_type']!='mid']
    removed=save(db,actor,row,changed,reduced,full_payment_total_key='billing:CNY',mismatch_reason='已移除中期记录')
    assert len(removed['payment']['payments'])==2
    assert any(item['proofs']=='中期更正备注' for item in confirmation.history(db,row.id)['items'][0]['before']['payment_details'])


def test_legacy_first_proof_and_invalid_detail_reference(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'LEGACY-PROOF',fixed=True)
    legacy=confirmation.save(db,row.id,confirmation.PaymentConfirmationWrite(is_paid=True,payment_option='deposit',proofs='旧定金备注'),actor.id)
    db.commit();state=payments.read(db,row)
    saved=payments.save(db,row,[payments.ProjectPayment(stage_type='deposit',actual_amount=50)],state['version'],actor.id,
        confirmation.PaymentConfirmationWrite(**legacy))
    db.commit()
    assert saved['payments'][0]['proofs']=='旧定金备注'
    current=finance.read(db,row.id)
    with pytest.raises(HTTPException) as error:
        save(db,actor,row,current,[{**saved['payments'][0],'proofs':'screenshot://00000000-0000-0000-0000-000000000000'}])
    assert error.value.status_code==422
    db.rollback()
