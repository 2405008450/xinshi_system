"""付款入口同步、版本冲突和凭证持久化；仅使用内存 SQLite。"""
from io import BytesIO
from uuid import UUID
import pytest
from PIL import Image
from fastapi import HTTPException
from pydantic import ValidationError
from tests.test_chat_participant_access import environment
from tests.test_translation_payments import project
import translation_payment_confirmation as confirmation
import translation_payment_service as payments
import translation_customer_finance as finance
from routers.translation_payments import write
import editor_screenshot_service as screenshots
from editor_screenshot_models import EditorScreenshot,EditorScreenshotBlob
from schemas import TranslationProjectUpdate
import crud


def test_finance_and_payment_dialog_share_record_and_conflict(environment):
    db,(actor,*_)=environment;row=project(db,actor)
    before=finance.read(db,row.id)
    receipt=confirmation.PaymentConfirmationWrite(is_paid=True,payment_option='deposit')
    result=finance.save(db,actor,row.id,finance.PriceWrite(version=before['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=100,payment_confirmation=receipt))
    assert result['item']['payment_confirmation']['payment_option']=='deposit'
    loaded=payments.read(db,row)
    assert loaded['confirmation']['revision']==1
    updated=write(row.id,payments.PaymentWrite(version=loaded['version'],payments=[],confirmation={**loaded['confirmation'],'payment_option':'full','full_payment_amount':100,'full_payment_total_key':'excl:CNY'}),db,actor)
    assert finance.read(db,row.id)['item']['payment_confirmation']==updated['confirmation']
    assert crud.get_translation_project(db,row.id).payment_confirmation==updated['confirmation']
    # 收费版本未变化，但独立付款版本仍能阻止旧表单覆盖。
    with pytest.raises(HTTPException) as stale:
        finance.save(db,actor,row.id,finance.PriceWrite(version=result['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=200,payment_confirmation=receipt))
    assert stale.value.status_code==409;db.rollback()
    assert finance.read(db,row.id)['item']['adjusted_total']=='100.00'
    assert confirmation.history(db,row.id)['total']==2


def test_proof_bytes_persist_and_unchecking_keeps_proofs_and_history(environment):
    db,(actor,*_)=environment;row=project(db,actor)
    buf=BytesIO();Image.new('RGB',(32,32),'blue').save(buf,'PNG')
    image=screenshots.save_image(db,actor.id,buf.getvalue(),'image/png','chat')
    proof='支付截图 ![截图]('+image['reference']+')'
    saved=confirmation.save(db,row.id,confirmation.PaymentConfirmationWrite(is_paid=True,payment_option='once',proofs=proof),actor.id);db.commit();db.expire_all()
    stored=db.get(EditorScreenshot,UUID(image['id']))
    assert stored.retention_kind=='business' and stored.expires_at is None
    assert db.get(EditorScreenshotBlob,stored.blob_sha256).content
    updated=crud.update_translation_project(db,row.id,TranslationProjectUpdate(payment_confirmation={**saved,'is_paid':False}),actor.id)
    assert updated.payment_confirmation['proofs']==proof
    screenshots.cleanup(db);db.expire_all()
    assert db.get(EditorScreenshot,stored.id).blob_sha256
    history=confirmation.history(db,row.id)
    assert history['total']==2 and history['items'][0]['before']['is_paid']
    assert history['items'][0]['after']['proofs']==proof
    assert history['items'][0]['created_at'].endswith('+08:00')


def test_validation_and_migration_idempotent(environment):
    db,(actor,*_)=environment;row=project(db,actor)
    with pytest.raises(ValidationError):confirmation.PaymentConfirmationWrite(is_paid=True)
    with pytest.raises(ValidationError):confirmation.PaymentConfirmationWrite(is_paid=True,payment_option='paid')
    with pytest.raises(HTTPException):confirmation.save(db,row.id,confirmation.PaymentConfirmationWrite(proofs='screenshot://00000000-0000-0000-0000-000000000000'),actor.id)
    db.rollback()
    from tools.apply_translation_payment_confirmation_migration import apply_migration
    with db.get_bind().begin() as conn:
        apply_migration(conn);apply_migration(conn)


def test_payment_account_and_custom_name_share_all_entries(environment):
    db,(actor,*_)=environment;row=project(db,actor)
    saved=confirmation.save(db,row.id,confirmation.PaymentConfirmationWrite(is_paid=True,payment_option='deposit',payment_account='广州公司公账'),actor.id);db.commit()
    assert crud.get_translation_project(db,row.id).payment_confirmation['payment_account']=='广州公司公账'
    assert finance.read(db,row.id)['item']['payment_confirmation']['payment_account']=='广州公司公账'
    loaded=payments.read(db,row)
    updated=write(row.id,payments.PaymentWrite(version=loaded['version'],payments=[{'stage_type':'deposit','payment_method':'广州公司公账'}],confirmation={**loaded['confirmation'],'payment_account':'自定义收款账户'}),db,actor)
    assert updated['confirmation']['payment_option']=='deposit'
    assert updated['confirmation']['payment_account']=='自定义收款账户'
    assert updated['payments'][0]['payment_method']=='广州公司公账'
    history=confirmation.history(db,row.id)['items'][0]
    assert history['before']['payment_account']=='广州公司公账' and history['after']['payment_account']=='自定义收款账户'
    # 老记录仍可读取；账户不改变全款/定金/一次款含义。
    raw=db.get(confirmation.TranslationPaymentConfirmation,row.id);raw.payment_option='full';db.commit()
    assert confirmation.read(db,row.id)['payment_account']==''
    assert confirmation.read(db,row.id)['payment_option']=='full'
    with pytest.raises(ValidationError):confirmation.PaymentConfirmationWrite(payment_account='长'*51)
