import api from './index'
const base = '/resource-development/issues'
export const issueApi = {
  access: () => api.get(`${base}/access`),
  options: () => api.get(`${base}/options`),
  source: (id, discussionRoomId = null) => api.get(`${base}/source/${id}`, {params: discussionRoomId ? {discussion_room_id:discussionRoomId} : undefined}),
  locateSource: id => api.get(`${base}/${id}/source`),
  list: (params, signal) => api.get(base, { params, signal }),
  detail: (id, signal) => api.get(`${base}/${id}`, { signal }),
  create: data => api.post(base, data),
  update: (id, data) => api.put(`${base}/${id}`, data),
  updateProgress:(id,data)=>api.patch(`${base}/${id}/progress`,data),
  remove: row => api.delete(`${base}/${row.id}`, { params: { revision: row.revision } }),
  saveTask: (id, data, taskId) => taskId ? api.patch(`${base}/${id}/tasks/${taskId}`, data) : api.post(`${base}/${id}/tasks`, data),
  removeTask: (id, taskId, revision) => api.delete(`${base}/${id}/tasks/${taskId}`, { params: { revision } }),
}
