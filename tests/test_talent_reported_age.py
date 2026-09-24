from datetime import date
from types import SimpleNamespace
import pytest
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonCreate
from tools.prepare_wenzhou_talents import merge_native_place

def test_reported_age_does_not_invent_birthday():
    payload=ResourcePersonCreate(full_name='测试人才',reported_age=24)
    assert payload.birth_date is None and payload.birth_year_month is None
    person=SimpleNamespace(birth_year_month=None,birth_date=None,reported_age=24)
    assert ResourcePerson.current_age.fget(person)==24

@pytest.mark.parametrize('value',[None,0,120])
def test_reported_age_preserves_empty_and_zero(value):
    person=SimpleNamespace(birth_year_month=None,birth_date=None,reported_age=value)
    assert ResourcePerson.current_age.fget(person)==value

@pytest.mark.parametrize('value',[-1,121])
def test_reported_age_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        ResourcePersonCreate(full_name='测试人才',reported_age=value)

def test_birth_information_takes_priority():
    today=date.today()
    p=SimpleNamespace(birth_year_month=f'{today.year-20}-01',birth_date=None,reported_age=24)
    assert ResourcePerson.current_age.fget(p)==20
    p.birth_year_month=None
    p.birth_date=date(today.year-19,1,1)
    assert ResourcePerson.current_age.fget(p)==19

@pytest.mark.parametrize('city,district,expected',[
    ('温州','乐清','温州 / 乐清'),('温州市龙湾区','温州市龙湾区','温州市龙湾区'),
    ('温州','温州市鹿城区','温州市鹿城区'),(None,None,None),('温州',None,'温州')])
def test_native_place_preserves_source_without_duplicate_prefix(city,district,expected):
    assert merge_native_place(city,district)==expected
