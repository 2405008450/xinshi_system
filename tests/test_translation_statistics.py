"""客户统计仅使用隔离数据库，覆盖周期、新老客户、母子去重及多币种金额。"""
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from models import TranslationProject,TranslationSubOrder,TranslationSubOrderChargeItem,Client
from tests.test_chat_participant_access import environment
from translation_statistics import report,summarize,order_date,period_bounds


def client(db,name):
 row=Client(id=uuid4(),client_name=name+'有限公司',client_short_name=name,client_code='C-'+name);db.add(row);return row

def project(db,user,client,number,amount=None,currency='CNY',reception=None):
 row=TranslationProject(id=uuid4(),project_name='测试.pdf',source_file_name='测试.pdf',order_no=number,client_id=client.id if client else None,created_by=user.id,created_at=datetime(2026,11,9),customer_reception_time=reception)
 db.add(row)
 if amount is not None:charge(db,row,amount,currency)
 return row

def charge(db,owner,amount,currency='CNY'):
 row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=owner.id if isinstance(owner,TranslationProject) else None,sub_order_id=owner.id if isinstance(owner,TranslationSubOrder) else None,sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency=currency,total_excl_tax=Decimal(str(amount)),total_incl_tax=Decimal(str(amount))*Decimal('1.06'));db.add(row)


def test_monthly_customer_cohorts_full_history_prices_zero_and_currency(environment):
 db,users=environment;old=client(db,'老客');new=client(db,'新客')
 project(db,users[0],old,'TP-260930-001',999)
 project(db,users[0],old,'TP-261101-001',100)
 project(db,users[0],old,'TP-261102-001',0)
 project(db,users[0],new,'TP-261102-002',50,'USD')
 project(db,users[0],new,'TP-261103-001')
 project(db,users[0],None,'TP-261103-002',20)
 db.commit()
 result=report(db,start=date(2026,11,1),end=date(2026,11,30))
 summary=result['periods'][0]
 assert summary['order_count']==5 and summary['customer_count']==2
 assert summary['new_customer_count']==summary['old_customer_count']==1
 assert summary['new_customer_share']==50 and summary['new_order_share']==40 and summary['old_order_share']==40 and summary['unknown_order_share']==20
 old_row=next(row for row in result['customers'] if row['client_id']==str(old.id))
 assert old_row['first_order_date']=='2026-09-30' and old_row['cohort']=='old'
 assert old_row['amounts'][0]['total_amount']=='100.00' and old_row['amounts'][0]['average_amount']=='50.00' and old_row['amounts'][0]['complete_order_count']==2
 new_row=next(row for row in result['customers'] if row['client_id']==str(new.id))
 assert new_row['amounts'][0]['currency']=='USD' and new_row['amounts'][0]['average_amount']=='50.00'
 assert new_row['missing_amount_orders']==1
 filtered=report(db,start=date(2026,11,1),end=date(2026,11,30),client_keyword='有限公司 老客')
 assert filtered['order_count']==2 and filtered['periods'][0]['new_customer_count']==0
 assert result['generated_at'].endswith('+08:00')


def test_tree_counted_once_partial_totals_not_zeroed_or_averaged(environment):
 db,users=environment;c=client(db,'分层')
 root=project(db,users[0],c,'TP-261109-001',9999)
 for suffix,amount in [('001',10),('002',20)]:
  child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.'+suffix,sub_project_name=suffix+'.pdf');db.add(child);charge(db,child,amount)
 partial=project(db,users[0],c,'TP-261110-001')
 for suffix,amount in [('001',5),('002',None)]:
  child=TranslationSubOrder(id=uuid4(),parent_project_id=partial.id,sub_order_no=partial.order_no+'.'+suffix,sub_project_name=suffix+'.pdf');db.add(child)
  if amount is not None:charge(db,child,amount)
 db.commit()
 result=report(db,start=date(2026,11,1),end=date(2026,11,30))
 row=result['customers'][0];assert row['order_count']==2 and row['partial_amount_orders']==1
 assert row['amounts'][0]['total_amount']=='35.00' and row['amounts'][0]['average_amount']=='30.00'
 incl=report(db,start=date(2026,11,1),end=date(2026,11,30),tax_basis='incl_tax')
 assert incl['customers'][0]['amounts'][0]['total_amount']=='37.10'
 assert incl['customers'][0]['amounts'][0]['average_amount']=='31.80'


def test_week_cross_month_and_daily_new_customer_status(environment):
 db,users=environment;c=client(db,'跨月')
 project(db,users[0],c,'TP-261031-001',10)
 project(db,users[0],c,'TP-261101-001',20)
 db.commit()
 weekly=report(db,start=date(2026,11,1),end=date(2026,11,2),granularity='week')
 assert weekly['periods'][0]['period_start']=='2026-10-26'
 assert weekly['periods'][0]['new_customer_count']==1
 monthly=report(db,start=date(2026,11,1),end=date(2026,11,2))
 assert monthly['periods'][0]['old_customer_count']==1
 daily=report(db,start=date(2026,10,31),end=date(2026,11,1),granularity='day')
 assert daily['periods'][0]['new_customer_count']==1 and daily['periods'][1]['old_customer_count']==1


def test_dates_timezone_invalid_numbers_and_empty_ranges(environment):
 assert order_date('TP-20261001-001')==date(2026,10,1)
 assert order_date('TP-261032-001') is None
 assert period_bounds(date(2027,1,1),'week')==(date(2026,12,28),date(2027,1,3))
 db,users=environment;c=client(db,'日期')
 project(db,users[0],c,'TP-261031-001',10,reception=datetime(2026,11,1,9))
 db.commit()
 assert report(db,start=date(2026,11,1),end=date(2026,11,1))['order_count']==0
 assert report(db,start=date(2026,11,1),end=date(2026,11,1),date_basis='reception')['order_count']==1
 with pytest.raises(HTTPException):report(db,start=date(2026,11,2),end=date(2026,11,1))


def test_statistics_route_registered_before_uuid_route():
 from routers.translation_projects import router
 paths=[route.path for route in router.routes]
 assert paths.index('/projects/translation/statistics')<paths.index('/projects/translation/{project_id}')
