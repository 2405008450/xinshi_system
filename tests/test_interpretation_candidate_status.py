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
    def save(items,status=None):
        return service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_name=project.project_name,project_status=status or project.project_status,interpreter_assignments=items),users[0].id)
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
    project=save([replacement]);assert project.project_status=='client_changed'
    project=save([replacement]);assert project.project_status=='client_changed'
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
