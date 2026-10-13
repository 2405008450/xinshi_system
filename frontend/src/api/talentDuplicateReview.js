import api from './index'

// 字段决策的键是后端字段路径或明细散列，保留原样，避免通用键转换破坏决策。
const root = '/talents/duplicate-review'
export const getDuplicateGroups = (params, signal) => api.get(`${root}/groups`, { params, signal, timeout: 60000 })
export const getDuplicateGroup = (key, signal) => api.get(`${root}/groups/${encodeURIComponent(key)}`, { signal, timeout: 60000 })
export const previewDuplicateReview = payload => api.post(`${root}/preview`, payload, { timeout: 60000 })
export const commitDuplicateReview = payload => api.post(`${root}/commit`, payload, { timeout: 60000 })
export const getDuplicateHistory = params => api.get(`${root}/history`, { params })
export const undoDuplicateReview = id => api.post(`${root}/operations/${id}/undo`, {}, { timeout: 60000 })
export const getDuplicateOperation = id => api.get(`${root}/operations/${id}`, { timeout: 60000 })
export const getNameMergeGroups = (params, signal) => api.get(`${root}/name-merge/groups`, { params, signal, timeout: 120000 })
export const previewNameMerge = (payload, signal) => api.post(`${root}/name-merge/preview`, payload, { signal, timeout: 120000 })
export const commitNameMerge = payload => api.post(`${root}/name-merge/commit`, payload, { timeout: 120000 })
export const getDuplicateOriginalData = (id, params = {}, signal) => api.get(`${root}/operations/${id}/original-data`, { params, signal, timeout: 60000 })
export const exportDuplicateOriginalData = id => api.get(`${root}/operations/${id}/original-data/export`, { responseType: 'blob', timeout: 60000 })
export const getDuplicateOriginalAttachment = (id, attachmentId) => api.get(`${root}/operations/${id}/original-data/attachments/${attachmentId}`, { responseType: 'blob', timeout: 120000 })
