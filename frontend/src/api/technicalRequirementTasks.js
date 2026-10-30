import api from './index'
export const getRequirementTask = roomId => api.get(`/technical-development/requirements/${roomId}`)
export const saveRequirementTask = (roomId, payload) => api.post(`/technical-development/requirements/${roomId}`, payload, { timeout: payload.allocations ? 60000 : 10000 })
