import api from './index'

export const getWordCountMatrix = (entityType, entityId, params = {}) =>
  api.get(`/word-count-matrices/${entityType}/${entityId}`, { params })

export const patchWordCountMatrix = (entityType, entityId, data, params = {}) =>
  api.patch(`/word-count-matrices/${entityType}/${entityId}`, data, { params })
