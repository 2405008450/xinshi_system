"""母、子和三级订单的安排隔离及工作报告编号回归；仅内存数据库。"""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_chat_participant_access import environment
from models import TranslationProject, TranslationSubOrder
import project_arrangement as service
import project_arrangement_targets as targets
from tests.test_project_arrangement import completion


def orders(db, owner):
    root=TranslationProject(id=uuid4(),order_no='TP-TARGET-001',project_name='母订单.docx',project_status='confirmed',created_by=owner.id)
    root.customer_requirement_professional='法律术语统一'
    root.customer_requirement_special='保留原格式'
    other=TranslationProject(id=uuid4(),order_no='TP-TARGET-002',project_name='其他母订单.docx',created_by=owner.id)
    db.add_all([root,other]);db.flush()
    child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.001',sub_project_name='子订单.pdf',status='confirmed')
    third=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.001.001',sub_project_name='三级订单.xlsx',status='pending_confirmation')
    foreign=TranslationSubOrder(id=uuid4(),parent_project_id=other.id,sub_order_no=other.order_no+'.001',sub_project_name='其他子订单.txt')
    db.add_all([child,third,foreign]);db.commit()
    return root,child,third,foreign


def batch(member,ids):
    return service.AssignmentBatch(items=[dict(assignee_id=member.id,content='核对所选订单',work_date=date(2026,10,31))],target_order_ids=ids)


def test_catalog_tree_and_selected_descendants_keep_identity(environment):
    db,(owner,member,_) = environment
    root,child,third,_=orders(db,owner)
    tree=targets.catalog(db,root.id)['items'][0]
    assert tree['id']==str(root.id)
    assert tree['children'][0]['id']==str(child.id)
    assert tree['children'][0]['children'][0]['id']==str(third.id)
    tasks=service.create_assignments(db,owner,root.id,batch(member,[child.id,third.id]))
    assert {(r['order_no'],r['order_level']) for r in tasks}=={(child.sub_order_no,2),(third.sub_order_no,3)}
    assert {r['project_name'] for r in tasks}=={'子订单.pdf','三级订单.xlsx'}
    assert root.project_status=='confirmed' and child.status==third.status=='arranged'
    assert all(r['root_order_no']==root.order_no for r in tasks)
    assert all(r['customer_requirement_professional']=='法律术语统一' and r['customer_requirement_special']=='保留原格式' for r in tasks)
    assert tasks[0]['execution_sequence'][1]['order_no']==third.sub_order_no
    from project_arrangement_history import detail
    event=detail(db,root.id)['history'][0]
    assert {r['order_no'] for r in event['after_snapshot']['tasks']}=={child.sub_order_no,third.sub_order_no}


def test_parent_and_multiple_people_expand_only_explicit_targets(environment):
    db,(owner,member,outsider)=environment
    root,child,third,_=orders(db,owner)
    data=batch(member,[root.id,third.id]);data.items.append(service.AssignmentInput(assignee_id=outsider.id,content='审校',work_date=date(2026,10,31)))
    tasks=service.create_assignments(db,owner,root.id,data)
    assert len(tasks)==4 and len({r['id'] for r in tasks})==4
    assert {r['order_no'] for r in tasks}=={root.order_no,third.sub_order_no}
    assert child.status=='confirmed' and root.project_status==third.status=='arranged'


def test_cross_project_duplicate_and_batch_limit_rejected(environment):
    db,(owner,member,_)=environment
    root,child,third,foreign=orders(db,owner)
    for ids in ([child.id,foreign.id],[child.id,child.id]):
        with pytest.raises(HTTPException) as error:service.create_assignments(db,owner,root.id,batch(member,ids))
        assert error.value.status_code==422
        db.rollback()
    oversized=batch(member,[root.id,child.id,third.id]);oversized.items*=34
    with pytest.raises(HTTPException):service.create_assignments(db,owner,root.id,oversized)
    assert db.query(service.ProjectArrangement).count()==0


def test_report_uses_descendant_number_not_root_and_deleted_name_survives(environment):
    db,(owner,member,_)=environment
    root,child,third,_=orders(db,owner)
    saved=service.create_assignments(db,owner,root.id,batch(member,[third.id]))[0]
    result=service.complete_task(db,member,saved['id'],completion())
    from task_models import DailyReportItem
    report=db.query(DailyReportItem).one()
    assert report.display_metadata['order_no']==third.sub_order_no
    assert report.display_metadata['sub_order_id']==str(third.id)
    assert result['order_no']==third.sub_order_no and result['status']=='completed'
    db.delete(third);db.commit()
    task=service.serialize(db,db.get(service.ProjectArrangement,saved['id']))
    assert task['project_name']=='三级订单.xlsx' and task['target_deleted'] is True
