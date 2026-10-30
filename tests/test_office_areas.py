"""办公室区域及总数一致性；全部使用隔离 SQLite。"""
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import inspect
from test_chat_participant_access import environment
from test_office_management import offices
import office_management as office
from tools.configure_guangzhou_office_areas import configure,AREAS


def test_guangzhou_four_areas_total_other_offices_untouched_and_idempotent(offices):
 db,users=offices
 before={row.city:(row.seats,row.revision) for row in db.query(office.OfficeSite).all()}
 assert configure(db,1,False)['result']=='preview'
 assert db.get(office.OfficeSite,office.default_id('广州')).seats is None
 assert configure(db,1,True)['result']=='saved'
 value=next(row for row in office.catalog(db)['items'] if row['city']=='广州')
 assert value['areas']==AREAS and value['seats']==35 and value['actual_people']==0
 assert configure(db,2,True)['result']=='unchanged'
 for row in db.query(office.OfficeSite).all():
  if row.city!='广州':assert (row.seats,row.revision)==before[row.city]
 with pytest.raises(RuntimeError):configure(db,1,True)


def test_edit_omit_clear_and_stale_areas(offices):
 db,_=offices;uid=office.default_id('广州')
 office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',areas=AREAS,revision=1),uid)
 office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',revision=2),uid)
 assert office.office_areas(db,[uid])[uid]==AREAS and db.get(office.OfficeSite,uid).seats==35
 with pytest.raises(HTTPException):office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',seats=36,revision=3),uid)
 changed=[{**item,'seats':30 if item['name']=='大办公区' else item['seats']} for item in AREAS]
 office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',areas=changed,revision=3),uid)
 assert db.get(office.OfficeSite,uid).seats==39
 with pytest.raises(HTTPException):office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',areas=AREAS,revision=3),uid)
 office.save(db,office.OfficeUpdate(city='广州',name='广州办公室',areas=[],seats=10,revision=4),uid)
 assert office.office_areas(db,[uid]).get(uid,[])==[] and db.get(office.OfficeSite,uid).seats==10


@pytest.mark.parametrize('areas,seats', [([{'name':'区域','seats':-1}],None),([{'name':'区域','seats':1.5}],None),([{'name':' ','seats':1}],None),([{'name':'A','seats':1},{'name':' a ','seats':2}],None),(AREAS,34)])
def test_area_validation(areas,seats):
 with pytest.raises(ValidationError):office.OfficeWrite(city='广州',name='广州办公室',areas=areas,seats=seats)


def test_area_migration_idempotent_no_existing_columns_changed(offices):
 from tools.apply_office_area_migration import apply_migration
 db,_=offices
 office.OfficeArea.__table__.drop(db.connection());db.commit()
 before=[column['name'] for column in inspect(db.connection()).get_columns('organization_office_site')]
 apply_migration(db.connection());apply_migration(db.connection());db.commit()
 assert before==[column['name'] for column in inspect(db.connection()).get_columns('organization_office_site')]
 assert db.query(office.OfficeSite).count()==3 and db.query(office.OfficeArea).count()==0
