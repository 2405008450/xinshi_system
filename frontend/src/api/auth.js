import api from './index'
import {chatClientType} from '@/utils/chatDevice'

export const login = (data) => api.post('/auth/login/json', data,{headers:{'X-Client-Type':chatClientType(navigator)}})
export const checkCaptchaRequired = () => api.get('/auth/captcha/required')
export const fetchCaptcha = () => api.get('/auth/captcha')
export const getCurrentSession = () => api.get('/auth/session')
export const changePersonalPassword = (data) => api.put('/auth/password', data)
export const getPersonalMailAccount = () => api.get('/auth/mail-account')
export const savePersonalMailAccount = (authorizationCode) =>
  api.put('/auth/mail-account', { authorization_code: authorizationCode })
export const verifyPersonalMailAccount = () => api.post('/auth/mail-account/verify')
export const deletePersonalMailAccount = () => api.delete('/auth/mail-account')
export const logout = () => api.post('/auth/logout')
