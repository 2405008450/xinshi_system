// 当前页面内存，不写入草稿，不跨账号共享。
export const businessNumberLeases = new Map()
export function newNumberWindowId(){
  const bytes=globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128
  const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
const numberFields = new WeakMap()
export function registerBusinessNumberField(model, field) {
  if(!model||!field)return
  if(!numberFields.has(model))numberFields.set(model,new Set())
  numberFields.get(model).add(field)
}
export function withoutBusinessNumbers(model, snapshot, comparison=false) {
  const copy={...snapshot}
  const fields=new Set(numberFields.get(model)||[])
  if(comparison)for(const field of ['orderNo','order_no','clientCode','client_code','subClientCode','sub_client_code','subOrderNo','sub_order_no','consultation_code','resourceCode','resource_code','translator_code','demand_no','task_no','greeting_no','requestNo'])fields.add(field)
  for(const field of fields)delete copy[field]
  return copy
}
export function numberLeaseHeaders(config) {
  if (!['post','put','patch'].includes(String(config.method).toLowerCase()) || String(config.url).includes('/business-numbers/')) return
  const data=JSON.stringify(config.data||{})
  const entries=[...businessNumberLeases.values()].filter(item=>item.owner===localStorage.getItem('user_id'))
  const matched=entries.filter(item=>data.includes(JSON.stringify(item.number)))
  const routes={translation:'/projects/translation',translation_suborder:'/sub-orders',interpretation:'/projects/interpretation',annotation:'/projects/annotation',annotation_suborder:'/projects/annotation',recruitment:'/projects/recruitment',client:'/clients',subclient:'/sub-clients',consultation:'/consultations',resource_request:'/resource-requests',hr_requirement:'/hr-recruitment/requirements',talent:'/talents',technical_task:'/technical-development',technical_subtask:'/technical-development',feedback:'/development-feedback',greeting:'/resource-development'}
  for(const [kind,route] of Object.entries(routes)) {
    const items=entries.filter(item=>item.kind===kind)
    if(String(config.url).startsWith(route)&&items.length===1&&!matched.includes(items[0]))matched.push(items[0])
  }
  if(String(config.url).startsWith('/recruitment-talents'))matched.push(...entries.filter(item=>item.kind==='talent'&&!matched.includes(item)))
  if(String(config.url).startsWith('/translators')||String(config.url).includes('/candidates'))matched.push(...entries.filter(item=>item.kind==='talent'&&!matched.includes(item)))
  if(String(config.url).includes('/sub_clients'))matched.push(...entries.filter(item=>item.kind==='subclient'&&!matched.includes(item)))
  const explicit=JSON.parse(config.headers['X-Business-Number-Leases']||'[]')
  if(matched.length||explicit.length)config.headers['X-Business-Number-Leases']=JSON.stringify([...new Set([...explicit,...matched.map(item=>item.token)])])
}
