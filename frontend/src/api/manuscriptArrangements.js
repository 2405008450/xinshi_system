import api from './index'

export const getManuscriptContext = (params = {}, config = {}) =>
  api.get('/manuscript-arrangements/context', { params, ...config })

export const getManuscriptMailStatus = () =>
  api.get('/manuscript-arrangements/mail-status')

export const quickCreateManuscriptTranslator = (data) =>
  api.post('/manuscript-arrangements/translators/quick-create', data)

export const getManuscriptArrangements = (params = {}) =>
  api.get('/manuscript-arrangements', { params })

export const getManuscriptDispatches = (params = {}, config = {}) =>
  api.get('/manuscript-arrangements/batches', { params, ...config })

export const createManuscriptDispatch = (data) =>
  api.post('/manuscript-arrangements/batches', data)

export const updateManuscriptDispatch = (id, data) =>
  api.put(`/manuscript-arrangements/batches/${id}`, data)

export const confirmManuscriptDispatch = (id) =>
  api.post(`/manuscript-arrangements/batches/${id}/confirm`)

export const cancelManuscriptDispatch = (id) =>
  api.post(`/manuscript-arrangements/batches/${id}/cancel`)

const buildAttachmentForm = (attachment, mailContent = {}) => {
  const formData = new FormData()
  if (attachment) formData.append('attachment', attachment)
  if (mailContent.subject !== undefined && mailContent.subject !== null) {
    formData.append('subject', mailContent.subject)
  }
  if (mailContent.body) formData.append('body', mailContent.body)
  if (mailContent.bodyHtml) formData.append('body_html', mailContent.bodyHtml)
  if (mailContent.inlineImageHtml) formData.append('inline_image_html', mailContent.inlineImageHtml)
  formData.append('inline_image_ids_json', JSON.stringify(mailContent.inlineImageIds || []))
  return formData
}

const attachmentRequestConfig = {
  headers: { 'Content-Type': 'multipart/form-data' },
  // 批量发送会逐封投递，上传大附件时需要覆盖完整发送耗时。
  timeout: 300000
}

export const sendManuscriptDispatch = (id, attachment = null, mailContent = {}) =>
  api.post(
    `/manuscript-arrangements/batches/${id}/send`,
    buildAttachmentForm(attachment, mailContent),
    attachmentRequestConfig
  )

export const sendManuscriptAssignment = (dispatchId, arrangementId, attachment = null, mailContent = {}) =>
  api.post(
    `/manuscript-arrangements/batches/${dispatchId}/arrangements/${arrangementId}/send`,
    buildAttachmentForm(attachment, mailContent),
    attachmentRequestConfig
  )

export const getManuscriptMailPreview = (dispatchId, arrangementId) =>
  api.get(
    `/manuscript-arrangements/batches/${dispatchId}/arrangements/${arrangementId}/mail-preview`
  )

export const updateManuscriptMailPaths = (dispatchId, data) =>
  api.patch(`/manuscript-arrangements/batches/${dispatchId}/mail-paths`, data)

export const updateManuscriptSettlement = (dispatchId, arrangementId, data) =>
  api.patch(
    `/manuscript-arrangements/batches/${dispatchId}/arrangements/${arrangementId}/settlement`,
    data
  )

export const createManuscriptArrangement = (data) =>
  api.post('/manuscript-arrangements', data)

export const updateManuscriptArrangement = (id, data) =>
  api.put(`/manuscript-arrangements/${id}`, data)

export const sendManuscriptArrangement = (id, attachment = null, mailContent = {}) =>
  api.post(
    `/manuscript-arrangements/${id}/send`,
    buildAttachmentForm(attachment, mailContent),
    attachmentRequestConfig
  )

export const deleteManuscriptArrangement = (id) =>
  api.delete(`/manuscript-arrangements/${id}`)
