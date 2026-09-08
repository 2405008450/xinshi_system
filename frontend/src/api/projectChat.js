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

const messageBasePath = (projectId, projectType = 'translation') => (
  projectType === 'annotation'
    ? `/project-chat/annotation/${projectId}`
    : `/project-chat/${projectId}`
)

export const getProjectChatMessages = (projectId, params = {}, projectType = 'translation') => {
  return api.get(`${messageBasePath(projectId, projectType)}/messages`, { params }).then(res => convertKeys(res, toCamelCase))
}

export const createProjectChatMessage = (projectId, data, projectType = 'translation') => {
  return api.post(`${messageBasePath(projectId, projectType)}/messages`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const uploadProjectChatAttachment = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/project-chat/attachments', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => convertKeys(res, toCamelCase))
}

export const getProjectChatAttachmentBlob = (attachmentId) =>
  api.get(`/project-chat/attachments/${attachmentId}`, { responseType: 'blob' })
