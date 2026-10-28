import api from './index'
import {chatClientType} from '@/utils/chatDevice'
export const getTodayAttendance=(config={})=>api.get('/attendance/today',config)
export const checkIn=data=>api.post('/attendance/check-in',data,{headers:{'X-Client-Type':chatClientType(navigator)}})
export const checkOut=data=>api.post('/attendance/check-out',data, {headers:{'X-Client-Type':chatClientType(navigator)}})
export const getAttendanceReport=(params,admin=false,config={})=>api.get(admin?'/attendance/report':'/attendance/mine',{...config,params})
export const previewAttendanceLeave=(data,config={})=>api.post('/attendance/leave/preview',data,config)
export const submitAttendanceLeave=data=>api.post('/attendance/leave',data,{timeout:90000})

export const getHomeOffice=(requested_date,config={})=>api.get('/attendance/home-office',{...config,params:{requested_date}})
export const applyHomeOfficeQualification=data=>api.post('/attendance/home-office/qualification',data)
export const applyHomeOffice=data=>api.post('/attendance/home-office/apply',data)
export const getCompanyHomeOffice=()=>api.get('/attendance/home-office/company')

export const saveHomeOfficeUsage=data=>api.put('/attendance/home-office/usage',data)

export const getDelayStartApplications=()=>api.get('/attendance/delay-start')
export const applyDelayStart=data=>api.post('/attendance/delay-start',data,{timeout:90000})
