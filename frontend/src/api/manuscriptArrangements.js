import api from './index'

export const getManuscriptContext = (params = {}) =>
  api.get('/manuscript-arrangements/context', { params })

export const getManuscriptMailStatus = () =>
  api.get('/manuscript-arrangements/mail-status')

export const getManuscriptArrangements = (params = {}) =>
  api.get('/manuscript-arrangements', { params })

export const getManuscriptDispatches = (params = {}) =>
  api.get('/manuscript-arrangements/batches', { params })

export const createManuscriptDispatch = (data) =>
  api.post('/manuscript-arrangements/batches', data)

export const updateManuscriptDispatch = (id, data) =>
  api.put(`/manuscript-arrangements/batches/${id}`, data)

export const confirmManuscriptDispatch = (id) =>
  api.post(`/manuscript-arrangements/batches/${id}/confirm`)

export const cancelManuscriptDispatch = (id) =>
  api.post(`/manuscript-arrangements/batches/${id}/cancel`)

export const sendManuscriptDispatch = (id) =>
  api.post(`/manuscript-arrangements/batches/${id}/send`)

export const sendManuscriptAssignment = (dispatchId, arrangementId) =>
  api.post(`/manuscript-arrangements/batches/${dispatchId}/arrangements/${arrangementId}/send`)

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

export const sendManuscriptArrangement = (id) =>
  api.post(`/manuscript-arrangements/${id}/send`)

export const deleteManuscriptArrangement = (id) =>
  api.delete(`/manuscript-arrangements/${id}`)
