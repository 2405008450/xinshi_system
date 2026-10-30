import api from './index'
const path='/hr-recruitment/requirements'
export const getRecruitmentRequirements=(params,config={})=>api.get(path,{...config,params})
export const createRecruitmentRequirement=data=>api.post(path,data)
export const updateRecruitmentRequirement=(id,data)=>api.put(`${path}/${id}`,data)
export const deleteRecruitmentRequirement=row=>api.delete(`${path}/${row.id}`,{params:{revision:row.revision}})
const processPath='/hr-recruitment/process'
export const getRecruitmentProcess=(params,config={})=>api.get(processPath,{...config,params})
export const createRecruitmentProcess=data=>api.post(processPath,data)
export const updateRecruitmentProcess=(id,data)=>api.put(`${processPath}/${id}`,data)
export const deleteRecruitmentProcess=row=>api.delete(`${processPath}/${row.id}`,{params:{revision:row.revision}})
