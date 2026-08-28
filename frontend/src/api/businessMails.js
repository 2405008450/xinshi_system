import api from './index'

export const getMailStatus = () => api.get('/mail-settings/status')
export const getMailGroups = () => api.get('/mail-settings/groups')
export const createMailGroup = (data) => api.post('/mail-settings/groups', data)
export const updateMailGroup = (id, data) => api.put(`/mail-settings/groups/${id}`, data)
export const deleteMailGroup = (id) => api.delete(`/mail-settings/groups/${id}`)
export const getMailPolicy = (projectType) => api.get(`/mail-settings/policies/${projectType}`)
export const updateMailPolicy = (projectType, data) => api.put(`/mail-settings/policies/${projectType}`, data)
export const getDailyReportMailPolicies = () => api.get('/mail-settings/daily-report-policies')
export const updateDailyReportMailPolicy = (userId, data) =>
  api.put(`/mail-settings/daily-report-policies/${userId}`, data)

export const previewProjectMail = (data) => api.post('/project-mails/preview', data)
// SMTP 连接超时高于全局普通接口超时，避免邮件实际已发送但页面误报超时。
export const sendProjectMail = (data) => api.post('/project-mails/', data, { timeout: 30000 })
export const retryProjectMail = (id) => api.post(`/project-mails/${id}/retry`, null, { timeout: 30000 })
export const getProjectMailHistory = (params) => api.get('/project-mails/', { params })
