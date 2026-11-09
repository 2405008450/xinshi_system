from types import SimpleNamespace
from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from models import Translator
from resource_models import ResourcePerson,ResourceCapability
from interpretation_resource_selection import resolve_interpreter_resources
from routers.talent_options import read_talent_options


def test_full_library_search_does_not_filter_capability_or_status(monkeypatch):
    captured={}
    def query(_db,**filters):captured.update(filters);return []
    monkeypatch.setattr('routers.talent_options.get_talents',query)
    monkeypatch.setattr('routers.talent_options.can_view_talent_contacts',lambda *_:False)
    read_talent_options(keyword='曹柳云',limit=100,db=object(),current_user=SimpleNamespace(id=uuid4()))
    assert captured['keyword']=='曹柳云'
    assert captured['capability_type'] is None and captured['capability_status'] is None
    assert captured['statuses'] is None


def test_resource_without_interpretation_capability_can_be_assigned(environment):
    db,_=environment
    person=ResourcePerson(id=uuid4(),resource_code='ALL-0001',full_name='曹柳云',status='pending_activation')
    db.add(person);db.flush()
    before=db.query(ResourceCapability).count()
    first=resolve_interpreter_resources(db,{person.id})
    assert first[person.id]==person.id
    bridge=db.get(Translator,first[person.id])
    assert bridge.translator_name=='曹柳云' and bridge.resource_person_id==person.id
    assert db.query(ResourceCapability).count()==before
    assert resolve_interpreter_resources(db,{person.id})==first
    assert db.query(Translator).filter_by(resource_person_id=person.id).count()==1


def test_existing_bridge_and_historical_assignments_are_preserved(environment):
    db,_=environment
    person=ResourcePerson(id=uuid4(),resource_code='ALL-0002',full_name='资源人员',status='standby')
    bridge=Translator(id=uuid4(),resource_person_id=person.id,translator_name=person.full_name)
    historical=Translator(id=uuid4(),translator_name='历史译员')
    db.add_all([person,bridge,historical]);db.flush()
    assert resolve_interpreter_resources(db,{person.id})[person.id]==bridge.id
    assert resolve_interpreter_resources(db,{historical.id},{historical.id})[historical.id]==historical.id
    with pytest.raises(ValueError):resolve_interpreter_resources(db,{uuid4()})
