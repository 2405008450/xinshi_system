import json
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import TranslationProject,TranslationSubOrder
from manuscript_models import ManuscriptArrangement,ManuscriptDispatch
from routers.translation_projects import _field_filters
import crud

def test_assignment_filter_matches_displayed_parent_assignments_and_pagination(environment):
    db,_=environment
    projects=[]
    for kind in ('confirmed','legacy','cancelled','draft','suborder','empty'):
        row=TranslationProject(id=uuid4(),order_no='TP-ASSIGN-'+kind,project_name=kind,translator_id=uuid4() if kind=='legacy' else None)
        db.add(row);db.flush();projects.append(row)
        if kind in ('legacy','empty'):continue
        dispatch=ManuscriptDispatch(id=uuid4(),translation_project_id=row.id,status='draft' if kind=='draft' else 'confirmed',confirmed_at=None if kind=='draft' else datetime(2026,11,6,tzinfo=timezone(timedelta(hours=8))))
        db.add(dispatch);db.flush()
        child=None
        if kind=='suborder':
            child=TranslationSubOrder(id=uuid4(),parent_project_id=row.id,sub_order_no=row.order_no+'.001',sub_project_name='子订单')
            db.add(child);db.flush()
        db.add(ManuscriptArrangement(id=uuid4(),dispatch_id=dispatch.id,translation_project_id=row.id,sub_order_id=child.id if child else None,translator_id=uuid4(),translator_name_snapshot='测试译员',status='cancelled' if kind=='cancelled' else 'confirmed'))
    db.commit()
    def query(assigned):
        filters=_field_filters(json.dumps({'translator_assigned':{'op':'eq','value':assigned}}))
        return crud._apply_translation_project_filters(db.query(TranslationProject),field_filters=filters)
    assert {row.id for row in query(True)}=={projects[0].id,projects[1].id}
    assert {row.id for row in query(False)}=={row.id for row in projects[2:]}
    assert query(True).count()==2
    assert len(query(True).order_by(TranslationProject.order_no).offset(1).limit(1).all())==1
