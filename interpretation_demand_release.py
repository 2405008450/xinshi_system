"""口译需求发布文案及上海三次/深圳一次的幂等轮换。"""
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import Column, String, Integer, DateTime, Uuid, CheckConstraint, func, inspect, text
from sqlalchemy.orm import Session
from models import Base
from database import get_db
from annotation_progress_time import business_now
from interpretation_models import InterpretationLanguage
from interpretation_schemas import InterpretationNamePreviewRequest
from interpretation_service import format_interpretation_date_ranges
from interpretation_location_summary import interpretation_cities
from routers.auth import require_permission

class InterpretationDemandReleaseOffice(Base):
    __tablename__ = 'interpretation_demand_release_office'
    __table_args__ = (CheckConstraint("office IN ('上海','深圳')", name='ck_interpretation_demand_release_office'),)
    request_key = Column(Uuid, primary_key=True)
    sequence = Column(Integer, nullable=False, unique=True)
    office = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)

class DemandReleaseRequest(InterpretationNamePreviewRequest):
    request_key: UUID
    project_name: str = Field(min_length=1, max_length=1000)
    interpretation_domain: str = Field(min_length=1, max_length=10000)
    task_description: str = Field(min_length=1, max_length=10000)

    @field_validator('project_name','interpretation_domain','task_description')
    @classmethod
    def required_text(cls, value):
        if not value.strip():raise ValueError('请填写项目名称、领域/行业/产品和工作内容')
        return value.strip()


def choose_office(db, request_key, locations):
    location = ' '.join(locations)
    if '深圳' in location:return '深圳'
    if '上海' in location:return '上海'
    if not inspect(db.connection()).has_table(InterpretationDemandReleaseOffice.__tablename__):
        raise HTTPException(503, '需求发布公司轮换表尚未初始化')
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(261125041)'))
    prior = db.get(InterpretationDemandReleaseOffice, request_key)
    if prior:return prior.office
    sequence = (db.query(func.max(InterpretationDemandReleaseOffice.sequence)).scalar() or 0) + 1
    office = '深圳' if sequence % 4 == 0 else '上海'
    db.add(InterpretationDemandReleaseOffice(request_key=request_key, sequence=sequence, office=office))
    db.flush()
    return office


def title_without_date(payload):
    name = payload.project_name.strip()
    prefix = format_interpretation_date_ranges(payload.time_ranges)
    if prefix and name.startswith(prefix):return name[len(prefix):].lstrip(' -—；:：')
    # 兼容手工填写的中文/数字日期前缀，保留名称中的其他数字和地点。
    date = r'(?:\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}(?:\s*[-—至]\s*\d{1,2})?\s*日|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})'
    return re.sub(r'^\s*'+date+r'(?:\s*[（(](?:上午|下午|全天|晚上|早上)[）)])?\s*[-—:：]?\s*', '', name).strip() or name


def build_release(payload, directions, office):
    count = sum(item.required_count or 0 for item in payload.language_directions)
    cities = interpretation_cities(payload)
    city = '、'.join(cities) or 'XXXX'
    languages = '；'.join(directions)
    staffing = ('语言与人数：'+'；'.join(f'{label}方向，{item.required_count}人' for label,item in zip(directions,payload.language_directions))
                if len(payload.language_directions)>1 else f'需求人数：{count}人\n项目语言：{languages}')
    company = f'信实{office}翻译公司'
    from annotation_progress_time import business_datetime
    times=[]
    for period in payload.time_ranges:
        start,end=business_datetime(period.scheduled_start),business_datetime(period.scheduled_end)
        times.append(start.strftime('%Y年%m月%d日 %H:%M')+'—'+end.strftime('%H:%M' if start.date()==end.date() else '%Y年%m月%d日 %H:%M'))
    return f"""{title_without_date(payload)}（{company}）

{staffing}
项目时间：{'；'.join(times)}
项目地点：{city}
领域/行业/产品：{payload.interpretation_domain}
工作内容：{payload.task_description}
应聘要求：{languages}口译流利，临场应变能力强。XXXXXXXXX优先考虑；居住在{city}及周边地区的优先考虑。

🙏投递格式：

#没有这边微信的（号满）-请优先投邮箱hr4@xinshifanyi.com.cn：

简历 ➕"姓名+现居地 +可看看优惠的-报价xx元 一天 项目总计 ，其他费用如有说明；是否全含   +有没有做过相关的-请备注说明个人情况/经验背景等--这边提交   +Telephone请附一起   +{payload.project_name}（{company}招募）+兼职来源+相关证书如有(毕业学位双证、语言水平证明之类等）”

🌹咨询联系：优先投递邮箱（高效）👉hr4@xinshifanyi.com.cn，谢谢！！

🌹已加 口译微信的HR1-Alice//HR2-Mary微信的（号满），直接投递，不要重复添加！！{{没有前面2个的-其他临时储备沟通微信HR4-Emma（微信17324319719//Geeksbin）-注意备注语种名字和咨询兼职项目}}

信实翻译公司深耕口译领域十余载，专业覆盖国际会议口译、同声传译、同传设备租赁、交替传译、商务口译五大核心场景。公司持有ISO三大国际权威认证，核心译员均具备CATTI一级资质及3年以上全职经验，曾为众多全球500强企业国际会议提供稳定口译支持。依托“会前-会中-会后”闭环服务，精准把控行业术语，保障跨语言沟通零误差，是企业国际化沟通的信赖之选。"""

router = APIRouter(prefix='/projects/interpretation-demand-release', tags=['interpretation-demand-release'])

@router.post('', dependencies=[Depends(require_permission('projects:write'))])
def generate(payload: DemandReleaseRequest, db: Session = Depends(get_db)):
    if not payload.locations or not payload.time_ranges or not payload.language_directions:
        raise HTTPException(422,'请先填写项目时间、项目地点和口译方向')
    if not interpretation_cities(payload):
        raise HTTPException(422,'请填写项目地点的城市')
    ids = {language for direction in payload.language_directions for language in direction.language_ids}
    catalog = {row.id:row.label for row in db.query(InterpretationLanguage).filter(InterpretationLanguage.id.in_(ids)).all()}
    if ids - catalog.keys():raise HTTPException(422,'所选口译语种不存在')
    if any(not direction.required_count for direction in payload.language_directions):
        raise HTTPException(422,'请填写各口译方向的需求人数')
    directions = [' ↔ '.join(catalog[language] for language in direction.language_ids) for direction in payload.language_directions]
    office = choose_office(db,payload.request_key,payload.locations)
    content = build_release(payload,directions,office)
    db.commit()
    return {'content':content,'office':office}
