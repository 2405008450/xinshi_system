from uuid import uuid4
import pytest
from sqlalchemy import inspect
from models import TranslationProject
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from project_customer_sources import ProjectCustomerSource
from tests.test_chat_participant_access import environment

MODELS = [('translation',TranslationProject),('interpretation',InterpretationProject),('annotation',AnnotationProject),('recruitment',RecruitmentProject)]

@pytest.mark.parametrize('module,model', MODELS)
def test_source_round_trip_clear_and_atomic_rollback(environment,module,model):
    db,_=environment
    from tools.apply_project_customer_source_migration import apply_migration
    tables=set(inspect(db.connection()).get_table_names())
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==tables
    project=model(id=uuid4(),order_no='SOURCE-'+module,project_name='来源测试',client_source=' 朋友推荐 ')
    db.add(project);db.commit();project_id=project.id
    assert db.get(ProjectCustomerSource,(module,project_id)).content=='朋友推荐'
    db.expunge_all();project=db.get(model,project_id)
    assert project.client_source=='朋友推荐'
    project.client_source='展会咨询';db.flush();db.rollback()
    db.expunge_all();project=db.get(model,project_id)
    assert project.client_source=='朋友推荐'
    project.client_source='展会咨询';db.commit();db.expunge_all()
    project=db.get(model,project_id);assert project.client_source=='展会咨询'
    # 未提供来源的旧客户端不能清空现有内容。
    project.client_source=None;project.project_name='改名称';db.commit();db.expunge_all()
    project=db.get(model,project_id);assert project.client_source=='展会咨询'
    project.client_source='';db.commit();db.expunge_all()
    assert db.get(model,project_id).client_source==''


def test_same_uuid_isolated_by_project_type(environment):
    db,_=environment
    project_id=uuid4()
    for module,model in MODELS:
        db.add(model(id=project_id,order_no='ISOLATED-'+module,project_name='隔离',client_source=module))
    db.commit();db.expunge_all()
    for module,model in MODELS:
        assert db.get(model,project_id).client_source==module
