import api from './index'
export const getOffices=(config={})=>api.get('/office-management',config)
export const getOfficeCities=(config={})=>api.get('/office-management/cities',config)
export const createOffice=data=>api.post('/office-management',data)
export const updateOffice=(id,data)=>api.put(`/office-management/${id}`,data)
