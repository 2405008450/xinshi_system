"""工作台口译任务范围；只使用隔离 SQLite，不改变全局项目目录范围。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from models import Client, SubClient, Consultation
from department_models import Department, DepartmentMember
from interpretation_models import InterpretationProject
from project_client_manager import ProjectClientManagerChange
from workflow_models import ProjectWorkbenchResponsibility
from my_project_tasks import search, interpretation_task_filter
import report_project_picker as picker


def project(db, number, status='in_progress', **values):
    row=InterpretationProject(id=uuid4(),order_no=f'IP-{number}',project_name='甲乙 项目',project_status=status,**values)
    db.add(row);db.flush()
    return row


def department(db,*users):
    row=Department(id=uuid4(),name='口译项目部',aliases=[],revision=1)
    db.add(row);db.flush()
    db.add_all(DepartmentMember(department_id=row.id,user_id=user.id,position='') for user in users)


@pytest.mark.parametrize('username',['kuangjiao','zixia'])
def test_special_accounts_all_active_statuses_search_and_paging(environment,username):
    db,(owner,member,outsider)=environment
    member.username=username
    allowed=[project(db,i,status) for i,status in enumerate([
        'initial_follow_up','deal_pending_execution','in_progress','partially_cancelled','ended',None,''])]
    for i,status in enumerate(['cancelled','settled','取消','已取消','已结款'],100):
        project(db,i,status)
    db.commit()
    assert search(db,member,'interpretation')['total']==len(allowed)
    result=search(db,member,'interpretation','乙 甲',2,3)
    assert result['total']==7 and len(result['items'])==3
    scoped=picker.search(db,'口译项目','',1,100,scope_filter=interpretation_task_filter(db,member))
    assert {row['id'] for row in scoped['items']}=={str(row.id) for row in allowed}
    # 通用项目目录保留原有全量读取规则。
    assert picker.search(db,'口译项目','',1,100)['total']==12


def test_department_members_only_current_client_manager_not_project_manager(environment):
    db,(owner,member,outsider)=environment
    department(db,owner,member)
    own=Client(id=uuid4(),client_code='C-OWN',client_name='客户甲',client_short_name='甲',client_manager=owner.full_name)
    other=Client(id=uuid4(),client_code='C-OTHER',client_name='客户乙',client_short_name='乙',client_manager=member.username)
    db.add_all([own,other]);db.flush()
    a=project(db,1,client_id=own.id)
    child=SubClient(id=uuid4(),parent_client_id=own.id,sub_client_code='SC',client_name='子客户',client_short_name='子',client_manager=member.full_name)
    db.add(child);db.flush()
    b=project(db,2,client_id=own.id,sub_client_id=child.id)
    moved=project(db,3,client_id=own.id)
    removed=project(db,4,client_id=own.id)
    manager_only=project(db,5,client_id=other.id)
    consultation=Consultation(id=uuid4(),consultation_code='ZX',customer_service_id=owner.id)
    db.add(consultation);db.flush()
    project(db,6,client_id=other.id,consultation_id=consultation.id)
    db.add(ProjectWorkbenchResponsibility(id=uuid4(),interpretation_project_id=manager_only.id,
        role_code='project_manager',assignee_id=owner.id))
    for revision,uid in [(1,owner.id),(2,member.id)]:
        db.add(ProjectClientManagerChange(id=uuid4(),project_type='interpretation',project_id=moved.id,revision=revision,new_manager_id=uid,reason='交接'))
    db.add(ProjectClientManagerChange(id=uuid4(),project_type='interpretation',project_id=removed.id,revision=1,new_manager_id=None,reason='撤销'))
    project(db,7,'cancelled',client_id=own.id)
    project(db,8,'settled',client_id=own.id)
    project(db,9,'ended',client_id=own.id)
    db.commit()
    assert {row['id'] for row in search(db,owner,'interpretation')['items']}=={str(a.id),str(db.query(InterpretationProject).filter_by(order_no='IP-9').one().id)}
    member_ids={row['id'] for row in search(db,member,'interpretation')['items']}
    assert str(b.id) in member_ids and str(moved.id) in member_ids
    assert search(db,outsider,'interpretation')['total']==0
    # 离开口译项目部后，即使仍为客户经理，也不进入该工作台任务范围。
    db.query(DepartmentMember).filter_by(user_id=owner.id).delete();db.commit()
    assert search(db,owner,'interpretation')['total']==0


def test_workbench_create_revalidates_status_and_manager_scope(environment):
    import annotation_daily_operations as operations
    from chat_time import now
    from work_report_dates import report_business_date
    db,(owner,member,outsider)=environment
    department(db,member)
    row=project(db,1)
    db.add(ProjectClientManagerChange(id=uuid4(),project_type='interpretation',project_id=row.id,revision=1,new_manager_id=member.id,reason='指定'))
    db.commit()
    payload=operations.BatchWrite(work_date=report_business_date(now()),project_type='口译项目',stage='pending',
        projects=[{'project_id':row.id,'operations':[{'content':'联系译员','estimated_minutes':30}]}])
    assert operations.create(db,member,payload)['items'][0]['project_type']=='口译项目'
    row.project_status='settled';db.commit()
    with pytest.raises(HTTPException) as error:
        operations.create(db,member,payload)
    assert error.value.status_code==403
