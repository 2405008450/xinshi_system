from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import AppUser,Client,TranslationProject
from department_models import Department,DepartmentMember
from project_client_manager import ProjectClientManagerChange
from annotation_progress_time import business_now
import translation_customer_finance as finance


def test_options_include_all_customer_department_memberships_only(environment):
    db,(owner,member,sales)=environment
    dept=Department(id=uuid4(),name='客户部',aliases=['客户服务部'])
    db.add(dept);db.flush()
    owner.department='客户服务部';member.department='IT部';sales.department='销售'
    db.add(DepartmentMember(department_id=dept.id,user_id=member.id))
    inactive=AppUser(id=uuid4(),username='inactive',full_name='停用客户成员',password_hash='disabled',department='客户部',is_active=False,is_deleted=False)
    deleted=AppUser(id=uuid4(),username='deleted',full_name='已删除客户成员',password_hash='disabled',department='客户部',is_active=True,is_deleted=True)
    db.add_all([inactive,deleted]);db.commit()
    options=finance.manager_options(db)['items']
    assert {row['id'] for row in options}=={str(owner.id),str(member.id),str(inactive.id)}
    assert next(row for row in options if row['id']==str(inactive.id))['active'] is False


def test_multi_manager_ids_match_latest_identity_not_partial_names(environment):
    db,(owner,member,outsider)=environment
    owner.full_name='客户经理甲';member.full_name='客户经理乙';outsider.full_name='客户经理甲'
    client=Client(id=uuid4(),client_name='客户全称',client_short_name='客户简称',client_manager=owner.full_name)
    partial=Client(id=uuid4(),client_name='其他客户',client_short_name='其他',client_manager='客户经理甲的其他人')
    db.add_all([client,partial]);db.flush()
    roots=[TranslationProject(id=uuid4(),order_no=f'TP-MANAGER-{i}',project_name='测试.docx',client_id=partial.id if i==5 else client.id) for i in range(6)]
    db.add_all(roots);db.flush()
    def assign(index,uid,name,revision=1):db.add(ProjectClientManagerChange(project_type='translation',project_id=roots[index].id,revision=revision,new_manager_id=uid,new_manager_name=name,actor_user_id=owner.id,actor_name=owner.full_name,reason='隔离验证',changed_at=business_now()))
    assign(0,owner.id,'旧姓名');assign(1,member.id,member.full_name);assign(2,outsider.id,owner.full_name)
    assign(3,owner.id,owner.full_name);assign(3,None,None,2)
    db.commit()
    params=dict(skip=0,limit=1,keyword=None,project_status=None,billing_month=None,client=None,client_manager=None,db=db,user=owner,only_mine=False,manager_ids=[owner.id,member.id])
    first=finance.page(**params)
    assert first['total']==3 # 甲、乙的最新ID + 历史档案精确姓名；排除同名其他ID、已清空、包含姓名。
    assert sum(row['project_count'] for row in first['client_subtotals'])==3
    ids=set()
    for index in range(3):ids.update(row['id'] for row in finance.page(**{**params,'skip':index})['items'])
    assert ids=={str(roots[i].id) for i in (0,1,4)}
    single=finance.page(**{**params,'limit':10,'manager_ids':[member.id],'only_mine':True})
    assert {row['id'] for row in single['items']}=={str(roots[1].id)}
    assert single['total']==1 and single['client_subtotals'][0]['project_count']==1
