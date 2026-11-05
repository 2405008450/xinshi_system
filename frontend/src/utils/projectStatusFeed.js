// 公共状态检查调度器；同一页面的多个表格共享请求和定时器。
export const statusKey=item=>`${item.projectType}:${item.id}`
export function createProjectStatusFeed({fetchStatuses,setWatch,visible=()=>true,setInterval:interval=globalThis.setInterval,clearInterval:clear=globalThis.clearInterval,setTimeout:later=globalThis.setTimeout,clearTimeout:cancel=globalThis.clearTimeout}){
  const listeners=new Set();let timer,queued,controller,sequence=0
  const entries=()=>[...listeners].filter(entry=>entry.active())
  const items=()=>[...new Map(entries().flatMap(entry=>entry.items()).map(item=>[statusKey(item),{projectType:item.projectType,id:item.id}])).values()]
  function deliver(changes){
    if(!visible())return
    const latest=new Map(changes.map(item=>[statusKey(item),item]))
    for(const entry of entries()){
      const changed=entry.items().flatMap(item=>{const value=latest.get(statusKey(item));return value&&String(item.status||'')!==String(value.status||'')?[value]:[]})
      if(changed.length)entry.changed(changed)
    }
  }
  async function check(){
    if(!visible()||!listeners.size)return
    const wanted=items();if(!wanted.length)return
    controller?.abort();controller=new AbortController();const signal=controller.signal,current=++sequence
    try{
      const values=[]
      for(let start=0;start<wanted.length;start+=500){const data=await fetchStatuses(wanted.slice(start,start+500),signal);values.push(...(data.items||[]))}
      if(current===sequence&&!signal.aborted)deliver(values)
    }catch{/* 离线或权限变化不弹通知，重连/下次检查继续核对。 */}
  }
  function update(){
    sequence++;controller?.abort();cancel(queued);queued=null
    const wanted=visible()?items():[];setWatch(wanted.slice(0,2000))
    if(timer){clear(timer);timer=null}
    if(wanted.length){timer=interval(check,60000);queued=later(check,120)}
  }
  return {register(entry){listeners.add(entry);update();return()=>{listeners.delete(entry);update()}},update,check,push(payload){sequence++;controller?.abort();deliver(payload.items||[])},stop(){listeners.clear();update()}}
}
