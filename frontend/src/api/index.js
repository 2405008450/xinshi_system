import axios from 'axios'

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
    // FastAPI 的 422 detail 是校验错误数组，统一转换为可读文本，避免消息框显示空白。
    const responseDetail = error.response?.data?.detail
    const errorMessage = Array.isArray(responseDetail)
      ? responseDetail.map(item => {
          const field = Array.isArray(item?.loc) ? item.loc.filter(part => part !== 'body').join('.') : ''
          return `${field ? `${field}：` : ''}${item?.msg || '字段校验失败'}`
        }).join('；')
      : responseDetail || error.message || '请求失败'
    return Promise.reject({ ...error, detail: errorMessage, message: errorMessage })
  }
)

export default api
