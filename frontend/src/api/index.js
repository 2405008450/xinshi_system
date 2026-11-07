import axios from 'axios'
import { normalizeApiError } from '@/utils/errorMessages'
import { clearAuthSession } from '@/utils/authSession'
import { chatConversationScope } from '@/utils/chatAccess'
import { screenshotIds, screenshotGrantHeaders, rememberScreenshotGrant } from '@/utils/screenshotReferences'
import {draftSubmitSnapshot,completeDraftSubmit} from '@/utils/autoDrafts'
import {rememberSavedRead,savedReadPromise} from '@/utils/savedDataRegistry'
import {numberLeaseHeaders} from '@/utils/businessNumberLeases'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  async config => {
    numberLeaseHeaders(config)
    if(['post','put','patch','delete'].includes(String(config.method).toLowerCase()))config.autoDraftSubmission=draftSubmitSnapshot(config.url)
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const ids = config.screenshotIds || screenshotIds(JSON.stringify(config.data || '') + JSON.stringify(config.params || {}))
    if(ids.length && !config.refreshingScreenshotGrant) config.headers['X-Screenshot-Grants'] = await screenshotGrantHeaders(ids, source=>api.get(source.url,{params:source.params,responseType:source.responseType,screenshotIds:source.screenshotIds,refreshingScreenshotGrant:true}))
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    completeDraftSubmit(response.config?.autoDraftSubmission)
    rememberScreenshotGrant(response)
    const scope = chatConversationScope(response.config?.url)
    if (scope) window.dispatchEvent(new CustomEvent('chat-conversation-access-granted', { detail: scope }))
    // 实时同步是附加能力，隐藏界面的收集异常不能让成功的业务请求变成失败。
    try{return rememberSavedRead(response)}catch{return response.data}
  },
  error => {
    const scope = chatConversationScope(error.config?.url)
    if (scope && [403, 404].includes(error.response?.status)) window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: scope }))
    if (error.response?.status === 401) {
      clearAuthSession()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(normalizeApiError(error))
  }
)

const readGet=api.get.bind(api)
api.get=(...args)=>savedReadPromise(readGet(...args))
export default api
