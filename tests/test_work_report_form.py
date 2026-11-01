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


def test_vocabulary_clients_search_and_report_roundtrip(environment, monkeypatch):
    from models import Client
    from routers.tasks import report_client_options
    from work_report_categories import DEFAULT_CATEGORIES
    import task_service as service
    from task_models import DailyReportItem, DailyReport
    db, (owner, _, _) = environment
    clients = [Client(id=uuid4(), client_code=f'VOC-{i}', client_name=f'全称{i}', client_short_name=name, manager_contact='不应返回') for i, name in enumerate(['AA-BB', 'BB-AA', 'AA_only', '100%客户', '100客户'])]
    db.add_all(clients); db.commit()
    options = report_client_options('bb aa', 50, db, owner)
    assert len(options) == 2 and all(set(item) == {'id', 'name'} for item in options)
    assert [item['name'] for item in report_client_options('100%', 50, db, owner)] == ['100%客户']
    assert '词汇整理' in DEFAULT_CATEGORIES['非项目工作']
    selected = [{'id': str(client.id), 'name': client.client_short_name} for client in clients[:2]]
    item = row(report_types=['非项目工作::词汇整理'], order_no='', vocabulary_clients=selected)
    item.task_name = 'AA-BB、BB-AA'
    db.add(DailyReport(id=uuid4(), user_id=owner.id, report_date=date(2026, 10, 29), status='draft'))
    db.commit()
    monkeypatch.setattr(service, 'derive_daily_report_items', lambda *args: [])
    original = DailyReportItem
    monkeypatch.setattr(service, 'DailyReportItem', lambda **kwargs: original(id=uuid4(), **kwargs))
    saved = service.save_daily_report(db, owner, date(2026, 10, 29), DailyReportSaveRequest(items=[item]))
    preview = service.preview_daily_report(db, owner, saved.report_date)
    assert preview['items'][0]['task_name'] == item.task_name
    assert preview['items'][0]['display_metadata']['vocabulary_clients'] == selected

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


def test_custom_root_category_requires_saved_content_and_is_user_scoped(environment,monkeypatch):
    import work_report_categories as categories
    db,(owner,other,_)=environment
    monkeypatch.setattr(categories,'can_add_project_category',lambda *_:False)
    data=categories.add_category_group(db,owner,'质量工作','核对术语')
    assert data['work_categories']['质量工作']==['核对术语']
    categories.add_category(db,owner,'质量工作','检查格式')
    categories.add_category_group(db,owner,'质量工作','核对术语')
    assert set(categories.category_catalog(db,owner)['work_categories']['质量工作'])=={'核对术语','检查格式'}
    assert '质量工作' not in categories.category_catalog(db,other)['work_categories']
    item=row(report_types=['质量工作::核对术语'])
    categories.validate_categories(db,owner,[item])
    with pytest.raises(ValueError):categories.validate_categories(db,other,[item])
    with pytest.raises(ValueError):categories.add_category_group(db,owner,'项目工作','绕过限制')
    with pytest.raises(ValueError):categories.add_category_group(db,owner,'自定义',' ')


def test_layout_task_presets_persist_without_polluting_work_categories(environment,monkeypatch):
    import work_report_categories as categories
    db,(owner,other,_)=environment
    monkeypatch.setattr(categories,'can_add_project_category',lambda *_:False)
    owner.department='排版部';db.commit()
    data=categories.add_layout_task_preset(db,owner,'文件终检')
    assert data['layout_task_presets']==['专检','排版','稽查','文件终检']
    assert '__layout_tasks__' not in data['work_categories']
    assert categories.add_layout_task_preset(db,owner,'文件终检')['layout_task_presets'].count('文件终检')==1
    assert '文件终检' not in categories.category_catalog(db,other)['layout_task_presets']
    with pytest.raises(PermissionError):categories.add_layout_task_preset(db,other,'文件终检')
    with pytest.raises(ValueError): categories.validate_categories(db,other,[row(report_types=['项目工作::伪造分类'])])
    with pytest.raises(PermissionError):categories.validate_categories(db,other,[row(report_types=['其他项目'],custom_project_type='绕过权限')])
