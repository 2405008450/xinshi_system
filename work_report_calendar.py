"""国务院发布的中国大陆放假调休安排；未知年份不回退到普通周末。"""
from datetime import date,timedelta
from fastapi import HTTPException

CALENDARS={
 2025:{'holidays':[('01-01','01-01'),('01-28','02-04'),('04-04','04-06'),('05-01','05-05'),('05-31','06-02'),('10-01','10-08')],
       'workdays':['01-26','02-08','04-27','09-28','10-11'],
       'source':'https://www.forestry.gov.cn/c/www/szxx/594663.jhtml'},
 2026:{'holidays':[('01-01','01-03'),('02-15','02-23'),('04-04','04-06'),('05-01','05-05'),('06-19','06-21'),('09-25','09-27'),('10-01','10-07')],
       'workdays':['01-04','02-14','02-28','05-09','09-20','10-10'],
       'source':'https://www.beijing.gov.cn/cs/gncs/zcwj/202603/t20260327_4568275.html'}
}


def is_workday(day):
    calendar=CALENDARS.get(day.year)
    if not calendar:raise HTTPException(422,f'{day.year}年节假日及调休日历尚未配置，不能统计')
    value=day.strftime('%m-%d')
    if value in calendar['workdays']:return True
    if any(start<=value<=end for start,end in calendar['holidays']):return False
    return day.weekday()<5


def period_bounds(anchor,period):
    if period=='day':return anchor,anchor
    if period=='week':
        start=anchor-timedelta(days=anchor.weekday());return start,start+timedelta(days=6)
    if period=='month':
        start=anchor.replace(day=1);end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1);return start,end
    raise HTTPException(422,'请选择日、周或月统计')
