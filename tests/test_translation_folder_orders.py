"""目录层级导入、统计汇总、Excel：只用隔离 SQLite 与临时目录。"""
from io import BytesIO
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,inspect,text
from openpyxl import load_workbook
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case
from translation_folder_orders import FolderImport,FolderEntry,import_folders,normalized_entries


def folder_payload(root):
    return FolderImport(parent_project_id=root.id,source_kind='local',root_path=r'D:\客户项目',entries=[
        FolderEntry(relative_path='客户项目',files=['根文件.pdf']),
        FolderEntry(relative_path='客户项目/一级资料',files=['一级文件.docx']),
        FolderEntry(relative_path='客户项目/一级资料/二级资料',files=[]),
        FolderEntry(relative_path='客户项目/一级资料/二级资料/三级资料',files=['末级文件.xlsx']),
    ])

def root_project(case):
    from models import TranslationProject
    db,user,crud=case
    root=TranslationProject(id=uuid4(),order_no='TP-261107-971',project_name='原名.docx',source_file_name='原名.docx',created_by=user.id)
    db.add(root);db.commit();return root


def test_folder_migration_only_creates_one_new_table_and_is_repeatable():
    from tools.apply_translation_order_folder_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE translation_sub_order (id CHAR(32) PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'translation_sub_order','translation_order_folder','translation_folder_import_log'}


def test_root_is_mother_dirs_are_first_through_third_files_reach_fourth_and_export(case):
    from models import TranslationSubOrder
    from word_count_service import patch_word_count_matrix
    from word_count_schemas import WordCountMatrixPatch
    from translation_suborder_export import build_workbook
    db,user,crud=case;root=root_project(case)
    result=import_folders(db,folder_payload(root),user.id)
    assert result['created_count']==6
    root=crud.get_translation_project(db,root.id)
    assert root.project_name=='客户项目' and root.network_file_path==r'D:\客户项目'
    by_name={row.sub_project_name:row for row in root.sub_orders}
    assert by_name['一级资料'].sub_order_no.count('.')==1
    assert by_name['二级资料'].sub_order_no.count('.')==2
    assert by_name['三级资料'].sub_order_no.count('.')==3
    leaf=by_name['末级文件.xlsx']
    assert leaf.sub_order_no.count('.')==4
    assert leaf.network_file_path==r'D:\客户项目\一级资料\二级资料\三级资料\末级文件.xlsx'
    assert by_name['三级资料'].folder_info['relative_path']=='客户项目/一级资料/二级资料/三级资料'
    assert by_name['一级资料'].folder_info['files']==['一级文件.docx']
    payload=WordCountMatrixPatch(changes=[dict(scope='entity',dimension='company',metric_type='words',value=123),dict(scope='entity',dimension='customer',metric_type='words',value=100)])
    patch_word_count_matrix(db,'suborder',leaf.id,payload,updated_by=user.id)
    root=crud.get_translation_project(db,root.id)
    assert root.word_count_matrix['company']['words'] is None
    assert root.word_count_matrix['customer']['words'] is None
    for name in ['一级资料','二级资料','三级资料']:assert by_name[name].word_count_matrix['company']['words'] is None
    repeated=import_folders(db,folder_payload(root),user.id)
    assert repeated['created_count']==0 and db.query(TranslationSubOrder).count()==6
    book=load_workbook(BytesIO(build_workbook(crud.get_translation_project(db,root.id))));sheet=book.active
    file_row=next(row[0].row for row in sheet.iter_rows(min_row=4) if row[3].value=='末级文件.xlsx')
    assert [sheet.cell(3,col).value for col in (6,7,8)]==['根路径','相对路径','完整路径']
    assert sheet.cell(file_row,6).value==r'D:\客户项目'
    assert sheet.cell(file_row,7).value==r'客户项目\一级资料\二级资料\三级资料\末级文件.xlsx'
    assert sheet.cell(file_row,8).value==leaf.network_file_path
    assert sheet.cell(4,7).value=='客户项目'
    assert sheet.cell(file_row,4).alignment.indent==4 and sheet.row_dimensions[file_row].outlineLevel==4
    assert sheet.freeze_panes=='E4' and sheet.cell(4,4).value=='客户项目'
    with pytest.raises(ValueError,match='先删除下级'):
        crud.delete_sub_order(db,by_name['一级资料'].id)
    db.rollback()


