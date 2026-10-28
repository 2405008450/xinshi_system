"""午间加班声明、时段校验及已确认工作报告的考勤计回。"""
import re
from datetime import timedelta


def window(metadata):
    def minute(value):
        if not isinstance(value,str) or not re.fullmatch(r'\d{2}:\d{2}',value):raise ValueError('请填写中午加班开始及结束时间')
        hour,minutes=map(int,value.split(':'))
        if hour>23 or minutes>59:raise ValueError('中午加班时间无效')
        return hour*60+minutes
    left,right=minute(metadata.get('lunch_start')),minute(metadata.get('lunch_end'))
    if not 720<=left<right<=810:raise ValueError('中午加班须在12:00至13:30内，结束时间晚于开始时间')
    return left,right


def validate_item(metadata,duration,source_type):
    if 'lunch_overtime' in metadata and not isinstance(metadata['lunch_overtime'],bool):raise ValueError('中午加班标记无效')
    if not metadata.get('lunch_overtime'):return
    if source_type=='system_event':raise ValueError('系统记录不能改为中午加班')
    if metadata.get('lunch_overtime_confirmed') is not True:raise ValueError('请确认中午确实加班且未顺延下午上班时间')
    if not metadata.get('report_types'):raise ValueError('中午加班须填写任务/项目类型')
    left,right=window(metadata)
    if duration!=right-left:raise ValueError('中午加班耗时必须与实际起止时段一致')


def validate_report(items):
    windows=sorted(window(item.display_metadata or {}) for item in items or [] if (item.display_metadata or {}).get('lunch_overtime'))
    if any(right>next_left for (_left,right),(next_left,_right) in zip(windows,windows[1:])):raise ValueError('中午加班项目时段不能重叠，避免重复计算加班')


def reports(db,user_ids,start,end):
    from task_models import DailyReport,DailyReportItem
    rows=db.query(DailyReport,DailyReportItem).join(DailyReportItem,DailyReportItem.report_id==DailyReport.id).filter(DailyReport.user_id.in_(user_ids),DailyReport.report_date>=start,DailyReport.report_date<=end,DailyReport.status=='finalized').all() if user_ids else []
    result={}
    for report,item in rows:
        metadata=item.display_metadata or {}
        if not metadata.get('lunch_overtime'):continue
        try:validate_item(metadata,item.duration_minutes,item.source_type);left,right=window(metadata)
        except ValueError:continue
        value=result.setdefault((report.user_id,report.report_date),{'windows':[],'projects':[]})
        value['windows'].append((left,right));value['projects'].append({'project':item.task_name,'order_no':metadata.get('order_no',''),'types':metadata.get('report_types',[]),'start':metadata['lunch_start'],'end':metadata['lunch_end'],'minutes':right-left})
    return result


def credited(value,day,closed_rows):
    import attendance_service as attendance
    actual=attendance.merged([(attendance.stamp(row.check_in),attendance.stamp(row.check_out)) for row in closed_rows if row.check_out])
    claimed=attendance.merged([(attendance.midnight(day)+timedelta(minutes=left),attendance.midnight(day)+timedelta(minutes=right)) for left,right in value['windows']])
    reported=sum((b-a).total_seconds()/60 for a,b in claimed)
    minutes=round(sum(attendance.overlap(a,b,left,right) for a,b in actual for left,right in claimed)/60,2)
    return round(reported,2),minutes
