from datetime import date
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Query
from database import get_db
from routers.auth import get_current_user
import attendance_service as service
import attendance_clock as clock
import home_office_service as home
import attendance_delay_start as delay
import attendance_comp_time as comp_time
import attendance_annual_leave as annual

router=APIRouter(prefix='/attendance',tags=['attendance'])

@router.get('/annual-leave')
def annual_mine(year:int=Query(ge=2000,le=9998),db=Depends(get_db),user=Depends(get_current_user)):return annual.overview(db,user,year)
@router.get('/annual-leave/company')
def annual_company(year:int=Query(ge=2000,le=9998),db=Depends(get_db),user=Depends(get_current_user)):return annual.overview(db,user,year,admin=True)
@router.post('/annual-leave/settlement')
def annual_settlement(payload:annual.SettlementWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return annual.adjustment(db,user,payload) if service.desktop_request(request) else reject_mobile()

@router.get('/policy')
def policy(year:int=Query(ge=2000,le=9998),db=Depends(get_db),user=Depends(get_current_user)):return comp_time.overview(db,user,year)
@router.get('/policy/company')
def company_policy(year:int=Query(ge=2000,le=9998),db=Depends(get_db),user=Depends(get_current_user)):return comp_time.overview(db,user,year,admin=True)
@router.post('/comp-time')
def request_comp_time(payload:service.LeaveWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return comp_time.submit(db,user,payload) if service.desktop_request(request) else reject_mobile()
@router.post('/comp-time/{request_id}/cancel')
def cancel_comp_time(request_id:UUID,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return comp_time.cancel(db,user,request_id) if service.desktop_request(request) else reject_mobile()
def reject_mobile():
    from fastapi import HTTPException
    raise HTTPException(403,'手机端仅支持请假和延迟上班申请，其他考勤操作请使用电脑端')
@router.get('/delay-start')
def delay_mine(db=Depends(get_db),user=Depends(get_current_user)):return delay.mine(db,user)
@router.post('/delay-start')
def delay_submit(payload:delay.DelayWrite,db=Depends(get_db),user=Depends(get_current_user)):return delay.submit(db,user,payload)
@router.get('/home-office')
def home_office(requested_date:date|None=None,db=Depends(get_db),user=Depends(get_current_user)):return home.overview(db,user,requested_date)
@router.post('/home-office/qualification')
def home_qualification(payload:home.QualificationWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return home.apply_qualification(db,user,payload) if service.desktop_request(request) else reject_mobile()
@router.post('/home-office/apply')
def home_apply(payload:home.ApplicationWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return home.apply(db,user,payload) if service.desktop_request(request) else reject_mobile()
@router.get('/home-office/company')
def home_company(db=Depends(get_db),user=Depends(get_current_user)):return home.company(db,user)
@router.put('/home-office/usage')
def home_usage(payload:home.UsageWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return home.save_usage(db,user,payload) if service.desktop_request(request) else reject_mobile()
@router.post('/arrival')
def arrival(request:Request,db=Depends(get_db),user=Depends(get_current_user)):return service.auto_check_in(db,user,request)
@router.get('/today')
def today(db=Depends(get_db),user=Depends(get_current_user)):return service.today_status(db,user)
@router.post('/check-in')
def check_in(payload:clock.CheckInWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return clock.check_in(db,user,request,payload)
@router.post('/check-out')
def check_out(payload:clock.CheckOutWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):return service.check_out(db,user,request,payload)
@router.post('/leave/preview')
def preview(payload:service.LeaveWindow,db=Depends(get_db),user=Depends(get_current_user)):
    value=service.preview_leave(db,user,payload)
    return {**value,'settlement':annual.preview(db,user,value['days'])}
@router.post('/leave')
def leave(payload:service.LeaveWrite,db=Depends(get_db),user=Depends(get_current_user)):return service.create_leave(db,user,payload)
@router.get('/mine')
def mine(anchor:date,period:str='week',page:int=Query(1,ge=1),limit:int=Query(50,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):
    return service.attendance_report(db,user,anchor,period,page=page,limit=limit)
@router.get('/report')
def report(anchor:date,period:str='week',keyword:str='',department:str='',page:int=Query(1,ge=1),limit:int=Query(50,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):
    return service.attendance_report(db,user,anchor,period,admin=True,keyword=keyword,department=department,page=page,limit=limit)
