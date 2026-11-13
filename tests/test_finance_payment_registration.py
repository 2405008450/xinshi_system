"""价格与付款统一保存分期记录；仅使用隔离 SQLite。"""
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance
import translation_payment_service as payments
import translation_payment_confirmation as confirmation
from models import FinancePayment, FinanceRecord
from routers.translation_payments import confirm as confirm_payment


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
    first = saved['payment']['payments'][0]
    assert first['confirmed_by'] is None and first['confirmed_at'] is None
    request=payments.PaymentConfirm(version=saved['payment']['version'],payment_id=first['id'])
    with pytest.raises(HTTPException) as forbidden:
        confirm_payment(row.id,request,db,actor)
    assert forbidden.value.status_code==403
    actor.department='行政部';db.commit()
    saved['payment']=confirm_payment(row.id,request,db,actor)
    first=saved['payment']['payments'][0]
    assert first['confirmed_by'] == str(actor.id)
    assert first['confirmed_by_name'] == (actor.full_name or actor.username)
    assert first['confirmed_at'].endswith('+08:00')
    assert saved['payment']['confirmation']['proofs']=='定金备注'
    assert payments.read(db,row)['payments']==saved['payment']['payments']
    details=saved['payment']['payments']+[{'stage_type':'final','actual_amount':250}]
    final=save(db,actor,row,saved,details,full_payment_total_key='billing:CNY')
    assert final['payment']['confirmation']['full_payment_source']=='details'
    assert final['payment']['confirmation']['full_match_status']=='matched'
    assert final['payment']['confirmation']['full_payment_amount']=='300.00'
    assert final['payment']['payments'][0]['confirmed_at'] == first['confirmed_at']
    assert final['payment']['payments'][1]['confirmed_by'] is None
    db.expire_all()
    assert [item['stage_no'] for item in finance.read(db,row.id)['payment']['payments']]==[1,2]
    stored=db.query(FinancePayment).join(FinanceRecord).filter(FinanceRecord.project_id==row.id).all()
    assert {item.stage_type:item.stage_no for item in stored}=={'deposit':1,'final':1}
    with_later_payment=save(db,actor,row,final,final['payment']['payments']+[
        {'stage_type':'mid','actual_amount':10},
    ],amount=310,full_payment_total_key='billing:CNY')
    db.expire_all()
    details=finance.read(db,row.id)['payment']['payments']
    assert [(item['stage_type'],item['stage_no']) for item in details]==[('deposit',1),('final',2),('mid',3)]
    with pytest.raises(HTTPException) as error:
        save(db,actor,row,with_later_payment,details+[{'stage_type':'final','actual_amount':10}])
    assert error.value.status_code==422
    db.rollback()


def test_full_payment_confirmation_survives_price_recheck(context):
    _, db, clients, _, actor = context
    row = project(db, clients[0], 'FULL-CONFIRM', fixed=True)
    current = finance.read(db, row.id)
    saved = save(db, actor, row, current, [], payment_option='full',
                 full_payment_amount=300, full_payment_total_key='billing:CNY')
    assert saved['payment']['confirmation']['full_payment_confirmed_at'] is None
    actor.department='行政部';db.commit()
    confirmed = confirm_payment(row.id,payments.PaymentConfirm(version=saved['payment']['version']),db,actor)['confirmation']
    assert confirmed['full_payment_confirmed_by'] == str(actor.id)
    assert confirmed['full_payment_confirmed_by_name'] == (actor.full_name or actor.username)
    assert confirmed['full_payment_confirmed_at'].endswith('+08:00')
    changed = finance.save(db, actor, row.id, finance.PriceWrite(
        version=saved['version'], order_id=row.id, pricing_mode='fixed', adjusted_total=400,
    ))['payment']['confirmation']
    assert changed['full_match_status'] == 'mismatch'
    assert changed['full_payment_confirmed_at'] == confirmed['full_payment_confirmed_at']
    latest=finance.read(db,row.id)
    changed_amount=save(db,actor,row,latest,[],amount=400,payment_option='full',full_payment_amount=400,full_payment_total_key='billing:CNY')
    assert changed_amount['payment']['confirmation']['full_payment_confirmed_at'] is None


