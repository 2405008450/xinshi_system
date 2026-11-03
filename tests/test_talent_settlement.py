from decimal import Decimal
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, select
from sqlalchemy.orm import Session

from resource_schemas import ResourcePersonUpdate
from talent_settlement import TalentSettlement, TalentSettlementInput, TalentSettlementPrice, read_settlement, save_settlement


@pytest.fixture
def settlement_db(monkeypatch):
    import main  # 注册 ORM 关系，不运行 startup，也不连接业务数据库。
    engine=create_engine('sqlite:///:memory:')
    meta=MetaData()
    people=Table('resource_person',meta,Column('id',Uuid,primary_key=True))
    users=Table('app_user',meta,Column('id',Uuid,primary_key=True))
    TalentSettlement.__table__.to_metadata(meta)
    meta.create_all(engine)
    monkeypatch.setattr('talent_privacy.can_view_talent_contacts',lambda *_:True)
    with Session(engine) as db:
        person=SimpleNamespace(id=uuid4())
        actor=SimpleNamespace(id=uuid4())
        db.execute(people.insert().values(id=person.id))
        db.execute(users.insert().values(id=actor.id))
        yield db,person,actor
    engine.dispose()


def test_payment_accounts_preserve_leading_zeros_and_payment_screenshots():
    value=TalentSettlementInput(bank_account='  0012345678  ',paypal_account='paypal@example.test',payoneer_account='payoneer@example.test',
                                wechat_payment_code='![截图](screenshot://f60f3c24-6c19-4574-81f5-5709e5c9ac1f)',alipay_payment_code='  ')
    assert value.bank_account=='0012345678'
    assert value.alipay_payment_code is None
    assert 'screenshot://' in value.wechat_payment_code


@pytest.mark.parametrize('category',['interpretation','written_translation','annotation','collection'])
def test_price_types_decimal_precision_units_currency(category):
    price=TalentSettlementPrice(category=category,amount='0.123456',unit='  work_hour  ',currency='USD')
    assert price.amount==Decimal('0.123456')
    assert price.unit=='work_hour'
    assert price.model_dump(mode='json')['amount']=='0.123456'


def test_quote_pending_currency_is_not_inferred_and_range_is_exact():
    pending=TalentSettlementPrice(status='pending',raw_text='21-30$，币种待核',price_type='range',amount='21',amount_max='30')
    assert pending.currency is None and pending.category is None and pending.unit is None
    assert pending.model_dump(mode='json')['amount_max']=='30'
    assert TalentSettlementPrice(category='annotation',amount=1,unit='hour').currency=='CNY'
    confirmed=TalentSettlementPrice(status='confirmed',category='written_translation',service_type='proofreading',
        price_type='range',amount='0.025',amount_max='0.05',currency='USD',unit='source_word')
    assert confirmed.amount==Decimal('0.025') and confirmed.amount_max==Decimal('0.05')
    assert TalentSettlementPrice(status='confirmed',category='written_translation',price_type='negotiable',unit='month',currency='BRL').amount is None


@pytest.mark.parametrize('changes',[
    {'price_type':'range','amount_max':'0.01'}, {'price_type':'fixed','amount_max':'2'},
    {'price_type':'range'}, {'currency':None}, {'category':None}, {'amount':None},
])
def test_confirmed_quotes_reject_incomplete_or_inverted_ranges(changes):
    with pytest.raises(ValidationError):
        TalentSettlementPrice(**{**dict(status='confirmed',category='written_translation',amount='0.025',unit='per_word',currency='USD'),**changes})


def test_pending_raw_quote_requires_meaningful_content():
    with pytest.raises(ValidationError,match='至少填写金额或原始报价'):
        TalentSettlementPrice(status='pending',raw_text=' ')
    assert TalentSettlementPrice(status='pending',amount=0).amount==0
    assert TalentSettlementPrice(status='pending',raw_text='IDR750000',currency='IDR').currency=='IDR'


def test_extended_price_roundtrip_and_legacy_noop(settlement_db):
    db,person,actor=settlement_db
    old={'id':str(uuid4()),'category':'annotation','amount':'0.025','unit':'word','currency':'USD'}
    row=TalentSettlement(person_id=person.id,revision=1,prices=[old],gig_platform_calculation=False,
        updated_at=datetime.now(timezone(timedelta(hours=8))))
    db.add(row);db.flush()
    unchanged=read_settlement(db,person.id,visible=True)
    save_settlement(db,person,ResourcePersonUpdate(full_name='旧价格',settlement=unchanged),actor)
    assert row.revision==1 and row.prices==[old]
    quote=dict(status='pending',price_type='range',amount='21',amount_max='30',unit='hour',currency=None,
        service_type='lqa',language_pair='EN-AR',raw_text='21-30$\nLQA',source_file='共培.xlsx',source_sheet='共培总表',source_row=521,source_column='每小时',notes='币种待确认')
    value=ResourcePersonUpdate(full_name='扩展价格',settlement=dict(revision=1,prices=[old,quote]))
    save_settlement(db,person,value,actor);db.commit();db.expire_all()
    observed=read_settlement(db,person.id,visible=True)
    assert observed['revision']==2
    added=observed['prices'][1]
    for key in ['service_type','language_pair','raw_text','source_file','source_sheet','source_row','source_column','notes']:
        assert added[key]==quote[key]
    assert added['currency'] is None and added['amount_max']==Decimal('30')
    save_settlement(db,person,ResourcePersonUpdate(full_name='再次保存',settlement=observed),actor)
    assert read_settlement(db,person.id,visible=True)['revision']==2


