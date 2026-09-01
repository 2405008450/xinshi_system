import api from './index'

export const uploadMailInlineImage = (file) => {
  const data = new FormData()
  data.append('file', file)
  return api.post('/mail-inline-images', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}

export const getMailInlineImageContent = (id) =>
  api.get(`/mail-inline-images/${id}/content`, { responseType: 'blob' })

export const deleteMailInlineImage = (id) =>
  api.delete(`/mail-inline-images/${id}`)
