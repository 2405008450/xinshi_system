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

/**
 * 获取所有译员列表（含排班属性）
 * @param {string} [direction] 翻译方向: zh_en / en_zh / both
 * 返回 [{ id, name, type, quality, cloudRev, dailyRate, direction, order, remarks }]
 */
export const getTranslatorList = (direction) => {
    const params = direction ? { direction } : {}
    return api.get('/schedules/translators/list', { params })
}
