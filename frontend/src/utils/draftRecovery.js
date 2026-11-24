export function chooseDraft(local,remote){
 if(!remote)return local||null
 if(local&&Number.isInteger(local._baseRevision)&&local._baseRevision>=remote.revision)return local
 const localTime=local?._savedAt||Date.parse(local?.savedAt||'')||0
 const remoteTime=remote.payload?._savedAt||Date.parse(remote.updated_at||'')||0
 if(remote.payload==null){return remote.revision>0&&localTime>0&&remoteTime>=localTime?null:local||null}
 return local&&(!localTime||localTime>remoteTime)?local:remote.payload
}
