import axios from 'axios'
import { normalizeApiError } from '@/utils/errorMessages'
import { clearAuthSession } from '@/utils/authSession'
import { chatConversationScope } from '@/utils/chatAccess'
import { screenshotIds, screenshotGrantHeaders, rememberScreenshotGrant } from '@/utils/screenshotReferences'
import {draftSubmitSnapshot,completeDraftSubmit} from '@/utils/autoDrafts'
import {rememberSavedRead,savedReadPromise} from '@/utils/savedDataRegistry'
import {numberLeaseHeaders} from '@/utils/businessNumberLeases'
import { createLocalRequestQueue } from '@/utils/localRequestQueue'
import { captureUnsavedSave, completeUnsavedSave } from '@/utils/windowUnsavedState'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const sendRequest = axios.getAdapter(api.defaults.adapter)
const localRequestQueue = createLocalRequestQueue({
  locks: typeof navigator === 'undefined' ? null : navigator.locks,
  hostname: typeof window === 'undefined' ? '' : window.location.hostname,
  canceledError: config => new axios.CanceledError('请求已取消', config),
})
api.defaults.adapter = config => localRequestQueue(config, sendRequest)

// 请求拦截器
api.interceptors.request.use(
  async config => {
    config.windowUnsavedSubmission=captureUnsavedSave(config)
    numberLeaseHeaders(config)
    if(!config.skipDraftSubmit&&['post','put','patch','delete'].includes(String(config.method).toLowerCase()))config.autoDraftSubmission=draftSubmitSnapshot(config.url)
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
    completeUnsavedSave(response.config?.windowUnsavedSubmission,response.data)
    completeDraftSubmit(response.config?.autoDraftSubmission)
    rememberScreenshotGrant(response)
    const scope = chatConversationScope(response.config?.url)
    if (scope) window.dispatchEvent(new CustomEvent('chat-conversation-access-granted', { detail: scope }))
    // 实时同步是附加能力，隐藏界面的收集异常不能让成功的业务请求变成失败。
    try{return rememberSavedRead(response)}catch{return response.data}
  },
  async error => {
    const detail=error.response?.data?.detail
    if(error.response?.status===409&&detail?.code==='project_multiple_active_statements'){
      const {ElMessageBox}=await import('element-plus/es/components/message-box/index.mjs')
      const affected=(detail.projects||[]).map(project=>`${project.order_no}：${(project.statements||[]).join('、')}`).join('\n')
      await ElMessageBox.alert(`${detail.message}\n\n${affected}`,'项目重复归属有效对账单',{type:'warning',confirmButtonText:'知道了'}).catch(()=>{})
      error.response.data.detail=detail.message
    }
    if(error.response?.status===409&&detail?.code==='finance_note_sync_confirmation_required'&&error.config){
      const [{ElMessageBox},{h}]=await Promise.all([import('element-plus/es/components/message-box/index.mjs'),import('vue')])
      const rows=Array.isArray(detail.overwrites)?detail.overwrites:[]
      const message=h('div',{style:{maxHeight:'min(440px,60vh)',overflowY:'auto',whiteSpace:'pre-wrap'}},[
        h('p','以下子订单已有说明。确认后将覆盖这些内容；取消则不保存本次修改。'),
        ...rows.map(row=>h('div',{style:{borderTop:'1px solid #e2e8f0',padding:'8px 0'}},[h('strong',`${row.order_no} · ${row.field}`),h('div',`原内容：${row.before}`),h('div',`同步后：${row.after||'（清空）'}`)])),
      ])
      try{await ElMessageBox.confirm(message,'确认覆盖子订单说明',{type:'warning',confirmButtonText:'确认覆盖并同步',cancelButtonText:'取消',closeOnClickModal:false})}catch{return Promise.reject(new axios.CanceledError('已取消覆盖子订单说明',error.config))}
      let plans=[];try{plans=JSON.parse(error.config.headers?.['X-Finance-Note-Sync-Plans']||'[]')}catch{}
      error.config.headers['X-Finance-Note-Sync-Plans']=JSON.stringify([...new Set([...plans,detail.plan])])
      return api.request(error.config)
    }
    const scope = chatConversationScope(error.config?.url)
    if (scope && [403, 404].includes(error.response?.status)) window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: scope }))
    if (error.response?.status === 401) {
      const token = localStorage.getItem('token')
      if (token && error.config?.headers?.Authorization === `Bearer ${token}`) {
        clearAuthSession()
        if (window.location.pathname !== '/login') window.location.replace('/login')
      }
    }
    return Promise.reject(normalizeApiError(error))
  }
)

const readGet=api.get.bind(api)
api.get=(...args)=>savedReadPromise(readGet(...args))
export default api
