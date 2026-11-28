"""真实创建、编辑服务的隔离事务回归，不发送外部通知。"""
from uuid import uuid4
import pytest
from sqlalchemy import event
from tests.test_chat_participant_access import environment
from interpretation_schemas import InterpretationProjectCreate,InterpretationProjectUpdate
from interpretation_models import InterpretationProjectStatusHistory
from resource_models import ResourcePerson
import interpretation_service as service


@pytest.mark.parametrize('autoflush',[True,False])
def test_assignment_selection_change_history_and_later_status(environment,monkeypatch,autoflush):
    db,users=environment
    db.autoflush=autoflush
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',ids)
    monkeypatch.setattr(service,'generate_interpretation_order_no',lambda *_:'IP-261127-STATUS')
    people=[ResourcePerson(id=uuid4(),resource_code=f'RC-STATUS-{n}',full_name=f'测试译员{n}',status='standby') for n in range(2)]
    db.add_all(people);db.commit()
    project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='状态隔离测试'),users[0].id)
    def save(items,status=None,reason=None):
        return service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_name=project.project_name,project_status=status or project.project_status,interpreter_assignments=items,status_change_reason=reason),users[0].id)
    row={'translator_id':people[0].id,'client_selected':False}
    project=save([row]);assert project.project_status=='candidates_provided' and project.assigned_interpreter_count==1
    from interpretation_status_notice import content
    assert project.status_change_id and '已登记译员：测试译员0（1人）' in content(db,project.id,project.status_change_id)
    history=db.query(InterpretationProjectStatusHistory).filter_by(project_id=project.id).count()
    project=save([row]);assert db.query(InterpretationProjectStatusHistory).filter_by(project_id=project.id).count()==history
    assert project.status_change_id is None
    row['client_selected']=True
    project=save([row]);assert project.project_status=='client_selected'
    replacement={'translator_id':people[1].id,'client_selected':True}
    project=save([replacement],reason='测试');assert project.project_status=='client_mixed'
    assert '客户增减人选：增加：测试译员1；减少：测试译员0' in content(db,project.id,project.status_change_id)
    project=save([replacement]);assert project.project_status=='client_mixed'
    project=save([{**row,'client_selected':False},replacement])
    project=save([row,{**replacement,'client_selected':False}],reason='测试')
    assert project.project_status=='client_mixed'
    first_event=project.status_change_id
    assert '客户增减人选：增加：测试译员0；减少：测试译员1' in content(db,project.id,first_event)
    project=save([{**row,'client_selected':False},replacement],reason='测试')
    assert project.project_status=='client_mixed' and project.status_change_id!=first_event
    assert '客户增减人选：增加：测试译员1；减少：测试译员0' in content(db,project.id,project.status_change_id)
    project=save([replacement],'in_progress');assert project.project_status=='in_progress'
    project=save([row]);assert project.project_status=='in_progress'
    project=save([row],'ended');assert project.project_status=='ended'
    project=save([replacement]);assert project.project_status=='ended'


@pytest.mark.parametrize('autoflush',[True,False])
def test_create_with_interpreters_and_failure_rolls_back_status(environment,monkeypatch,autoflush):
    db,users=environment
    db.autoflush=autoflush
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',ids)
    monkeypatch.setattr(service,'generate_interpretation_order_no',lambda *_:'IP-261127-STATUS2')
    person=ResourcePerson(id=uuid4(),resource_code='RC-STATUS-NEW',full_name='新建测试译员',status='standby');db.add(person);db.commit()
    items=[{'translator_id':person.id,'client_selected':False}]
    project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='新建测试',interpreter_assignments=items),users[0].id)
    assert project.project_status=='candidates_provided'
    monkeypatch.setattr(service,'_save_finance_draft',lambda *_:(_ for _ in ()).throw(ValueError('模拟后续校验失败')))
    import pytest
    with pytest.raises(ValueError,match='模拟'):
        service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_status=project.project_status,interpreter_assignments=[{**items[0],'client_selected':True}]),users[0].id)
    db.rollback()
    reloaded=service.get_interpretation_project(db,project.id)
    assert reloaded.project_status=='candidates_provided' and not reloaded.interpreter_assignments[0].client_selected

@pytest.mark.parametrize('before,after,label',[
 ([],['a'],'已登记译员'),(['a'],['b'],'译员调整'),(['a'],['a','b'],'增加译员'),
 (['a'],['b','c'],'译员调整+增加'),(['a'],[],'移除译员登记'),
 (['a','b'],['a'],'译员减少'),(['a','b'],['b','c'],'译员增加+移除'),
 (['a','b'],['b','a'],None),(['a'],['a'],None)])
def test_roster_change_descriptions(before,after,label):
    from interpretation_candidate_status import roster_change
    assert roster_change(before,after)==label


def test_repeated_adjustments_and_removal_keep_history_and_counts(environment,monkeypatch):
    db,users=environment
    from interpretation_status_notice import content
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',ids)
    monkeypatch.setattr(service,'generate_interpretation_order_no',lambda *_:'IP-261127-ROSTER')
    people=[ResourcePerson(id=uuid4(),resource_code=f'RC-ROSTER-{n}',full_name=f'译员{n}',status='standby') for n in range(4)]
    db.add_all(people);db.commit()
    project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='人选变更测试'),users[0].id)
    def save(indices,status,label):
        updated=service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_status=project.project_status,interpreter_assignments=[{'translator_id':people[n].id} for n in indices]),users[0].id)
        assert updated.project_status==status
        assert updated.status_change_id
        message=content(db,project.id,updated.status_change_id)
        assert f'（{len(indices)}人）' in message
        expected='客户调整译员' if label in {'译员调整','译员调整+增加'} else label
        assert f'变更原因：{expected}：' in message
        return updated
    project=save([0],'candidates_provided','已登记译员')
    project=save([0,1],'candidates_added','增加译员')
    project=save([2,1],'candidates_adjusted','译员调整')
    project=save([3,1],'candidates_adjusted','译员调整')
    project=save([1,2],'candidates_adjusted','译员增加+移除')
    project=save([1],'candidates_adjusted','译员减少')
    project=save([],'candidates_adjusted','移除译员登记')
    unchanged=service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_status=project.project_status,interpreter_assignments=[]),users[0].id)
    assert unchanged.status_change_id is None
