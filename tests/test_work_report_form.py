"""工作报告表单回归：仅使用内存 SQLite，不访问业务库。"""
from datetime import date
from io import BytesIO
from uuid import uuid4
import pytest
from pydantic import ValidationError
from openpyxl import load_workbook
from test_chat_participant_access import environment
from task_schemas import DailyReportItemInput, DailyReportSaveRequest


def row(**metadata):
    return DailyReportItemInput(source_type='manual',task_type='项目工作',task_name='测试项目',progress_content='整理资料',duration_minutes=66,display_metadata={'report_types':['笔译项目','非项目工作'],'order_no':'TP-001','quantity':'1.5','quantity_unit':'页',**metadata})

@pytest.mark.parametrize('metadata',[{'quantity':-1},{'quantity':'abc'},{'quantity':'nan'},{'quantity_unit':''},{'quantity_unit':'其他'},{'report_types':[]},{'report_types':['无效']},{'report_types':['其他项目']}])
def test_invalid_form_metadata_rejected(metadata):
    with pytest.raises(ValidationError):row(**metadata)


def test_own_report_metadata_roundtrip_and_history_isolation(environment,monkeypatch):
    db,(owner,other,_) = environment
    import task_service as service
    from task_models import DailyReport,DailyReportItem
    from department_models import Department,DepartmentMember
    from routers.tasks import report_editor_context
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *args:[])
    original=DailyReportItem
    monkeypatch.setattr(service,'DailyReportItem',lambda **kwargs:original(id=uuid4(),**kwargs))
    day=date(2026,10,24)
    report=DailyReport(id=uuid4(),user_id=owner.id,report_date=day,status='draft');db.add(report)
    other_report=DailyReport(id=uuid4(),user_id=other.id,report_date=day,status='draft');db.add(other_report);db.flush()
    db.add(DailyReportItem(id=uuid4(),report_id=other_report.id,sort_order=0,source_type='manual',task_type='其他',task_name='其他人',progress_content='不可泄露的历史任务',duration_minutes=10))
    owner.department='业务部'
    department=Department(id=uuid4(),name='项目部',revision=1);db.add(department);db.flush()
    db.add(DepartmentMember(user_id=owner.id,department_id=department.id,position='成员'));db.commit()
    saved=service.save_daily_report(db,owner,day,DailyReportSaveRequest(items=[row()]))
    preview=service.preview_daily_report(db,owner,day)
    assert preview['items'][0]['display_metadata']['quantity']=='1.5'
    assert preview['items'][0]['duration_minutes']==66
    context=report_editor_context(db,owner)
    assert set(context['departments'])=={'业务部','项目部'}
    assert context['task_history']==['整理资料']
    saved=service.save_daily_report(db,owner,day,DailyReportSaveRequest(items=[row(quantity_unit='其他',quantity_unit_other='段')]),finalize=True)
    book=load_workbook(BytesIO(service.report_to_xlsx(saved)))
    sheet=book.active
    assert sheet['F5'].value=='1.5' and sheet['G5'].value=='段' and sheet['H5'].value=='1.1小时'
    assert '笔译项目' in sheet['B5'].value and sheet['E5'].value=='整理资料'
    with pytest.raises(ValueError):service.save_daily_report(db,owner,day,DailyReportSaveRequest(items=[row()]))


@pytest.mark.parametrize('parent', ['项目工作', '外勤工作', '管理工作'])
def test_identity_required_except_nonproject(parent):
    types = {'项目工作': '笔译项目', '外勤工作': '外勤工作::拜访客户', '管理工作': '管理工作::分析数据'}
    with pytest.raises(ValidationError):
        row(report_types=[types[parent]], order_no='')
    with pytest.raises(ValidationError):
        DailyReportItemInput(source_type='manual', task_type=parent, task_name='', progress_content='任务', duration_minutes=10, display_metadata={'report_types':[types[parent]],'quantity':1,'quantity_unit':'次','order_no':'A'})


def test_nonproject_can_omit_identity_but_other_fields_required():
    data = dict(source_type='manual',task_type='非项目工作',task_name='',progress_content='接待客户',duration_minutes=10,display_metadata={'report_types':['非项目工作::接待客户'],'quantity':0,'quantity_unit':'次'})
    assert DailyReportItemInput(**data).task_name == ''
    for field, value in [('progress_content',' '), ('duration_minutes',0)]:
        with pytest.raises(ValidationError): DailyReportItemInput(**{**data,field:value})
    for field in ['quantity','quantity_unit']:
        with pytest.raises(ValidationError): DailyReportItemInput(**{**data,'display_metadata':{**data['display_metadata'],field:''}})
    with pytest.raises(ValidationError): DailyReportItemInput(**{**data,'display_metadata':{**data['display_metadata'],'report_types':['非项目工作::接待客户','管理工作::分析数据']}})


def test_report_fields_reject_screenshots():
    with pytest.raises(ValidationError):
        DailyReportSaveRequest(items=[row()], supplemental_note='![截图](screenshot://00000000-0000-0000-0000-000000000000)')
    data=row().model_dump();data['display_metadata']['order_no']='data:image/png;base64,xx'
    with pytest.raises(ValidationError): DailyReportSaveRequest(items=[data])


def test_historical_incomplete_rows_still_readable():
    from task_schemas import DailyReportItemResponse
    item=DailyReportItemResponse(source_type='manual',task_type='笔译项目',task_name='旧项目',progress_content='旧任务',display_metadata={'report_types':['笔译项目']})
    assert item.duration_minutes==0


def test_category_migration_repeatable_in_isolated_database():
    from sqlalchemy import create_engine, inspect
    from tools.apply_work_report_categories_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection);apply_migration(connection)
        assert inspect(connection).has_table('work_report_category')
    engine.dispose()


def test_category_permissions_persistence_and_user_isolation(environment,monkeypatch):
    db,(owner,other,_)=environment
    import work_report_categories as categories
    monkeypatch.setattr(categories,'can_add_project_category',lambda db,user:user.id==owner.id)
    with pytest.raises(PermissionError):categories.add_category(db,other,'项目工作','测试新项目')
    categories.add_category(db,owner,'项目工作','测试新项目')
    categories.add_category(db,other,'外勤工作','展会')
    categories.add_category(db,other,'外勤工作',' 展会 ')
    assert '测试新项目' in categories.category_catalog(db,other)['work_categories']['项目工作']
    assert categories.category_catalog(db,other)['work_categories']['外勤工作'].count('展会')==1
    assert '展会' not in categories.category_catalog(db,owner)['work_categories']['外勤工作']
    categories.validate_categories(db,other,[row(report_types=['项目工作::测试新项目'])])
    with pytest.raises(ValueError): categories.validate_categories(db,owner,[row(report_types=['外勤工作::展会'])])
    with pytest.raises(ValueError): categories.validate_categories(db,other,[row(report_types=['项目工作::伪造分类'])])
    with pytest.raises(PermissionError):categories.validate_categories(db,other,[row(report_types=['其他项目'],custom_project_type='绕过权限')])
