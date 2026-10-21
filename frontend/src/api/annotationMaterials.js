import api from './index'

const base = '/projects/annotation'
export const listMaterials = (projectId, config = {}) => api.get(`${base}/${projectId}/materials`, config)
export const listMaterialFolders = (projectId, config = {}) => api.get(`${base}/${projectId}/material-folders`, config)
export const listMaterialVersions = (projectId, fileId, config = {}) => api.get(`${base}/${projectId}/materials/${fileId}/versions`, config)
export const trashMaterial = (projectId, fileId) => api.post(`${base}/${projectId}/materials/${fileId}/trash`)
export const listMaterialTrash = (projectId, params, config = {}) => api.get(`${base}/${projectId}/material-trash`, { ...config, params })
export const restoreMaterial = (projectId, row) => api.post(`${base}/${projectId}/materials/${row.file_id}/restore`, { trash_token: row.trash_token })
export const purgeMaterial = (projectId, row) => api.delete(`${base}/${projectId}/material-trash/${row.file_id}`, { data: { trash_token: row.trash_token } })
export const cancelMaterialUpload = id => api.delete(`${base}/material-uploads/${id}`, { timeout: 300000 })

export function uploadMaterial(file, onUploadProgress, signal) {
  const data = new FormData()
  data.append('file', file)
  return api.post(`${base}/material-uploads`, data, {
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000, onUploadProgress, signal,
  })
}

export async function downloadMaterial(projectId, row) {
  const blob = await api.get(`${base}/${projectId}/materials/${row.file_id}/versions/${row.id}/download`, {
    responseType: 'blob', timeout: 300000,
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = row.original_name
  link.click()
  // 留出浏览器启动下载的时间。
  window.setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export const readMaterialVersion = (projectId, row) => api.get(`${base}/${projectId}/materials/${row.file_id}/versions/${row.id}/download`, {
  responseType: 'blob', timeout: 300000,
})
export const commitOnlineVersion = (projectId, fileId, data) => api.post(`${base}/${projectId}/materials/${fileId}/online-versions`, data)
export const createOnlineFile = (projectId, data) => api.post(`${base}/${projectId}/materials/online-files`, data)

export const openOfficeSession = (projectId, data) => api.post(`${base}/${projectId}/office/sessions`, data)
export const officeSessionStatus = id => api.get(`${base}/office/sessions/${id}`)
export const heartbeatOfficeSession = id => api.post(`${base}/office/sessions/${id}/heartbeat`)
export const saveOfficeSession = (id, saveId, revision) => api.post(`${base}/office/sessions/${id}/save`, { save_id: saveId, revision }, { timeout: 25000 })
export const discardOfficeSession = id => api.post(`${base}/office/sessions/${id}/discard`)
export function releaseOfficeSessionOnExit(id) {
  const token = localStorage.getItem('token')
  if (!token) return
  void fetch(`/api${base}/office/sessions/${id}/discard`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, keepalive: true,
  }).catch(() => {})
}
