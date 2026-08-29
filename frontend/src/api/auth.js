import api from './index'

export const login = (data) => api.post('/auth/login/json', data)
export const getCurrentSession = () => api.get('/auth/session')
export const logout = () => api.post('/auth/logout')
