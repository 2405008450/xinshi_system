import api from './index'

// 字段决策的键是后端字段路径或明细散列，保留原样，避免通用键转换破坏决策。
const root = '/talents/duplicate-review'
export const getDuplicateGroups = (params, signal) => api.get(`${root}/groups`, { params, signal, timeout: 60000 })
export const getDuplicateGroup = (key, signal) => api.get(`${root}/groups/${encodeURIComponent(key)}`, { signal, timeout: 60000 })
export const previewDuplicateReview = payload => api.post(`${root}/preview`, payload, { timeout: 60000 })
export const commitDuplicateReview = payload => api.post(`${root}/commit`, payload, { timeout: 60000 })
export const getDuplicateHistory = params => api.get(`${root}/history`, { params })
export const undoDuplicateReview = id => api.post(`${root}/operations/${id}/undo`, {}, { timeout: 60000 })
