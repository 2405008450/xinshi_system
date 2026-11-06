import {onMounted,onActivated,onDeactivated,onBeforeUnmount,watch,toValue} from 'vue'
import api from '@/api/index'
import {subscribe,setProjectStatusWatch} from '@/utils/realtimeSocket'
import {createProjectStatusFeed,statusKey} from '@/utils/projectStatusFeed'

const feed=createProjectStatusFeed({fetchStatuses:(items,signal)=>api.post('/project-status-sync/snapshot',{items},{signal}),setWatch:setProjectStatusWatch,visible:()=>document.visibilityState!=='hidden'})
let users=0,cleanup=[]
function bind(){if(users++)return;const resume=()=>feed.update();document.addEventListener('visibilitychange',resume);cleanup=[subscribe('project_status_changed',payload=>feed.push(payload)),subscribe('connected',resume),subscribe('foreground',resume),()=>document.removeEventListener('visibilitychange',resume)]}
function unbind(){if(--users)return;cleanup.forEach(fn=>fn());cleanup=[]}

export function useProjectStatusSync(projectType,source,{field='projectStatus',onChanged,enabled=()=>true,children=true,typeForRow,idForRow}={}){
  let active=true,unregister,highlightTimer,refreshTimer
  const nodes=()=>{
    const result=[]
    function visit(row,depth=0){const id=idForRow?idForRow(row):row?.id;if(!row||!id||row._clientGroup)return;const kind=typeForRow?typeForRow(row):toValue(projectType);const child=kind==='translation'&&(depth>0||row.subOrderNo||row.parentProjectId||(row.rootId&&row.rootId!==row.id));result.push({row,projectType:child?'translation_suborder':kind,id:String(id),field:child&&'status' in row?'status':field});if(children)for(const next of row.children||row.subOrders||[])visit(next,depth+1)}
    const value=toValue(source);for(const row of Array.isArray(value)?value:[value])visit(row)
    return result
  }
  const entry={active:()=>active&&toValue(enabled),items:()=>nodes().map(item=>({projectType:item.projectType,id:item.id,status:item.row[item.field]||''})),changed:changes=>{
    const latest=new Map(changes.map(item=>[statusKey(item),item]));for(const item of nodes()){const value=latest.get(statusKey(item));if(value){item.row[item.field]=value.status;item.row._statusSynced=true}}
    clearTimeout(highlightTimer);highlightTimer=setTimeout(()=>{for(const item of nodes())delete item.row._statusSynced},1800)
    if(onChanged){clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>{if(active&&document.visibilityState!=='hidden')onChanged(changes)},250)}
  }}
  onMounted(()=>{bind();unregister=feed.register(entry)})
  watch(()=>nodes().map(item=>statusKey(item)).join('|'),()=>{if(unregister)feed.update()})
  watch(()=>toValue(enabled),()=>{if(unregister)feed.update()})
  onActivated(()=>{active=true;if(unregister)feed.update()})
  onDeactivated(()=>{active=false;if(unregister)feed.update()})
  onBeforeUnmount(()=>{unregister?.();unregister=null;clearTimeout(highlightTimer);clearTimeout(refreshTimer);unbind()})
  return {refresh:()=>feed.check()}
}
