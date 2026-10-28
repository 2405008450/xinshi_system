from fastapi import APIRouter,Depends,Query,Request,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import monthly_shift as service
import weekend_duty as duty
import weekly_shift as weekly
import fixed_shift as fixed
import weekly_shift_publication as publication
import weekend_duty_management as duty_management
import weekend_duty_transfer as duty_transfer
def desktop_writes(request:Request):
    import re
    if request.method in ('POST','PUT','PATCH','DELETE') and (re.search(r'Android|iPhone|iPad|iPod|Mobile',request.headers.get('user-agent',''),re.I) or request.headers.get('sec-ch-ua-mobile')=='?1' or request.headers.get('x-client-type')=='mobile'):
        raise HTTPException(403,'排班考勤的手机操作仅支持请假和延迟上班申请，排班调整请用电脑端')
router=APIRouter(prefix='/monthly-shifts',tags=['monthly-shifts'],dependencies=[Depends(desktop_writes)])
@router.get('/fixed')
def fixed_config(db:Session=Depends(get_db),user=Depends(get_current_user)):return fixed.get_config(db,user)

@router.put('/fixed')
def save_fixed_config(payload:service.PlanWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return fixed.save_config(db,user,payload)

@router.get('/weekly/mine')
def weekly_mine(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.my_plan(db,user,week)

@router.get('/weekly/overview')
def weekly_overview(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.overview(db,user,week)

@router.get('/weekly/history')
def weekly_history(week:str,public:bool=False,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),user=Depends(get_current_user)):return publication.history(db,user,week,public,offset,limit)

@router.post('/weekly/sync')
def sync_weekly(week:str,payload:publication.SyncWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return publication.publish(db,user,week,payload)

@router.post('/weekly/enable-edit')
def enable_weekly_edit(week:str,payload:publication.SyncWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return publication.enable_edit(db,user,week,payload)

@router.post('/weekly/transfer')
def transfer_weekly(payload:weekly.WeekTransfer,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.transfer_plan(db,user,payload)

@router.get('/weekly')
def weekly_plan(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.get_plan(db,user,week)

@router.put('/weekly')
def save_weekly(week:str,payload:weekly.WeeklyPlanWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.save_plan(db,user,week,payload)

@router.get('/weekend-duty')
def duty_plan(month:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty.get_plan(db,user,month)

@router.get('/weekend-duty/fixed')
def duty_fixed(db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.get_fixed(db,user)

@router.put('/weekend-duty/fixed')
def save_duty_fixed(payload:duty_management.FixedWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.save_fixed(db,user,payload)

@router.get('/weekend-duty/weekly')
def duty_week(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_transfer.get_week(db,user,week)

@router.post('/weekend-duty/transfer')
def transfer_duty(payload:duty_transfer.DutyTransfer,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_transfer.transfer(db,user,payload)

@router.post('/weekend-duty/sync')
def sync_duty(month:str,payload:publication.SyncWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.publish(db,user,month,payload)

@router.post('/weekend-duty/enable-edit')
def enable_duty_edit(month:str,payload:publication.SyncWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.enable_edit(db,user,month,payload)

@router.get('/weekend-duty/overview')
def duty_overview(month:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.overview(db,user,month)

@router.get('/weekend-duty/history')
def duty_history(month:str,public:bool=False,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),user=Depends(get_current_user)):return duty_management.history(db,user,month,public,offset,limit)

@router.put('/weekend-duty')
def save_duty(month:str,payload:duty.DutyWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty.save_plan(db,user,month,payload)

@router.get('/directory')
def directory(db:Session=Depends(get_db),user=Depends(get_current_user)):return service.directory(db,user)
@router.get('/mine')
def mine(month:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return service.my_plan(db,user,month)
@router.get('')
def plan(month:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return service.get_plan(db,user,month)
@router.put('')
def save(month:str,payload:service.PlanWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return service.save_plan(db,user,month,payload)
