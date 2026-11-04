import api from './index'
export const getProjectCustomerFinancePage = (module, params, config = {}) => api.get(`/project-customer-finance/${module}/page`, { ...config, params })
export const getProjectCustomerFinance = (module, id, config = {}) => api.get(`/project-customer-finance/${module}/project/${id}`, config)
export const saveProjectCustomerFinance = (module, id, data) => api.put(`/project-customer-finance/${module}/project/${id}`, data)
export const getProjectCustomerFinanceHistory = (module, id, page = 1) => api.get(`/project-customer-finance/${module}/project/${id}/history`, { params: { page } })
