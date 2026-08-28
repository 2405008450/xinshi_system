import api from './index'

export const getMyWorkItems = () => api.get('/work-items/my')

export const getNonProjectTasks = (params) => api.get('/non-project-tasks', { params })
export const createNonProjectTask = (data) => api.post('/non-project-tasks', data)
export const updateNonProjectTask = (id, data) => api.patch(`/non-project-tasks/${id}`, data)
export const changeNonProjectTaskStatus = (id, action, note = '') =>
  api.post(`/non-project-tasks/${id}/actions/${action}`, { note })

export const createTaskRecurrence = (data) => api.post('/non-project-tasks/recurrences', data)
export const getTaskRecurrences = () => api.get('/non-project-tasks/recurrences')
export const setTaskRecurrenceActive = (id, active) =>
  api.patch(`/non-project-tasks/recurrences/${id}/active`, null, { params: { active } })

export const createWorkEntry = (data) => api.post('/work-entries', data)
export const getWorkEntries = (params) => api.get('/work-entries', { params })
export const updateWorkEntry = (id, data) => api.patch(`/work-entries/${id}`, data)

export const previewDailyReport = (reportDate, refresh = false) =>
  api.get('/daily-reports/preview', { params: { report_date: reportDate, refresh } })
export const saveDailyReport = (reportDate, data) =>
  api.put(`/daily-reports/${reportDate}`, data)
export const finalizeDailyReport = (reportDate, data) =>
  api.post(`/daily-reports/${reportDate}/finalize`, data)
export const withdrawDailyReport = (reportDate) =>
  api.post(`/daily-reports/${reportDate}/withdraw`)
export const exportDailyReport = (reportDate) =>
  api.get(`/daily-reports/${reportDate}/export`, { responseType: 'blob' })
export const getDailyReportMailAccount = () => api.get('/daily-reports/mail-account')
export const saveDailyReportMailAccount = (authorizationCode) =>
  api.put('/daily-reports/mail-account', { authorization_code: authorizationCode })
export const verifyDailyReportMailAccount = () => api.post('/daily-reports/mail-account/verify')
export const deleteDailyReportMailAccount = () => api.delete('/daily-reports/mail-account')
export const previewDailyReportMail = (reportDate) =>
  api.get(`/daily-reports/${reportDate}/mail-preview`)
export const sendDailyReportMail = (reportDate, data) =>
  api.post(`/daily-reports/${reportDate}/send`, data, { timeout: 30000 })
export const getDailyReportDeliveries = (reportDate) =>
  api.get(`/daily-reports/${reportDate}/deliveries`)
