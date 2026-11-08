import {onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
import {businessNumberLeases,registerBusinessNumberField,newNumberWindowId} from '@/utils/businessNumberLeases'

export function useBusinessNumber(options) {
  const error=ref('')
  let lease=null,request=null,generation=0,timer=null,inputKey=''
  function releaseItem(item){fetch(`/api/business-numbers/${item.token}/release`,{method:'POST',keepalive:true,headers:{Authorization:`Bearer ${item.authToken}`}}).catch(()=>{})}
  function release(){
    generation++;clearInterval(timer);timer=null
    const old=lease;lease=null
    if(old){businessNumberLeases.delete(old.token);releaseItem(old)}
  }
  async function acquire(){
    release();error.value=''
    const current=generation,owner=localStorage.getItem('user_id'),model=options.model(),authToken=localStorage.getItem('token')
    registerBusinessNumberField(model,options.field())
    model[options.field()]=''
    request=api.post('/business-numbers/reserve',{kind:options.kind(),window_id:newNumberWindowId(),parent_id:options.parent()||null,business_date:options.date()||null}).then(result=>{
      const item={...result,kind:options.kind(),owner,authToken}
      if(current!==generation||owner!==localStorage.getItem('user_id')){releaseItem(item);return false}
      lease=item;businessNumberLeases.set(item.token,item);model[options.field()]=item.number
      if(options.field()==='orderNo'&&model.emailSubjectPreview)model.emailSubjectPreview=model.emailSubjectPreview.replace(/\b(?:TP|IP|AP|HP)-(?:\d{6}|\d{8})-\d{3,}\b/,item.number)
      timer=setInterval(async()=>{try{await api.post(`/business-numbers/${item.token}/heartbeat`)}catch{if(lease===item)error.value='编号占用无法续期，请重新打开新增窗口；填写内容将保留'}},60000)
      return true
    }).catch(cause=>{if(current===generation)error.value=cause.message||'编号占用失败，请重新打开窗口重试';return false})
    return request
  }
  watch(()=>[options.active(),options.kind(),options.parent(),options.date(),localStorage.getItem('user_id'),options.kind()==='greeting'?options.model()?.id:null],([active,kind,parent,date,owner,recordKey])=>{
    const key=JSON.stringify([kind,parent,date,owner,recordKey])
    if(!active||!kind||!owner){release();inputKey='';return}
    if(key!==inputKey||!lease){inputKey=key;void acquire()}
  },{immediate:true,flush:'post'})
  watch(()=>options.model()?.[options.field()],value=>{if(lease&&options.active()&&value!==lease.number)options.model()[options.field()]=lease.number},{flush:'sync'})
  const logout=()=>{release();error.value='账号已退出，请重新登录后打开新增窗口'}
  const accountChanged=event=>{if(event.key==='user_id'&&lease?.owner!==localStorage.getItem('user_id'))logout()}
  window.addEventListener('auth-session-clearing',logout);window.addEventListener('pagehide',release)
  window.addEventListener('storage',accountChanged)
  onBeforeUnmount(()=>{release();window.removeEventListener('pagehide',release);window.removeEventListener('auth-session-clearing',logout);window.removeEventListener('storage',accountChanged)})
  async function ensure(){if(!options.active())return true;if(request)await request;return Boolean(lease)&&lease.owner===localStorage.getItem('user_id')&&!error.value}
  return {error,ensure,headers:()=>lease?{'X-Business-Number-Leases':JSON.stringify([lease.token])}:{}}
}