def test_export_paths_match_root_boundaries_and_preserve_unmatched_paths():
    from types import SimpleNamespace
    from translation_suborder_export import path_columns
    roots=[r'\\server\share\项目']
    assert path_columns(SimpleNamespace(network_file_path=r'\\server\share\项目\资料\a.pdf'),roots)==[roots[0],r'项目\资料\a.pdf',r'\\server\share\项目\资料\a.pdf']
    outside=r'\\server\share\项目旧\a.pdf'
    assert path_columns(SimpleNamespace(network_file_path=outside),roots)==['','',outside]
    assert path_columns(SimpleNamespace(network_file_path=None),roots)==['','','']


def test_invalid_depth_and_missing_parent_are_rejected(case):
    from schemas import TranslationSubOrderCreate
    db,user,crud=case;root=root_project(case)
    with pytest.raises(ValueError,match='四级'):
        normalized_entries([FolderEntry(relative_path='根/a/b/c/d',files=['文件.docx'])])
    with pytest.raises(ValueError,match='缺少上级'):
        normalized_entries([FolderEntry(relative_path='根',files=[]),FolderEntry(relative_path='根/a/b',files=['文件.docx'])])
    with pytest.raises(ValueError,match='先创建上级'):
        crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=root.id,sub_order_no=root.order_no+'.001.001',sub_project_name='文件.docx'))
    db.rollback()


def test_import_failure_rolls_back_root_name_and_all_children(case,monkeypatch):
    from models import TranslationSubOrder
    db,user,crud=case;root=root_project(case);original=crud._create_sub_order_in_transaction;calls=[]
    def fail(db,payload,**kw):
        calls.append(payload)
        if len(calls)==3:raise ValueError('模拟目录写入失败')
        return original(db,payload,**kw)
    monkeypatch.setattr(crud,'_create_sub_order_in_transaction',fail)
    with pytest.raises(ValueError,match='模拟'):
        import_folders(db,folder_payload(root),user.id)
    db.rollback()
    assert root.project_name=='原名.docx' and db.query(TranslationSubOrder).count()==0


def test_empty_folders_are_logged_and_skipped_but_nonempty_ancestors_kept(case):
    from translation_folder_orders import TranslationFolderImportLog,import_records
    from translation_suborder_export import build_workbook
    db,user,crud=case;root=root_project(case)
    payload=folder_payload(root)
    payload.entries += [FolderEntry(relative_path='客户项目/空目录',files=[]),FolderEntry(relative_path='客户项目/空目录/空下级',files=[])]
    result=import_folders(db,payload,user.id)
    assert result['created_count']==6 and result['skipped_count']==2
    records=import_records(db,root.id)
    assert len(records)==1 and records[0]['actor_name']==user.full_name
    assert set(records[0]['empty_folders'])=={'客户项目/空目录','客户项目/空目录/空下级'}
    assert records[0]['created_at'].endswith('+08:00')
    root=crud.get_translation_project(db,root.id)
    assert '二级资料' in {row.sub_project_name for row in root.sub_orders}
    assert not any(row.sub_project_name in ('空目录','空下级') for row in root.sub_orders)
    book=load_workbook(BytesIO(build_workbook(root,records)))
    sheet=book['目录导入与空文件夹记录']
    assert sheet.max_row==3 and sheet.cell(2,6).value=='空文件夹，不生成子订单'
    assert db.query(TranslationFolderImportLog).count()==1


def test_all_empty_root_only_records_and_never_renames_existing_mother(case):
    from models import TranslationSubOrder
    from translation_folder_orders import import_records
    db,user,crud=case;root=root_project(case)
    payload=FolderImport(parent_project_id=root.id,source_kind='local',root_path=r'D:\空目录',entries=[FolderEntry(relative_path='空目录',files=[])])
    result=import_folders(db,payload,user.id)
    assert result['created_count']==0 and result['skipped_count']==1
    assert db.query(TranslationSubOrder).count()==0 and root.project_name=='原名.docx'
    assert import_records(db,root.id)[0]['empty_folders']==['空目录']


