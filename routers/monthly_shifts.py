from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import monthly_shift as service
import weekend_duty as duty
import weekly_shift as weekly
import fixed_shift as fixed
router=APIRouter(prefix='/monthly-shifts',tags=['monthly-shifts'])
@router.get('/fixed')
def fixed_config(db:Session=Depends(get_db),user=Depends(get_current_user)):return fixed.get_config(db,user)

@router.put('/fixed')
def save_fixed_config(payload:service.PlanWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return fixed.save_config(db,user,payload)

@router.get('/weekly/mine')
def weekly_mine(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.my_plan(db,user,week)

@router.get('/weekly/overview')
def weekly_overview(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.overview(db,user,week)

@router.post('/weekly/transfer')
def transfer_weekly(payload:weekly.WeekTransfer,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.transfer_plan(db,user,payload)

@router.get('/weekly')
def weekly_plan(week:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.get_plan(db,user,week)

@router.put('/weekly')
def save_weekly(week:str,payload:weekly.WeeklyPlanWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):return weekly.save_plan(db,user,week,payload)

@router.get('/weekend-duty')
def duty_plan(month:str,db:Session=Depends(get_db),user=Depends(get_current_user)):return duty.get_plan(db,user,month)

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
