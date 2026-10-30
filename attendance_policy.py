"""迟到折算请假与自然月追责。来源直接关联打卡，不复制生成真实请假单。"""
from datetime import date,datetime,timedelta
from sqlalchemy import inspect
from attendance_models import AttendanceDay,AttendanceLeave,AttendanceClockSession
from models import EmployeeLeave
import attendance_service as service
from chat_time import now


def month_end(day):
    return (day.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)


def clock_sources(db,ids,start,end):
    if not ids:return [],[]
    sessions=db.query(AttendanceClockSession).filter(AttendanceClockSession.user_id.in_(ids),AttendanceClockSession.day>=start,AttendanceClockSession.day<=end).all() if inspect(db.connection()).has_table('attendance_clock_session') else []
    occupied={(row.user_id,row.day) for row in sessions}
    old=db.query(AttendanceDay).filter(AttendanceDay.user_id.in_(ids),AttendanceDay.day>=start,AttendanceDay.day<=end).all()
    leaves=db.query(EmployeeLeave).filter(EmployeeLeave.employee_id.in_(ids),EmployeeLeave.start_date<service.midnight(end+timedelta(days=1)).replace(tzinfo=None),EmployeeLeave.end_date>service.midnight(start).replace(tzinfo=None)).all()
    return [*sessions,*[row for row in old if (row.user_id,row.day) not in occupied]],leaves


def lateness_events(rows,leaves):
    result=[]
    for row in rows:
        own=[item for item in leaves if item.employee_id==row.user_id]
        value=service.metrics(row,own)
        if not value['late_count']:continue
        # 精确列出扣除正式请假、班间休息和既有15分钟宽限后的应出勤区间。
        windows=service.merged([(service.stamp(item.start_date),service.stamp(item.end_date)) for item in own])
        pieces=[];check_in=service.stamp(row.check_in)
        for left,right in service.intervals(row.day,row.shift_snapshot):
            override=row.shift_snapshot.get('late_start_at')
            if override:left=max(left,service.stamp(datetime.fromisoformat(override)))
            remaining=[(left,min(right,check_in))] if left<check_in else []
            for start,end in windows:
                remaining=[part for a,b in remaining for part in ((a,min(b,start)),(max(a,end),b)) if part[1]>part[0]]
            pieces.extend(remaining)
        grace=service.LATE_GRACE_SECONDS;spans=[]
        for left,right in pieces:
            skipped=min(grace,(right-left).total_seconds());grace-=skipped;left+=timedelta(seconds=skipped)
            if right>left:spans.append({'start_at':left,'end_at':right,'minutes':round((right-left).total_seconds()/60,2)})
        result.append({'id':f'late:{row.id}','clock_id':str(row.id),'user_id':str(row.user_id),'day':row.day.isoformat(),'month':row.day.strftime('%Y-%m'),'source':'lateness','source_label':'迟到折算请假','start_at':spans[0]['start_at'],'end_at':spans[-1]['end_at'],'minutes':value['late_minutes'],'spans':spans,'reason':'迟到累计请假（保留原有15分钟宽限；不重复扣正式请假）'})
    return sorted(result,key=lambda row:(row['start_at'],row['id']))


def free_late_count(overtime_minutes):
    return 1 if overtime_minutes<=600 else 3 if overtime_minutes<=1200 else 5


def accountability(events,balances,ids,start,end):
    grouped={}
    for uid in ids:
        day=start.replace(day=1)
        while day<=end:
            key=(str(uid),day.strftime('%Y-%m'))
            grouped[key]={'user_id':key[0],'month':key[1],'overtime_minutes':0,'late_count':0,'late_leave_minutes':0,'events':[],'provisional':month_end(day)>=now().date()}
            day=month_end(day)+timedelta(days=1)
    for balance in balances:
        if (balance['user_id'],balance['month']) in grouped:grouped[(balance['user_id'],balance['month'])]['overtime_minutes']=balance['overtime_minutes']
    for event in events:
        item=grouped.get((event['user_id'],event['month']))
        if item is not None:item['events'].append(event)
    for item in grouped.values():
        allowed=free_late_count(item['overtime_minutes']);item['free_count']=allowed
        item['late_count']=len(item['events']);item['late_leave_minutes']=round(sum(row['minutes'] for row in item['events']),2)
        item['linked_count']=max(0,item['late_count']-allowed)
        item['events']=[{**row,'ordinal':index+1,'bonus_linked':index>=allowed} for index,row in enumerate(item['events'])]
        item['status']='待开发：年终奖挂钩记录' if item['linked_count'] else '未达到追责次数'
    return list(grouped.values())


def monthly(db,ids,start,end,balances=None):
    from attendance_clock import monthly_balances
    left=start.replace(day=1);right=month_end(end)
    rows,leaves=clock_sources(db,ids,left,right)
    events=lateness_events(rows,leaves)
    return accountability(events,monthly_balances(db,ids,left,right) if balances is None else balances,ids,left,right)


def attach_report(db,daily,leave_items,people,start,end,balances):
    ids=[__import__('uuid').UUID(uid) for uid in people]
    policy=monthly(db,ids,start,end,balances)
    events=[event for item in policy for event in item['events'] if start.isoformat()<=event['day']<=end.isoformat()]
    for item in leave_items:item.update(source='application',source_label='申请请假')
    for event in events:
        person=people[event['user_id']]
        leave_items.append({**event,'name':person['name']})
        key=(event['user_id'],date.fromisoformat(event['day']))
        row=daily[key]
        row.setdefault('requested_leave_minutes',row['leave_minutes'])
        row['late_leave_minutes']=round(row.get('late_leave_minutes',0)+event['minutes'],2)
        row['leave_minutes']=round(row['leave_minutes']+event['minutes'],2)
        row.setdefault('late_leave_events',[]).append(event)
    return policy