def test_folder_first_creates_pending_mother_and_children_with_idempotent_retry(case):
    from models import TranslationProject,TranslationSubOrder
    from schemas import TranslationProjectUpdate
    db,user,crud=case
    payload=FolderImport(order_no='TP-261107-978',source_kind='local',root_path=r'D:\客户项目',entries=[FolderEntry(relative_path='客户项目',files=['文档.docx']),FolderEntry(relative_path='客户项目/一级目录',files=['附件.pdf'])])
    result=import_folders(db,payload,user.id,'folder-first-unique-request')
    assert result['created_root'] and result['created_count']==3
    root=crud.get_translation_project(db,result['project_id'])
    assert root.order_no=='TP-261107-978' and root.project_name=='客户项目'
    assert root.project_status=='pending_confirmation' and root.client_id is None and root.created_by==user.id
    assert root.folder_root is True
    repeated=import_folders(db,payload,user.id,'folder-first-unique-request')
    assert repeated['project_id']==root.id and repeated['created_count']==0
    assert db.query(TranslationProject).count()==1 and db.query(TranslationSubOrder).count()==3
    changed=crud.update_translation_project(db,root.id,TranslationProjectUpdate(remarks='稍后补填'),actor_user_id=user.id)
    assert changed.remarks=='稍后补填'
    with pytest.raises(ValueError,match='不属于当前账号'):
        import_folders(db,payload,uuid4(),'folder-first-unique-request')
    db.rollback()


def test_folder_first_failure_rolls_back_mother_and_children_together(case,monkeypatch):
    from models import TranslationProject,TranslationSubOrder
    db,user,crud=case
    payload=FolderImport(order_no='TP-261107-979',source_kind='local',root_path=r'D:\客户项目',entries=[FolderEntry(relative_path='客户项目',files=['文档.docx','附件.pdf'])])
    original=crud._create_sub_order_in_transaction;calls=[]
    def fail(db,payload,**kw):
        calls.append(payload)
        if len(calls)==2:raise ValueError('模拟失败')
        return original(db,payload,**kw)
    monkeypatch.setattr(crud,'_create_sub_order_in_transaction',fail)
    with pytest.raises(ValueError,match='模拟失败'):
        import_folders(db,payload,user.id,'folder-first-failure')
    db.rollback()
    assert db.query(TranslationProject).count()==0 and db.query(TranslationSubOrder).count()==0


def test_empty_folder_first_records_without_children_and_allows_later_basic_edit(case):
    from models import TranslationSubOrder
    from schemas import TranslationProjectUpdate
    db,user,crud=case
    payload=FolderImport(order_no='TP-261107-980',source_kind='local',root_path=r'D:\空目录',entries=[FolderEntry(relative_path='空目录',files=[])])
    result=import_folders(db,payload,user.id,'empty-folder-first')
    assert result['created_root'] and result['created_count']==0 and db.query(TranslationSubOrder).count()==0
    root=crud.get_translation_project(db,result['project_id'])
    assert root.folder_root is True and root.network_file_path==r'D:\空目录'
    root=crud.update_translation_project(db,root.id,TranslationProjectUpdate(project_name='空目录',source_file_name='空目录'),actor_user_id=user.id)
    assert root.project_name=='空目录'

def test_new_project_directory_waits_for_outer_save_and_keeps_edited_root(case):
    from schemas import TranslationProjectCreate
    from models import TranslationProject,TranslationSubOrder
    db,user,crud=case
    plan=folder_payload(root_project(case)).model_dump(exclude={'parent_project_id','preserve_original_file','order_no'})
    baseline=db.query(TranslationProject).count()
    # 构造/校验新增表单数据没有业务写入；只有 create 才正式登记。
    payload=TranslationProjectCreate(project_name='人工修改后的母订单',created_by=user.id,
        initial_folder_import=plan,submission_mode='normal_children',sub_orders_reviewed=True,
        initial_sub_order_details={'001':{'word_count_matrix':{'company':{'words':10}}},
          '002.001':{'word_count_matrix':{'company':{'words':20}}},
          '002.002.001.001':{'word_count_matrix':{'company':{'words':30}}}})
    assert db.query(TranslationProject).count()==baseline
    root=crud.create_translation_project(db,payload,order_no='TP-261108-979',commit=False)
    assert root.project_name=='人工修改后的母订单'
    assert len(root.sub_orders)==6
    assert root.word_count_matrix['company']['words'] is None
    assert sum(row.word_count_matrix['company']['words'] or 0 for row in root.sub_orders)==60
    assert max(row.sub_order_no.count('.') for row in root.sub_orders)==4
    db.rollback()
    assert db.query(TranslationProject).count()==baseline
    assert db.query(TranslationSubOrder).count()==0


