export const childProgressReadStorageKey=(userId,projectId)=>`annotation-child-progress-read:${userId}:${projectId}`
export function parseChildProgressRead(value){
  try{const parsed=JSON.parse(value);return Array.isArray(parsed)?[...new Set(parsed.filter(item=>typeof item==='string'))]:[]}catch{return []}
}
export function childProgressReadCount(keys,readKeys){const read=new Set(readKeys);return [...new Set(keys)].filter(key=>read.has(key)).length}
export function markChildProgressRead(keys,readKeys,key){return [...new Set([...readKeys,key])].filter(value=>keys.includes(value))}
