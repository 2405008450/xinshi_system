import api from './index'
export const getFixedShiftConfig=()=>api.get('/monthly-shifts/fixed')
export const saveFixedShiftConfig=data=>api.put('/monthly-shifts/fixed',data)
export const getWeeklyShiftPlan=(week,config={})=>api.get('/monthly-shifts/weekly',{...config,params:{week}})
export const getWeeklyShiftOverview=(week,config={})=>api.get('/monthly-shifts/weekly/overview',{...config,params:{week}})
export const saveWeeklyShiftPlan=(week,data)=>api.put('/monthly-shifts/weekly',data,{params:{week}})
export const syncWeeklyShiftPlan=(week,data)=>api.post('/monthly-shifts/weekly/sync',data,{params:{week}})
export const enableWeeklyShiftEdit=(week,data)=>api.post('/monthly-shifts/weekly/enable-edit',data,{params:{week}})
export const getWeeklyShiftHistory=(week,config={})=>api.get('/monthly-shifts/weekly/history',{signal:config.signal,params:{week,public:config.public??true,offset:config.offset||0,limit:50}})
export const transferWeeklyShiftPlan=data=>api.post('/monthly-shifts/weekly/transfer',data)
export const getMyWeeklyShift=(week,config={})=>api.get('/monthly-shifts/weekly/mine',{...config,params:{week}})
export const getWeekendDutyPlan=(month,config={})=>api.get('/monthly-shifts/weekend-duty',{...config,params:{month}})
export const saveWeekendDutyPlan=(month,data)=>api.put('/monthly-shifts/weekend-duty',data,{params:{month}})
export const getFixedWeekendDuty=()=>api.get('/monthly-shifts/weekend-duty/fixed')
export const saveFixedWeekendDuty=data=>api.put('/monthly-shifts/weekend-duty/fixed',data)
export const getWeekendDutyWeek=(week,config={})=>api.get('/monthly-shifts/weekend-duty/weekly',{...config,params:{week}})
export const transferWeekendDuty=data=>api.post('/monthly-shifts/weekend-duty/transfer',data)
export const syncWeekendDuty=(month,data)=>api.post('/monthly-shifts/weekend-duty/sync',data,{params:{month}})
export const enableWeekendDutyEdit=(month,data)=>api.post('/monthly-shifts/weekend-duty/enable-edit',data,{params:{month}})
export const getWeekendDutyOverview=(month,config={})=>api.get('/monthly-shifts/weekend-duty/overview',{...config,params:{month}})
export const getWeekendDutyHistory=(month,config={})=>api.get('/monthly-shifts/weekend-duty/history',{signal:config.signal,params:{month,public:config.public??true,offset:config.offset||0,limit:50}})
let directoryRequest=null,directoryOwner=''
export const getMonthlyShiftDirectory=()=>{
  const owner=localStorage.getItem('user_id')||''
  if(directoryRequest&&directoryOwner===owner)return directoryRequest
  directoryOwner=owner
  const request=api.get('/monthly-shifts/directory',{timeout:30000})
  directoryRequest=request
  request.finally(()=>{if(directoryRequest===request)directoryRequest=null}).catch(()=>{})
  return request
}
export const getMonthlyShiftPlan=(month,config={})=>api.get('/monthly-shifts',{...config,params:{month}})
export const saveMonthlyShiftPlan=(month,data)=>api.put('/monthly-shifts',data,{params:{month}})
export const getMyMonthlyShift=(month,config={})=>api.get('/monthly-shifts/mine',{...config,params:{month}})