def test_mismatched_full_payment_saves_without_updating_project_price(context):
    from io import BytesIO
    from PIL import Image
    import editor_screenshot_service as screenshots

    _, db, clients, _, actor = context
    row = project(db, clients[0], 'PAYMENT-ONLY', fixed=True)
    content = BytesIO()
    Image.new('RGB', (2, 2), 'blue').save(content, format='PNG')
    picture = screenshots.save_image(db, actor.id, content.getvalue(), 'image/png', retention='chat')
    proofs = '付款凭证备注 ' + picture['reference']
    current = finance.read(db, row.id)
    db.execute(text("""
        CREATE TEMP TRIGGER reject_payment_project_update
        BEFORE UPDATE ON translation_project
        BEGIN
            SELECT RAISE(ABORT, 'Payment-only save attempted to update the project');
        END
    """))

    saved = finance.update(row.id, finance.PriceWrite(
        version=current['version'], order_id=row.id, documents_only=True,
        payment_confirmation={
            'is_paid': True,
            'payment_option': 'full',
            'full_payment_amount': 260,
            'full_payment_total_key': 'billing:CNY',
            'mismatch_reason': '差额测试',
            'proofs': proofs,
        },
    ), db, actor)

    stored = finance.read(db, row.id)['payment']['confirmation']
    assert saved['item']['totals_excl_tax'] == current['item']['totals_excl_tax']
    assert stored['full_payment_amount'] == '260.00'
    assert stored['full_match_status'] == 'mismatch'
    assert stored['mismatch_reason'] == '差额测试'
    assert stored['proofs'] == proofs


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


def test_final_payment_retries_lock_timeout_without_duplicate_details(context, monkeypatch):
    _, db, clients, _, actor = context
    row = project(db, clients[0], 'FINAL-RETRY', fixed=True)
    deposit = save(db, actor, row, finance.read(db, row.id), [{'stage_type': 'deposit', 'actual_amount': 40}])
    deposit_payment = deposit['payment']['payments'][0]
    payload = finance.PriceWrite(
        version=deposit['version'], order_id=row.id, documents_only=True,
        payment_version=deposit['payment']['version'],
        payment_draft=[deposit_payment, {'stage_type': 'final', 'actual_amount': 260, 'proofs': '尾款凭证'}],
        payment_confirmation={
            **deposit['payment']['confirmation'],
            'full_payment_total_key': 'billing:CNY',
        },
    )
    class LockTimeout(Exception):
        pgcode = '55P03'

    write = finance._write_finance
    calls = 0

    def write_with_transient_lock(*args):
        nonlocal calls
        calls += 1
        write(*args)
        if calls == 1:
            raise OperationalError(None, None, LockTimeout())

    monkeypatch.setattr(finance, '_write_finance', write_with_transient_lock)
    saved = finance.update(row.id, payload, db, actor)['payment']

    assert calls == 2
    assert [(detail['stage_type'], detail['actual_amount']) for detail in saved['payments']] == [
        ('deposit', '40.00'), ('final', '260.00'),
    ]
    assert saved['payments'][0]['id'] == deposit_payment['id']
    assert saved['payments'][1]['proofs'] == '尾款凭证'
    assert saved['confirmation']['revision'] == deposit['payment']['confirmation']['revision'] + 1
    assert saved['confirmation']['full_match_status'] == 'matched'


def test_aggregate_documents_save_sequences_all_payments_and_rejects_duplicate_ids(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'DOCUMENTS',fixed=True)
    current=finance.read(db,row.id)
    saved=finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,documents_only=True,
        payment_version=current['payment']['version'],payment_draft=[{'stage_type':'deposit','actual_amount':25}],
        payment_confirmation={'is_paid':True,'payment_option':'deposit'}))
    assert saved['payment']['payments'][0]['actual_amount']=='25.00'
    saved = save(db, actor, row, saved, [
        saved['payment']['payments'][0],
        {'stage_type': 'mid', 'stage_no': 1, 'actual_amount': 10},
        {'stage_type': 'mid', 'stage_no': 1, 'actual_amount': 20},
    ])
    rows = saved['payment']['payments']
    assert [item['stage_no'] for item in rows] == [1, 2, 3]
    assert [item['actual_amount'] for item in rows] == ['25.00', '10.00', '20.00']
    with pytest.raises(HTTPException) as error:
        save(db, actor, row, saved, [rows[0], rows[0]])
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
