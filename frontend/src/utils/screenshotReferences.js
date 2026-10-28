export const screenshotPattern=/!\[截图\]\(screenshot:\/\/([0-9a-f-]{36})(?:#[0-9a-f]{64})?\)/gi
export const screenshotIds=value=>{current();return [...new Set(Array.from(String(value||'').matchAll(/screenshot:\/\/([0-9a-f-]{36})(?:#([0-9a-f]{64}))?/gi),match=>{const id=match[1].toLowerCase();if(match[2])signedRefs.set(id,match[0]);return id}))]}
const trailingRefs=/\n?(?:!\[截图\]\(screenshot:\/\/[0-9a-f-]{36}(?:#[0-9a-f]{64})?\)\n?)+$/i
export const screenshotText=value=>{const text=String(value??'');return screenshotIds(text).length?text.replace(trailingRefs,'').replace(screenshotPattern,''):text}
export const screenshotValue=(text,ids)=>{current();return ids.length?[String(text||''),...ids.map(id=>`![截图](${String(id).startsWith('screenshot://')?id:signedRefs.get(id)||`screenshot://${id}`})`)].filter(Boolean).join('\n'):String(text??'')}
export const screenshotPreview=value=>String(value??'').replace(/!\[截图\]\(screenshot:\/\/[^\s)]*(?:\)|$)/gi,'[截图]').replace(/screenshot:\/\/[0-9a-f-]*/gi,'[截图]')
let identity='',entries=new Map(),pending=new Map(),signedRefs=new Map()
function current(){const storage=globalThis.localStorage,key=storage?`${storage.getItem('user_id')}:${storage.getItem('token')}`:'unit';if(key!==identity){identity=key;entries=new Map();signedRefs=new Map()}}
export function rememberScreenshotGrant(response){
  if(response.config?.headers?.Authorization && response.config.headers.Authorization!==`Bearer ${localStorage.getItem('token')}`)return
  current();const grant=response.headers?.['x-screenshot-grant'];if(!grant)return
  const expires=Number(response.headers['x-screenshot-grant-expires']||0)*1000
  const ids=response.config?.screenshotIds||screenshotIds(typeof response.data==='string'?response.data:JSON.stringify(response.data))
  const source=response.config?.method==='get'?{url:response.config.url,params:response.config.params,responseType:response.config.responseType,screenshotIds:response.config.screenshotIds}:null
  ids.forEach(id=>entries.set(id,{grant,expires,source:response.config?.responseType==='blob'?(entries.get(id)?.source||source):(source||entries.get(id)?.source)}))
}
export async function screenshotGrantHeaders(ids,refresh){
  current();const sources=new Map()
  for(const id of ids){const entry=entries.get(id);if(entry&&entry.expires<Date.now()+30000&&entry.source)sources.set(JSON.stringify(entry.source),entry.source)}
  for(const [key,source] of sources){if(!pending.has(key))pending.set(key,Promise.resolve().then(()=>refresh(source)).finally(()=>pending.delete(key)));await pending.get(key)}
  return [...new Set(ids.map(id=>entries.get(id)?.grant).filter(Boolean))].join(',')
}