def test_outer_save_failure_does_not_leave_directory_orders(case):
    from schemas import TranslationProjectCreate
    from models import TranslationProject,TranslationSubOrder
    from translation_folder_orders import TranslationFolderImportLog
    db,user,crud=case
    plan={'source_kind':'local','root_path':r'D:\客户项目','entries':[{'relative_path':'客户项目','files':['a.pdf']}]}
    with pytest.raises(ValueError,match='我司统计或客户统计'):
        crud.create_translation_project(db,TranslationProjectCreate(project_name='客户项目',created_by=user.id,
          initial_folder_import=plan,submission_mode='normal_children',sub_orders_reviewed=True),order_no='TP-261108-978')
    db.rollback()
    assert db.query(TranslationProject).count()==0
    assert db.query(TranslationSubOrder).count()==0
    assert db.query(TranslationFolderImportLog).count()==0

def test_legacy_directory_endpoint_cannot_register_unsaved_parent():
    from fastapi import HTTPException
    from types import SimpleNamespace
    from routers.sub_orders import import_suborder_folders
    payload=FolderImport(source_kind='local',root_path=r'D:\测试目录',entries=[FolderEntry(relative_path='测试目录',files=['a.pdf'])])
    class NoDatabaseAccess:
        def __getattr__(self,name):raise AssertionError('不应访问数据库：'+name)
    with pytest.raises(HTTPException,match='') as error:
        import_suborder_folders(payload,db=NoDatabaseAccess(),current_user=SimpleNamespace(id=uuid4()),idempotency_key=None)
    assert error.value.status_code==400 and '保存后才正式登记' in error.value.detail


def test_directory_and_supplement_save_together_without_number_collision(case):
    from schemas import TranslationProjectCreate
    db,user,crud=case
    root=crud.create_translation_project(db,TranslationProjectCreate(project_name='测试母订单',created_by=user.id,
       initial_folder_import={'source_kind':'local','root_path':r'D:\测试目录','entries':[
         {'relative_path':'测试目录','files':['a.pdf']},{'relative_path':'测试目录/附件','files':['b.pdf']}]},
       initial_sub_order_names=['补充.pdf'],initial_sub_order_details={'003':{'word_count_matrix':{'company':{'words':23}}}}),order_no='TP-261108-977')
    assert next(row for row in root.sub_orders if row.sub_project_name=='补充.pdf').sub_order_no.endswith('.003')
    assert root.word_count_matrix['company']['words'] is None
    assert next(row for row in root.sub_orders if row.sub_project_name=='补充.pdf').word_count_matrix['company']['words']==23



def test_local_folder_save_replaces_stale_unc_and_never_inspects_network(case, monkeypatch):
    from schemas import TranslationProjectCreate
    import translation_folder_orders as folders
    db,user,crud=case
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS',r'\\allowed\share')
    def unexpected_inspection(*args, **kwargs):
        raise AssertionError('本地导入不得重新读取 UNC')
    monkeypatch.setattr(folders,'inspect_tree',unexpected_inspection)
    plan={'source_kind':'local','root_path':r'D:\本地项目','entries':[{'relative_path':'本地项目','files':['a.pdf']}]}
    source={'project_name':'本地项目','created_by':user.id,'network_file_path':r'\\old-server\outside\本地项目','initial_folder_import':plan,
        'language_pair':'中文→英语','initial_sub_order_details':{'001':{'language_pair':'中文→法语'}}}
    payload=TranslationProjectCreate.model_validate(source)
    assert source['network_file_path']==r'\\old-server\outside\本地项目'
    assert payload.network_file_path==r'D:\本地项目'
    root=crud.create_translation_project(db,payload,order_no='TP-261110-976')
    assert root.network_file_path==r'D:\本地项目'
    assert root.sub_orders[0].network_file_path==r'D:\本地项目\a.pdf'
    assert root.sub_orders[0].language_pair=='中文→法语'


def test_selected_unc_still_requires_allowed_root(case, monkeypatch):
    from schemas import TranslationProjectCreate
    from translation_folder_orders import FolderDraft
    from pydantic import ValidationError
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS',r'\\allowed\share')
    for source_kind in ['local','unc']:
        plan={'source_kind':source_kind,'root_path':r'\\outside\share\项目','entries':[{'relative_path':'项目','files':['a.pdf']}]}
        with pytest.raises(ValidationError,match='网络路径不在企业允许的目录中'):
            TranslationProjectCreate(project_name='项目',network_file_path=r'D:\旧路径',initial_folder_import=plan)
    plan=FolderDraft(source_kind='unc',root_path=r'\\allowed\share\项目',entries=[{'relative_path':'项目','files':['a.pdf']}])
    assert TranslationProjectCreate(project_name='项目',initial_folder_import=plan).network_file_path==plan.root_path
