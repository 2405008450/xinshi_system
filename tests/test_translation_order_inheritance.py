"""继承、覆盖、差异折叠及汇总：仅使用隔离 SQLite。"""
from datetime import datetime
from io import BytesIO
from uuid import uuid4
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case


def test_recursive_inheritance_overrides_and_reset(case):
    from models import TranslationProject
    from schemas import TranslationSubOrderCreate, TranslationSubOrderUpdate, TranslationProjectUpdate
    from translation_order_inheritance import TranslationOrderInheritance
    db, user, crud = case
    root=TranslationProject(id=uuid4(), order_no='TP-261108-991', project_name='测试', service_content='翻译', customer_requirement_professional='术语表', customer_requirement_special='保留格式', remarks='说明', language_pair='中文→英语', file_type_secondary='合同', project_status='pending_confirmation', customer_deadline_time=datetime(2026,11,10,18))
    db.add(root);db.commit()
    children=[]
    parent=None
    for _ in range(4):
        child=crud.create_sub_order(db, TranslationSubOrderCreate(parent_project_id=root.id, parent_sub_order_id=parent.id if parent else None, sub_project_name='测试.docx', created_by=user.id))
        assert child.service_content=='翻译' and child.customer_requirement_professional=='术语表'
        assert child.language_pair=='中文→英语' and child.customer_deadline_time==datetime(2026,11,10,18)
        assert child.status=='pending_confirmation'
        children.append(child);parent=child
    second=crud.update_sub_order(db,children[1].id,TranslationSubOrderUpdate(service_content='Word排版',customer_requirement_special='自定',remarks='下级说明',customer_deadline_time=datetime(2026,11,11,18)))
    for row in crud.get_sub_orders_by_project(db,root.id)[1:]:
        assert row.service_content=='Word排版' and row.customer_requirement_special=='自定' and row.remarks=='下级说明'
    root=crud.update_translation_project(db,root.id,TranslationProjectUpdate(service_content='翻译+Word排版',customer_requirement_professional='新术语',remarks='新说明',project_status='confirmed'),actor_user_id=user.id)
    by_id={r.id:r for r in root.sub_orders}
    assert by_id[children[0].id].service_content=='翻译+Word排版'
    assert by_id[children[1].id].service_content=='Word排版'
    assert by_id[children[3].id].customer_requirement_professional=='新术语'
    assert by_id[children[3].id].status=='confirmed'
    diff=root.child_field_differences['service_content']
    assert diff['count']==3 and len(diff['items'])==1
    assert diff['items'][0]['order_no']==second.sub_order_no and diff['items'][0]['includes_descendants']
    crud.update_sub_order(db,children[1].id,TranslationSubOrderUpdate(inherit_fields=['service_content','remarks']))
    root=crud.get_translation_project(db,root.id)
    assert 'service_content' not in root.child_field_differences
    assert all(row.remarks=='新说明' for row in root.sub_orders)
    assert db.query(TranslationOrderInheritance).count()==4


def test_partial_branch_differences_and_legacy_manual_values(case):
    from models import TranslationProject,TranslationSubOrder
    from schemas import TranslationProjectUpdate
    db,user,crud=case
    root=TranslationProject(id=uuid4(),order_no='TP-261108-992',project_name='测试',remarks='母说明')
    db.add(root);db.flush()
    rows=[TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+suffix,sub_project_name='a.pdf',remarks=note) for suffix,note in [('.001','母说明'),('.001.001','不同'),('.001.002','母说明')]]
    db.add_all(rows);db.commit()
    root=crud.update_translation_project(db,root.id,TranslationProjectUpdate(remarks='新说明'),actor_user_id=user.id)
    by_no={r.sub_order_no:r for r in root.sub_orders}
    assert by_no[root.order_no+'.001.001'].remarks=='不同'
    assert by_no[root.order_no+'.001.002'].remarks=='新说明'
    assert root.child_field_differences['remarks']['items'][0]['order_no']==root.order_no+'.001.001'


def test_migration_is_repeatable_and_only_adds_new_table():
    from sqlalchemy import create_engine,inspect,text
    from tools.apply_translation_order_inheritance_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE translation_sub_order (id CHAR(32) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE translation_project (id CHAR(32) PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'translation_sub_order','translation_order_inheritance','translation_project_submission','translation_project'}


def test_mail_hierarchy_summary_includes_file_counts(monkeypatch):
    from types import SimpleNamespace
    import business_mail_service as service
    from translation_order_inheritance import hierarchy_summary
    from tests.test_business_mail import _settings
    rows=[SimpleNamespace(sub_order_no='TP-1'+suffix) for suffix in ['.001','.001.001','.001.002','.001.002.001','.001.002.001.001','.002']]
    summary=hierarchy_summary(rows)
    assert summary==[{'level':1,'orders':2,'files':1},{'level':2,'orders':2,'files':1},{'level':3,'orders':1,'files':0},{'level':4,'orders':1,'files':1}]
    monkeypatch.setattr(service,'policy_recipients',lambda *_:([],[]))
    monkeypatch.setattr(service.SmtpSettings,'from_env',lambda:_settings())
    preview=service.build_preview(object(),'translation',source={'order_no':'TP-261108-991','project_name':'a.pdf','service_content':'翻译','language_pair':'中英','sub_order_hierarchy':summary})
    assert preview['body'].endswith('四级子订单：1 个，其中文件：1 个')
    assert '一级子订单：2 个，其中文件：1 个' in preview['body']


def test_file_parent_split_by_direction_still_counts_as_a_file():
    from types import SimpleNamespace
    from translation_order_inheritance import hierarchy_summary
    rows=[SimpleNamespace(sub_order_no='TP-1.001',sub_project_name='原文件.pdf',folder_info=None),
          SimpleNamespace(sub_order_no='TP-1.001.001',sub_project_name='原文件.pdf',folder_info=None),
          SimpleNamespace(sub_order_no='TP-1.002',sub_project_name='名字.docx',folder_info={'files':['a.docx']})]
    assert hierarchy_summary(rows)==[{'level':1,'orders':2,'files':1},{'level':2,'orders':1,'files':1}]
