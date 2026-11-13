// 搜索结果独立于预加载目录及已选项；输入变化时立即失效旧请求和旧候选。
export function createRemoteTalentSearch({fetchOptions,onUpdate,onError}){
  let sequence=0,controller,disposed=false
  const publish=(keyword,items,loading)=>{if(!disposed)onUpdate({keyword,items,loading,active:true})}
  function input(value){
    const keyword=String(value??'')
    sequence++;controller?.abort();publish(keyword,[],false)
    return keyword
  }
  async function search(value){
    const keyword=input(value),request=sequence
    controller=new AbortController()
    publish(keyword,[],true)
    try{
      const rows=await fetchOptions(keyword,controller.signal)
      if(disposed||request!==sequence)return
      publish(keyword, Array.isArray(rows) ? rows : [], false)
    }catch(error){
      if(disposed||request!==sequence)return
      publish(keyword,[],false)
      if(error.code!=='ERR_CANCELED'&&error.name!=='AbortError')onError?.(error)
    }
  }
  return {input,search,dispose(){disposed=true;sequence++;controller?.abort()}}
}
