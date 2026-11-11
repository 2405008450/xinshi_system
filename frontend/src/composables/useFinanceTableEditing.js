import {reactive} from 'vue'
import {getCustomerFinanceProject,saveCustomerFinanceTable} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {financeDraft,financeDraftFields,financePatchKeys,financeFieldValue,sameFinanceField,copyFinanceValue} from '@/utils/financeTableDraft'

export function useFinanceTableEditing(onSaved){
  const states=reactive(new Map()),queues=new Map()
  const draftValue=(field,value,previous)=>field==='prices'?copyFinanceValue(value).map((price,index)=>({...price,_config:previous?.[index]?._config||false})):copyFinanceValue(value)
  function syncRow(row){
    let state=states.get(row.id)
    if(state?.row===row)return state
    const latest=financeDraft(row)
    if(!state){
      state=reactive({row,base:latest,draft:copyFinanceValue(latest),saving:false,error:'',pending:new Map()})
      states.set(row.id,state)
      return state
    }
    for(const field of financeDraftFields){
      if(sameFinanceField(field,state.draft[field],state.base[field])){state.base[field]=copyFinanceValue(latest[field]);state.draft[field]=draftValue(field,latest[field],state.draft[field])}
      else if(!sameFinanceField(field,latest[field],state.base[field])&&!sameFinanceField(field,latest[field],state.draft[field]))state.error='此字段已在其他窗口更新；未保存内容已保留，请核对后重新加载或重试。'
    }
    state.row=row
    return state
  }
  const stateFor=row=>states.get(row.id)
  function syncRows(rows){for(const row of rows){syncRow(row);syncRows(row.children||[])}}
  const find=(node,id)=>node.id===id?node:(node.children||[]).map(child=>find(child,id)).find(Boolean)
  async function persist(state){
    if(!state.pending.size)return true
    const pending=new Map(state.pending);state.pending.clear();state.saving=true;state.error=''
    try{
      const current=await getCustomerFinanceProject(state.row.rootId),node=find(current.item,state.row.id)
      if(!node)throw new Error('订单已不存在，请刷新列表')
      const latest=financeDraft(node),patch={version:current.version,order_id:state.row.id}
      for(const [field,change] of pending){
        if(!sameFinanceField(field,latest[field],state.base[field])&&!sameFinanceField(field,latest[field],change.value))throw new Error('该字段已被其他操作修改，请重新加载并核对后填写')
        patch[financePatchKeys[field]]=financeFieldValue(field,change.value)
      }
      const result=await saveCustomerFinanceTable(state.row.rootId,patch)
      const saved=financeDraft(find(result.item,state.row.id))
      for(const [field,change] of pending){
        state.base[field]=copyFinanceValue(saved[field])
        if(sameFinanceField(field,state.draft[field],change.value))state.draft[field]=draftValue(field,saved[field],state.draft[field])
      }
      // 切换模式后的金额清理由服务端执行，同步其他未编辑的单元格。
      if(pending.has('pricingMode'))for(const field of ['adjustedTotal','adjustedTotalInclTax','prices']){
        const dirty=!sameFinanceField(field,state.draft[field],state.base[field])
        state.base[field]=copyFinanceValue(saved[field])
        if(!dirty&&!state.pending.has(field))state.draft[field]=draftValue(field,saved[field],state.draft[field])
      }
      await onSaved(result)
      return true
    }catch(error){state.error=getLocalizedErrorMessage(error,error.message||'自动保存失败，请重试');return false}
    finally{state.saving=false}
  }
  function commit(row,field){
    const state=stateFor(row)
    if(sameFinanceField(field,state.draft[field],state.base[field])&&!state.saving&&!state.pending.has(field)){
      if(financeDraftFields.every(key=>sameFinanceField(key,state.draft[key],state.base[key])))state.error=''
      return Promise.resolve(true)
    }
    state.pending.set(field,{before:copyFinanceValue(state.base[field]),value:copyFinanceValue(state.draft[field])})
    const task=(queues.get(row.rootId)||Promise.resolve()).catch(()=>false).then(()=>persist(state))
    queues.set(row.rootId,task)
    return task
  }
  async function flush(){
    for(const state of states.values())for(const field of financeDraftFields)if(!sameFinanceField(field,state.draft[field],state.base[field]))void commit(state.row,field)
    await Promise.all([...queues.values()])
    return ![...states.values()].some(state=>state.error||financeDraftFields.some(field=>!sameFinanceField(field,state.draft[field],state.base[field])))
  }
  function discard(){for(const state of states.values()){state.base=financeDraft(state.row);state.draft=copyFinanceValue(state.base);state.error='';state.pending.clear()}}
  return {stateFor,syncRows,commit,flush,discard,states}
}
