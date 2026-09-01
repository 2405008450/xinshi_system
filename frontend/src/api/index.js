import axios from 'axios'
import { normalizeApiError } from '@/utils/errorMessages'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user_roles')
      localStorage.removeItem('user_permissions')
      localStorage.removeItem('user_name')
      localStorage.removeItem('user_id')
      localStorage.removeItem('user_full_name')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(normalizeApiError(error))
  }
)

export default api
