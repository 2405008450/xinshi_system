"""群聊新增好友的共享日报接口，继承资源开拓模块访问权限。"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from database import get_db
from routers.auth import get_current_user
from resource_development_models import DevelopmentFriendDaily as Daily
from resource_friend_daily_service import FriendWrite, FriendAccountWrite, get_options, add_account, save_daily, serialize

router = APIRouter(prefix='/friend-daily')

@router.get('/options')
def options(db=Depends(get_db), user=Depends(get_current_user)):
    return get_options(db, user)

@router.post('/accounts')
def create_account(payload: FriendAccountWrite, db=Depends(get_db), user=Depends(get_current_user)):
    row = add_account(db, user, payload); db.commit(); return row

@router.get('')
def list_days(start: date | None = None, end: date | None = None, skip: int = Query(0, ge=0), limit: int = Query(7, ge=1, le=31), db=Depends(get_db), user=Depends(get_current_user)):
    end = end or date.today(); start = start or end - timedelta(days=2)
    if start > end: raise HTTPException(422, '开始日期不能晚于结束日期')
    q = db.query(Daily).filter(Daily.work_date.between(start, end))
    return {'total': q.count(), 'items': [serialize(db, r, r.work_date, user, False) for r in q.order_by(Daily.work_date.desc()).offset(skip).limit(limit)]}

@router.get('/{work_date}')
def read_day(work_date: date, db=Depends(get_db), user=Depends(get_current_user)):
    return serialize(db, db.query(Daily).filter_by(work_date=work_date).one_or_none(), work_date, user)

@router.put('/{work_date}')
def write_day(work_date: date, payload: FriendWrite, db=Depends(get_db), user=Depends(get_current_user)):
    row = save_daily(db, user, work_date, payload); db.commit(); return serialize(db, row, work_date, user)
