"""办公室城市字典、工位设置及人员城市关联；不修改既有 app_user 结构。"""
from datetime import datetime
from uuid import UUID,uuid4,uuid5,NAMESPACE_URL
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import Uuid,String,Integer,DateTime,ForeignKey,UniqueConstraint,inspect,func
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser
from database import get_db
from routers.auth import require_permission,require_any_permission,get_current_user
from chat_time import now,api_time


class OfficeSite(Base):
    __tablename__='organization_office_site'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    city:Mapped[str]=mapped_column(String(100),nullable=False)
    city_key:Mapped[str]=mapped_column(String(100),unique=True,nullable=False)
    name:Mapped[str]=mapped_column(String(200),nullable=False)
    seats:Mapped[int|None]=mapped_column(Integer,nullable=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class OfficeArea(Base):
    __tablename__='organization_office_area'
    office_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('organization_office_site.id'),primary_key=True)
    position:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(100),nullable=False)
    seats:Mapped[int]=mapped_column(Integer,nullable=False)


class EmployeeOffice(Base):
    __tablename__='employee_office_city'
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),primary_key=True)
    office_city_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('organization_office_site.id'),nullable=False,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


DEFAULT_OFFICES=[('广州','广州办公室'),('深圳','深圳南山办公室'),('上海','上海办公室')]
def default_id(city):return uuid5(NAMESPACE_URL,f'xinshi-system:office-city:{city}')
def ready(db):return all(inspect(db.connection()).has_table(name) for name in (OfficeSite.__tablename__,EmployeeOffice.__tablename__))
def require_ready(db):
    if not ready(db):raise HTTPException(503,'办公室及人员城市表尚未初始化')


