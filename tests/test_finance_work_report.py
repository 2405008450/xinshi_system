from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError
from task_schemas import DailyReportItemInput,DailyReportSaveRequest
from work_report_categories import DEFAULT_CATEGORIES,validate_categories
from test_chat_participant_access import environment


@pytest.mark.parametrize('name',['客户对账','资源对账','供应商对账','其他对账'])
def test_finance_category_roundtrip_without_order(environment,monkeypatch,name):
    db,(actor,*_)=environment
    import task_service as service
    from task_models import DailyReport,DailyReportItem
    assert name in DEFAULT_CATEGORIES['财务工作']
    item=DailyReportItemInput(source_type='manual',task_type='财务工作',task_name='',progress_content='核对本月账目',duration_minutes=30,
        display_metadata={'report_types':['财务工作::'+name],'quantity':1,'quantity_unit':'次'})
    validate_categories(db,actor,[item])
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *_:[])
    original=DailyReportItem
    monkeypatch.setattr(service,'DailyReportItem',lambda **kwargs:original(id=uuid4(),**kwargs))
    day=date(2026,11,24)
    db.add(DailyReport(id=uuid4(),user_id=actor.id,report_date=day,status='draft'));db.commit()
    service.save_daily_report(db,actor,day,DailyReportSaveRequest(items=[item]))
    saved=service.preview_daily_report(db,actor,day)['items'][0]
    assert saved['display_metadata']['report_types']==['财务工作::'+name]
    assert saved['progress_content']=='核对本月账目'
    assert saved['duration_minutes']==30


def test_finance_mixed_project_work_still_requires_order():
    with pytest.raises(ValidationError,match='订单号和项目名称'):
        DailyReportItemInput(source_type='manual',task_type='财务工作、项目工作',task_name='',progress_content='对账',duration_minutes=10,
            display_metadata={'report_types':['财务工作::客户对账','笔译项目'],'quantity':1,'quantity_unit':'次'})
