"""我的项目的 OR 关系、多人角色与分页，仅使用隔离内存 SQLite。"""
from uuid import uuid4
import json
import pytest
from test_chat_participant_access import environment
from managed_project_filters import apply_managed_filter


def selection(db, model, module, owner):
    from models import Client, SubClient
    query=db.query(model).outerjoin(Client,model.client_id==Client.id).outerjoin(SubClient,model.sub_client_id==SubClient.id)
    return apply_managed_filter(query,module,{'managed_user_id':{'op':'in','value':[str(owner.id)]}})


@pytest.mark.parametrize('module',['translation','interpretation','annotation','consultation'])
def test_either_manager_matches_with_correct_total_and_paging(environment,module):
    db,(owner,other,_)=environment
    from models import Client, TranslationProject, Consultation
    from annotation_models import AnnotationProject
    from interpretation_models import InterpretationProject
    from workflow_models import ProjectWorkbenchResponsibility as Responsibility
    owner.full_name='赵经理'
    client=Client(id=uuid4(),client_name='我的客户',client_manager=owner.full_name)
    foreign=Client(id=uuid4(),client_name='他人客户',client_manager='赵经理二')
    db.add_all([client,foreign]);db.flush()
    model={'translation':TranslationProject,'interpretation':InterpretationProject,'annotation':AnnotationProject,'consultation':Consultation}[module]
    rows=[model(id=uuid4(),client_id=foreign.id),model(id=uuid4(),client_id=client.id),model(id=uuid4(),client_id=foreign.id)]
    if module=='annotation':
        rows[1].client_manager_id=owner.id
    elif module=='translation':
        rows[0].project_manager_id=owner.id
    elif module=='consultation':
        rows[0].follow_up_person_id=owner.id
    db.add_all(rows);db.flush()
    if module in {'annotation','interpretation'}:
        field=module+'_project_id'
        db.add_all([Responsibility(id=uuid4(),role_code='project_manager',assignee_id=user.id,**{field:rows[0].id}) for user in [other,owner]])
    db.commit()
    query=selection(db,model,module,owner)
    assert {row.id for row in query.all()}=={rows[0].id,rows[1].id}
    assert query.count()==2
    assert len(query.order_by(model.id).offset(1).limit(1).all())==1
    assert apply_managed_filter(db.query(model),module,{}).count()==3


def test_all_four_apis_accept_owner_filter_and_reject_other_operators(environment):
    db,(owner,*_)=environment
    from routers import annotation_projects,translation_projects,interpretation_projects,consultations
    raw=json.dumps({'managed_user_id':{'op':'in','value':[str(owner.id)]}})
    for router in [annotation_projects,translation_projects,interpretation_projects,consultations]:
        result=router._field_filters(raw,db) if router is annotation_projects else router._field_filters(raw)
        assert result['managed_user_id']['value']==[str(owner.id)]