class OfficeAreaWrite(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    seats:int=Field(ge=0,le=100000,strict=True)
    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        if not value.strip():raise ValueError('请填写区域名称')
        return value.strip()


class OfficeWrite(BaseModel):
    city:str=Field(min_length=1,max_length=100)
    name:str=Field(min_length=1,max_length=200)
    seats:int|None=Field(default=None,ge=0,le=100000,strict=True)
    areas:list[OfficeAreaWrite]|None=Field(default=None,max_length=100)
    @model_validator(mode='after')
    def validate_areas(self):
        if self.areas:
            if len({area.name.casefold() for area in self.areas})!=len(self.areas):raise ValueError('同一办公室的区域名称不能重复')
            total=sum(area.seats for area in self.areas)
            if total>100000:raise ValueError('总工位数不能超过100000')
            if self.seats is not None and self.seats!=total:raise ValueError('总工位数须等于各区域合计')
        return self
    @field_validator('city','name')
    @classmethod
    def clean(cls,value):
        if not value.strip():raise ValueError('请填写城市及办公室名称')
        return value.strip()
class OfficeUpdate(OfficeWrite):revision:int=Field(ge=1)


def validate_city(db,city_id):
    if city_id is None:return
    require_ready(db)
    if db.get(OfficeSite,city_id) is None:raise HTTPException(422,'城市选项不存在，请刷新办公室城市列表后重试')


def write_user(db,user,city_id):
    validate_city(db,city_id)
    if not ready(db):return
    db.flush();row=db.get(EmployeeOffice,user.id)
    if city_id is None:
        if row:db.delete(row)
        return
    if row is None:row=EmployeeOffice(user_id=user.id);db.add(row)
    row.office_city_id=city_id;row.updated_at=now()


def attach_users(db,users):
    ids=[user.id for user in users]
    values={row.user_id:(row.office_city_id,city,name) for row,city,name in db.query(EmployeeOffice,OfficeSite.city,OfficeSite.name).join(OfficeSite,OfficeSite.id==EmployeeOffice.office_city_id).filter(EmployeeOffice.user_id.in_(ids)).all()} if ids and ready(db) else {}
    for user in users:
        user.office_city_id,user.city,user.office_name=values.get(user.id,(None,None,None))
    return users


def filter_users(db,query,city_id=None,active_only=False):
    if active_only:query=query.filter(AppUser.is_active.is_(True))
    if city_id:
        require_ready(db)
        query=query.filter(AppUser.id.in_(db.query(EmployeeOffice.user_id).filter(EmployeeOffice.office_city_id==city_id)))
    return query


def areas_ready(db):return inspect(db.connection()).has_table(OfficeArea.__tablename__)


def office_areas(db,ids):
    values={}
    if ids and areas_ready(db):
        for row in db.query(OfficeArea).filter(OfficeArea.office_id.in_(ids)).order_by(OfficeArea.office_id,OfficeArea.position).all():values.setdefault(row.office_id,[]).append({'name':row.name,'seats':row.seats})
    return values


def catalog(db):
    require_ready(db)
    grouped=db.query(EmployeeOffice.office_city_id,AppUser.is_active,func.count(AppUser.id)).join(AppUser,AppUser.id==EmployeeOffice.user_id).filter(AppUser.is_deleted.is_(False)).group_by(EmployeeOffice.office_city_id,AppUser.is_active).all()
    counts={}
    for city_id,active,count in grouped:
        value=counts.setdefault(city_id,{'actual_people':0,'registered_people':0});value['registered_people']+=count
        if active:value['actual_people']+=count
    rows=db.query(OfficeSite).order_by(OfficeSite.created_at,OfficeSite.city).all()
    areas=office_areas(db,[row.id for row in rows])
    return api_time({'ready':True,'items':[{**{key:getattr(row,key) for key in ('id','city','name','seats','revision','updated_at')},'areas':areas.get(row.id,[]),**counts.get(row.id,{'actual_people':0,'registered_people':0})} for row in rows],'unassigned_people':db.query(AppUser).filter(AppUser.is_deleted.is_(False),AppUser.is_active.is_(True),~AppUser.id.in_(db.query(EmployeeOffice.user_id))).count()})


def save(db,payload,office_id=None):
    require_ready(db)
    row=db.query(OfficeSite).filter_by(id=office_id).with_for_update().populate_existing().first() if office_id else None
    if office_id and row is None:raise HTTPException(404,'办公室不存在')
    if row and row.revision!=payload.revision:raise HTTPException(409,'办公室设置已被修改，请刷新后重试')
    conflict=db.query(OfficeSite).filter(OfficeSite.city_key==payload.city.casefold(),OfficeSite.id!=office_id).first()
    if conflict:raise HTTPException(409,'该城市已有办公室，请编辑现有办公室')
    configured=payload.areas is not None
    if configured and not areas_ready(db):raise HTTPException(503,'办公室区域表尚未初始化')
    areas=[item.model_dump() for item in payload.areas] if configured else office_areas(db,[row.id]).get(row.id,[]) if row else []
    seats=sum(item['seats'] for item in areas) if areas else payload.seats
    if areas and payload.seats is not None and payload.seats!=seats:raise HTTPException(422,'已设置分区工位，请按分区调整，总数自动合计')
    if row is None:row=OfficeSite(id=uuid4(),revision=0,created_at=now());db.add(row)
    row.city=payload.city;row.city_key=payload.city.casefold();row.name=payload.name;row.seats=seats;row.revision+=1;row.updated_at=now()
    if configured:
        db.flush()
        db.query(OfficeArea).filter_by(office_id=row.id).delete(synchronize_session='fetch')
        db.add_all(OfficeArea(office_id=row.id,position=index,**area) for index,area in enumerate(areas))
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'城市已经存在，请刷新后重试')
    return {'message':'办公室设置已保存','id':str(row.id)}


router=APIRouter(prefix='/office-management',tags=['office-management'])
@router.get('/cities',dependencies=[Depends(get_current_user)])
def city_options(db=Depends(get_db)):
    require_ready(db)
    return {'items':[{'id':str(row.id),'city':row.city,'name':row.name} for row in db.query(OfficeSite).order_by(OfficeSite.created_at,OfficeSite.city).all()]}
@router.get('',dependencies=[Depends(require_any_permission('system:users:read','system:users:write'))])
def overview(db=Depends(get_db)):return catalog(db)
@router.post('',dependencies=[Depends(require_any_permission('system:users:write','system:organization:write'))])
def create_office(payload:OfficeWrite,db=Depends(get_db)):return save(db,payload)
@router.put('/{office_id}',dependencies=[Depends(require_any_permission('system:users:write','system:organization:write'))])
def update_office(office_id:UUID,payload:OfficeUpdate,db=Depends(get_db)):return save(db,payload,office_id)
