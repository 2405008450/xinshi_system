import api from './index'

const base = '/projects/annotation'
export const listMaterials = projectId => api.get(`${base}/${projectId}/materials`)
export const listMaterialVersions = (projectId, fileId) => api.get(`${base}/${projectId}/materials/${fileId}/versions`)
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
