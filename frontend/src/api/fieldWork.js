import api from './index'

const base = '/attendance/field-work'

export const getFieldWorkOptions = signal => api.get(`${base}/options`, { signal })

export const getFieldWork = (customer, params, signal) => api.get(
  customer ? `${base}/customers` : base, { params, signal },
)

export const getFieldWorkPhoto = (id, customer, signal) => api.get(
  `${base}${customer ? '/customers' : ''}/${id}/photo`, { responseType: 'blob', signal },
)

export function saveFieldWork(payload, photo) {
  const form = new FormData()
  form.set('payload', JSON.stringify(payload))
  if (photo) form.set('photo', photo)
  return api.putForm(base, form, { timeout: 120000 })
}
