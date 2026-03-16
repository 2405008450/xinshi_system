import api from './index'

function toCamelCase(str) {
  return str.replace(/([-_][a-z])/g, (group) => group.toUpperCase().replace('-', '').replace('_', ''))
}

function toSnakeCase(str) {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function convertKeys(obj, converter) {
  if (Array.isArray(obj)) {
    return obj.map(v => convertKeys(v, converter))
  }
  if (obj !== null && obj?.constructor === Object) {
    return Object.keys(obj).reduce((result, key) => {
      result[converter(key)] = convertKeys(obj[key], converter)
      return result
    }, {})
  }
  return obj
}

export const getProjectChatSettings = (projectId) => {
  return api.get(`/project-chat/${projectId}/settings`).then(res => convertKeys(res, toCamelCase))
}

export const updateProjectChatSettings = (projectId, data) => {
  return api.post(`/project-chat/${projectId}/settings`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const getProjectChatMessages = (projectId, params = {}) => {
  return api.get(`/project-chat/${projectId}/messages`, { params }).then(res => convertKeys(res, toCamelCase))
}

export const createProjectChatMessage = (projectId, data) => {
  return api.post(`/project-chat/${projectId}/messages`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}
