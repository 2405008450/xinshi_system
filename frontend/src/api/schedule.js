/**
 * 排班管理 API
 * 用于替代 localStorage，实现全员共享的排班数据读写
 */
import api from './index'

/**
 * 获取某日排班数据
 * @param {string} date YYYY-MM-DD
 */
export const getSchedule = (date) => api.get(`/schedules/${date}`)

/**
 * 创建或更新某日排班数据（Upsert）
 * @param {string} date YYYY-MM-DD
 * @param {object} data 排班数据各板块
 */
export const saveSchedule = (date, data) => api.put(`/schedules/${date}`, data)

/**
 * 从某一天复制排班到另一天
 * @param {string} sourceDate YYYY-MM-DD
 * @param {string} targetDate YYYY-MM-DD
 */
export const copySchedule = (sourceDate, targetDate) =>
    api.post('/schedules/copy', null, { params: { source_date: sourceDate, target_date: targetDate } })

/**
 * 删除某日排班数据
 * @param {string} date YYYY-MM-DD
 */
export const deleteSchedule = (date) => api.delete(`/schedules/${date}`)

/**
 * 获取所有活跃内部员工列表（用于排班页面初始化人员模板）
 * 返回 [{ id, name, dept, fixedTasks }]
 */
export const getStaffList = () => api.get('/schedules/staff/list')

export const getEmployeeShifts = (params, signal) =>
    api.get('/schedules/employee-shifts', { params, signal })

export const getEmployeeShiftTemplate = (userId, referenceDate) =>
    api.get(`/schedules/employee-shifts/templates/${userId}`, {
        params: referenceDate ? { reference_date: referenceDate } : undefined
    })

export const saveEmployeeShiftTemplate = (userId, data) =>
    api.put(`/schedules/employee-shifts/templates/${userId}`, data)

export const saveEmployeeShiftLock = (userId, data) =>
    api.put(`/schedules/employee-shifts/locks/${userId}`, data)

export const saveEmployeeShiftOverrides = (items) =>
    api.put('/schedules/employee-shifts/overrides/batch', { items })

export const getMyEmployeeShift = (date, includeDepartment = true, signal) =>
    api.get('/schedules/employee-shifts/me', {
        params: { schedule_date: date, include_department: includeDepartment },
        signal
    })

/**
 * 获取所有译员列表（含排班属性及可用性信息）
 * @param {object} [options] { direction, active_only }
 */
export const getTranslatorList = (options) => {
    const params = {}
    if (typeof options === 'string') {
        params.direction = options
    } else if (options) {
        if (options.direction) params.direction = options.direction
        if (options.active_only) params.active_only = true
    }
    return api.get('/schedules/translators/list', { params })
}

export const getTranslatorAvailabilityGrid = (params, signal) =>
    api.get('/schedules/translators/availability-grid', { params, signal })

export const updateTranslatorAvailability = (translatorId, date, data) =>
    api.put(`/schedules/translators/${translatorId}/availability/${date}`, data)

export const importTranslatorScheduleDemo = (file, overwrite = true) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('overwrite', String(overwrite))
    return api.post('/schedules/translators/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export const previewTranslatorScheduleDemo = (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/schedules/translators/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}


export const downloadTranslatorScheduleTemplate = () =>
    api.get('/schedules/translators/import-template', { responseType: 'blob' })
