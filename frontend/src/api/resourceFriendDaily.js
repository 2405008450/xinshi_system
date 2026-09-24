import api from './index'
const base = '/resource-development/friend-daily'
export const friendDailyApi = {
  options: () => api.get(`${base}/options`),
  list: (params, signal) => api.get(base, { params, signal }),
  read: (date, signal) => api.get(`${base}/${date}`, { signal }),
  save: (date, payload) => api.put(`${base}/${date}`, payload),
  addAccount: payload => api.post(`${base}/accounts`, payload),
}
