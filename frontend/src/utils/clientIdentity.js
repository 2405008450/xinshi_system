// 仅根据已选客户 ID 补齐空白字段，不按名称猜测客户，也不覆盖手工输入。
const pending = new Map()
const text = value => String(value ?? '').trim()
export function clientIdentityKeys(model = {}) {
  return {
    id: Object.hasOwn(model,'client_id') ? 'client_id' : 'clientId',
    sub: Object.hasOwn(model,'sub_client_id') ? 'sub_client_id' : 'subClientId',
    full: Object.hasOwn(model,'clientFullName') ? 'clientFullName' : Object.hasOwn(model,'client_name') ? 'client_name' : 'clientName',
    short: Object.hasOwn(model,'client_short_name') ? 'client_short_name' : 'clientShortName',
    code: Object.hasOwn(model,'client_code') ? 'client_code' : 'clientCode',
  }
}

export async function fillMissingClientIdentity(model, {loadClient, owner = '', isCurrent = () => true}) {
  if(!model || typeof model !== 'object')return false
  const keys=clientIdentityKeys(model),id=text(model[keys.id])
  if(!id || !Object.hasOwn(model,keys.full))return false
  if(text(model[keys.full]) && (!Object.hasOwn(model,keys.short) || text(model[keys.short])))return false
  const subId=text(model[keys.sub]),recordId=model.id
  const requestKey=JSON.stringify([owner,id])
  if(!pending.has(requestKey)){
    const request=Promise.resolve().then(()=>loadClient(id))
    pending.set(requestKey,request)
    void request.finally(()=>{if(pending.get(requestKey)===request)pending.delete(requestKey)}).catch(()=>{})
  }
  const client=await pending.get(requestKey)
  if(!isCurrent() || model.id!==recordId || text(model[keys.id])!==id || text(model[keys.sub])!==subId)return false
  // 笔译有独立的子客户字段；其他组合客户选择框展示所选子客户身份。
  const separateSubClient=Object.hasOwn(model,'subClientName') || Object.hasOwn(model,'sub_client_name')
  const selected=subId&&!separateSubClient
    ? (client?.sub_clients || client?.subClients || []).find(row=>text(row.id)===subId)
    : client
  if(!selected)return false
  const values={
    [keys.full]:selected.client_name || selected.clientName || selected.clientFullName,
    [keys.short]:selected.client_short_name || selected.clientShortName,
    [keys.code]:subId&&!separateSubClient ? selected.sub_client_code || selected.subClientCode : selected.client_code || selected.clientCode,
  }
  let changed=false
  for(const [key,value] of Object.entries(values))if(Object.hasOwn(model,key)&&!text(model[key])&&text(value)){model[key]=value;changed=true}
  return changed
}