@pytest.mark.parametrize('changes',[{'category':'unknown'},{'amount':'-0.1'},{'amount':'0.1234567'},{'amount':'NaN'},{'unit':' '},{'currency':'bad'}])
def test_invalid_prices_rejected(changes):
    with pytest.raises(ValidationError):
        TalentSettlementPrice(**dict(dict(category='annotation',amount=1,unit='item',currency='CNY'),**changes))


def test_save_read_revision_and_stale_update(settlement_db):
    db,person,actor=settlement_db
    price=dict(id=uuid4(),category='written_translation',amount='0.123456',unit='word',currency='USD')
    payload=ResourcePersonUpdate(full_name='结算测试',settlement=dict(bank_account='001234',payoneer_account='account',prices=[price]))
    save_settlement(db,person,payload,actor)
    db.flush()
    result=read_settlement(db,person.id,visible=True)
    assert result['bank_account']=='001234' and result['revision']==1
    assert result['prices'][0]['amount']==Decimal('0.123456')
    assert person.settlement.revision==1
    same=ResourcePersonUpdate(full_name='结算测试',settlement=result)
    save_settlement(db,person,same,actor)
    assert person.settlement.revision==1
    same.settlement.bank_account='009999'
    save_settlement(db,person,same,actor)
    assert person.settlement.revision==2
    with pytest.raises(HTTPException) as error:
        save_settlement(db,person,payload,actor)
    assert error.value.status_code==409


def test_restricted_users_cannot_read_or_save(settlement_db,monkeypatch):
    db,person,actor=settlement_db
    assert read_settlement(object(),person.id,visible=False) is None
    monkeypatch.setattr('talent_privacy.can_view_talent_contacts',lambda *_:False)
    with pytest.raises(HTTPException) as error:
        save_settlement(db,person,ResourcePersonUpdate(full_name='受限',settlement=dict(bank_account='123')),actor)
    assert error.value.status_code==403
    assert db.scalars(select(TalentSettlement)).all()==[]


def test_restricted_serializer_drops_settlement_instead_of_leaking_codes():
    from pydantic import BaseModel
    from talent_privacy import serialize_with_contact_access
    class Response(BaseModel):
        settlement: dict | None = None
    result=serialize_with_contact_access({'settlement':{'bank_account':'001234','wechat_payment_code':'private-image'}},Response,(),contacts_visible=False)
    assert result['settlement'] is None
    assert '001234' not in str(result) and 'private-image' not in str(result)


def test_invoice_entity_required_only_when_invoice_available():
    with pytest.raises(ValidationError,match='开票主体'):
        TalentSettlementInput(invoice_available=True,invoice_entity=' ')
    assert TalentSettlementInput(invoice_available=True,invoice_entity='  公司甲  ').invoice_entity=='公司甲'
    assert TalentSettlementInput(invoice_available=False,invoice_entity='旧主体').invoice_entity is None
    assert TalentSettlementInput().gig_platform_calculation is False


def test_false_invoice_choice_is_saved_and_empty_defaults_do_not_create_row(settlement_db):
    db,person,actor=settlement_db
    save_settlement(db,person,ResourcePersonUpdate(full_name='空白',settlement={}),actor)
    assert db.scalars(select(TalentSettlement)).all()==[]
    save_settlement(db,person,ResourcePersonUpdate(full_name='不可开票',settlement={'invoice_available':False}),actor)
    db.flush()
    row=db.scalars(select(TalentSettlement)).one()
    assert row.invoice_available is False
    assert row.gig_platform_calculation is False


def test_migration_is_idempotent_and_records_rollback(settlement_db):
    from sqlalchemy import text
    from tools.apply_talent_settlement_migration import apply_migration
    db,person,actor=settlement_db
    db.commit()
    db.execute(text('DROP TABLE talent_settlement'))
    apply_migration(db.connection())
    apply_migration(db.connection())
    db.commit()
    save_settlement(db,person,ResourcePersonUpdate(full_name='回滚',settlement=dict(paypal_account='test')),actor)
    db.flush()
    assert db.scalars(select(TalentSettlement)).one().paypal_account=='test'
    db.rollback()
    assert db.scalars(select(TalentSettlement)).all()==[]
