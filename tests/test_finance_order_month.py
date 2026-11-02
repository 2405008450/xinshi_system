from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import TranslationProject
import translation_customer_finance as finance


def test_month_follows_order_number_even_without_prices(environment):
    db,(user,_,_)=environment
    numbers=['TP-261029-010','TP-261001-001','TP-261101-001','TP-20261029-001','TP-2610BAD-001']
    db.add_all([TranslationProject(id=uuid4(),order_no=number,project_name='测试.docx') for number in numbers]);db.commit()
    data=finance.page(skip=0,limit=10,billing_month='2026-10',db=db,user=user,only_mine=False,manager_ids=None)
    assert {row['order_no'] for row in data['items']}==set(numbers[index] for index in (0,1,3))
    assert data['total']==3 and sum(row['project_count'] for row in data['client_subtotals'])==3
    assert finance.order_billing_month('TP-261029-010.001.001')=='2026-10'
