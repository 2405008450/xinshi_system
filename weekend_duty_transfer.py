"""跨月周末值班复制、转移和互换；所有相关月份在同一事务内校验和写入。"""
from datetime import timedelta,date
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,Field
from hr_access import require_hr
from weekly_shift import week_key
from monthly_shift import directory,DEPARTMENTS
from chat_time import now
import weekend_duty as duty
import weekend_duty_management as management


class DutyTransfer(BaseModel):
    source_week:str
    target_week:str
    operation:Literal['copy','move','swap']
    versions:dict[str,int]=Field(min_length=1,max_length=4)
    fixed_revision:int=Field(ge=0)


def dates(start):return [start+timedelta(days=5),start+timedelta(days=6)]
def month_of(day):return day.replace(day=1)


def get_week(db,user,week):
    require_hr(db,user);start=week_key(week);days=dates(start)
    months=sorted({month_of(day) for day in days})
    plans=[duty.get_plan(db,user,month.strftime('%Y-%m')) for month in months]
    return {'ready':duty.ready(db) and management.ready(db),'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
        'assignments':[entry for plan in plans for entry in plan['assignments'] if entry['date'] in {day.isoformat() for day in days}],
        'departments':DEPARTMENTS,'shifts':[],'versions':{plan['month']:plan['revision'] for plan in plans},
        'publication_versions':{plan['month']:plan['publication_revision'] for plan in plans},
        'can_edit':all(plan['can_edit'] for plan in plans),'fixed_revision':management.fixed_revision(db)}


def transfer(db,user,payload:DutyTransfer):
    require_hr(db,user);management.require_ready(db)
    source,target=week_key(payload.source_week),week_key(payload.target_week)
    if source==target:raise HTTPException(422,'请选择不同的两个周末所在周')
    source_dates,target_dates=dates(source),dates(target)
    months=sorted({month_of(day) for day in source_dates+target_dates})
    expected={month.strftime('%Y-%m') for month in months}
    if set(payload.versions)!=expected or any(not isinstance(value,int) or value<0 for value in payload.versions.values()):raise HTTPException(422,'请重新加载所有相关月份的值班版本')
    management.lock_fixed(db);management.lock_months(db,months)
    if management.fixed_revision(db)!=payload.fixed_revision:raise HTTPException(409,'固定周末值班配置已变化，请重新预览')
    legacy={row.month:row for row in db.query(duty.WeekendDutyPlan).filter(duty.WeekendDutyPlan.month.in_(months)).with_for_update().populate_existing().all()}
    drafts={row.month:row for row in db.query(management.WeekendDutyDraft).filter(management.WeekendDutyDraft.month.in_(months)).with_for_update().populate_existing().all()}
    rows={**legacy,**drafts}
    for month in months:
        if payload.versions[month.strftime('%Y-%m')]!=(rows[month].revision if month in rows else 0):raise HTTPException(409,'相关月份的值班安排已变化，请重新预览后确认')
    fixed={month:management.effective(db,[],month) for month in months}
    def movable(days):
        day_keys={day.isoformat() for day in days};values=[]
        for month in {month_of(day) for day in days}:
            fixed_keys={(entry['user_id'],entry['date']) for entry in fixed[month]}
            values.extend(dict(entry) for entry in (rows[month].assignments if month in rows else []) if not entry.get('fixed') and entry['date'] in day_keys and (entry['user_id'],entry['date']) not in fixed_keys)
        return values
    left,right=movable(source_dates),movable(target_dates)
    if not left and (payload.operation!='swap' or not right):raise HTTPException(422,'没有可复制、转移或互换的非固定周末值班安排')
    replacements={day.isoformat():[] for day in target_dates}
    for entry in left:
        copied={**entry,'date':(date.fromisoformat(entry['date'])+(target-source)).isoformat()}
        replacements[copied['date']].append(copied)
    if payload.operation!='copy':
        replacements.update({day.isoformat():[] for day in source_dates})
        if payload.operation=='swap':
            for entry in right:
                copied={**entry,'date':(date.fromisoformat(entry['date'])+(source-target)).isoformat()};replacements[copied['date']].append(copied)
    allowed={person['id'] for person in directory(db,user)['people']}
    affected=sorted({date.fromisoformat(day).replace(day=1) for day in replacements})
    # 先校验全部月份，再写入；不会部分覆盖跨月的周六或周日。
    values_by_month={}
    for month in affected:
        management.assert_editable(db,month)
        before=list(rows[month].assignments) if month in rows else []
        fixed_keys={(entry['user_id'],entry['date']) for entry in fixed[month]}
        previous={(entry['user_id'],entry['date']):entry for entry in before}
        values=[entry for entry in before if (not entry.get('fixed') or (entry['user_id'],entry['date']) in fixed_keys) and (entry['date'] not in replacements or (entry['user_id'],entry['date']) in fixed_keys)]
        for day,entries in replacements.items():
            if date.fromisoformat(day).replace(day=1)!=month:continue
            for entry in entries:
                if (entry['user_id'],day) in fixed_keys:continue
                if entry['user_id'] not in allowed and entry!=previous.get((entry['user_id'],day)):raise HTTPException(422,'待复制人员已不在参与值班的在用名册中')
                values.append({key:entry[key] for key in ('user_id','department','date')})
        values_by_month[month]=values
    for month,values in values_by_month.items():
        previous=rows.get(month);before=list(previous.assignments) if previous else [];row=drafts.get(month)
        if row is None:row=management.WeekendDutyDraft(month=month,revision=previous.revision if previous else 0);db.add(row)
        row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
        management.audit(db,user,month,payload.operation,row.revision,before,values)
    db.commit()
    return {'source':get_week(db,user,source.isoformat()),'target':get_week(db,user,target.isoformat())}
