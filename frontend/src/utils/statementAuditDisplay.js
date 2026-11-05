// 审计原始数据保持不变；这里只转换为可阅读的业务对照行。
const names={before:'修改前',after:'修改后',fields:'',rows:'任务',boards:'对账单',tasks:'任务',name:'名称',board_name:'对账单',order_no:'订单号',month:'账单月份',months:'账单月份',board_id:'所属对账单',task_id:'任务',task_ids:'任务',company:'公司抬头',title:'对账单标题',client_name:'客户名称',client_code:'客户编号',customer_order_no:'客户单号',bank_name:'开户行',account_name:'账户名',account_number:'账号',stamp_image:'印章',tax_included:'金额口径',issue_date:'账单日期',billing_label:'账单月份显示',billing_month:'账单月份',billing_months:'账单月份',project_name:'项目名称',language_pair:'翻译方向',received_date:'来稿日期',quantity:'工作量',basis:'计价方式',unit_price:'单价',unit_size:'每份单价对应数量',unit_label:'单价口径',currency:'货币',subtotal:'小计',remarks:'备注',counted_in_total:'计入合计',pending:'待入账',pending_from:'原归属',origin_client_name:'原客户',added_tasks:'新增任务',existing_tasks_kept:'保留已有任务',deleted_boards:'删除对账单',removed_tasks:'移除任务',excluded_tasks:'排除无需对账单任务',accepted_pending:'纳入待入账任务',returned_to_pending:'退回待入账任务',restored_before_revision:'恢复到版本',x:'横向位置',y:'纵向位置',content:'任务内容',overrides:'汇总行调整',reason:'原因',action:'操作',target:'目标',source:'来源',from:'原位置',to:'新位置'}
const internal=new Set(['id','row_id','line_id','root_id','origin_client_id','client_id','version','roots'])
const uuid=/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)
export function statementAuditRows(changes,{labels={},before={},after={},boards=[],tasks={}}={}){
  const dictionary={...names,board_order:'排列顺序',target_client_name:'账单归属客户',...labels},references=new Map()
  for(const payload of [before,after,{boards,tasks}]){
    for(const board of payload?.boards||[])references.set(board.id,board.name||'未命名对账单')
    for(const [id,task] of Object.entries(payload?.tasks||{})){
      references.set(id,task.rows?.[0]?.order_no||'任务')
      for(const row of task.rows||[])references.set(row.line_id,row.order_no||row.project_name||'任务')
    }
  }
  const label=key=>dictionary[key]??references.get(key)??(uuid.test(key)?'记录':'变更项')
  const display=(value,key='')=>{
    if(value==null||value==='')return '未填写'
    if(key==='stamp_image')return '已设置印章'
    if(typeof value==='boolean')return key==='tax_included'?(value?'含税':'不含税'):(value?'是':'否')
    if(Array.isArray(value))return value.length?value.map(item=>display(item,key)).join('；'):'无'
    if(object(value))return Object.entries(value).filter(([name])=>!internal.has(name)&&!(name==='board_id'&&value.board_name)).map(([name,item])=>`${label(name)}：${display(item,name)}`).join('；')||'无'
    const text=String(value)
    if(text.startsWith('data:image/'))return '已设置印章'
    return references.get(text)||(uuid.test(text)?'关联记录':text)
  }
  const result=[]
  function walk(value,path=[],fieldKey=''){
    if(Array.isArray(value)){value.forEach((item,index)=>walk(item,[...path,...(object(item)?[]:[`第 ${index+1} 项`])]));return}
    if(!object(value)){result.push({field:path.join(' / ')||'变更内容',before:'—',after:display(value)});return}
    const context=value.board_name||value.order_no
    const current=context?[...path,String(context)]:path
    if(Object.hasOwn(value,'before')||Object.hasOwn(value,'after')){
      result.push({field:current.join(' / ')||'调整内容',before:display(value.before,fieldKey),after:display(value.after,fieldKey)});return
    }
    for(const [key,item] of Object.entries(value)){
      if(internal.has(key)||key==='board_name'||key==='order_no'||key==='board_id'&&context)continue
      const next=label(key);walk(item,next?[...current,next]:current,key)
    }
  }
  walk(changes)
  return result
}

export function statementSnapshotRows(before={},after={},options={}){
  const changes=[]
  const compare=(oldValue,newValue,path=[])=>{
    if(JSON.stringify(oldValue)===JSON.stringify(newValue))return
    if(object(oldValue)||object(newValue)){
      for(const key of new Set([...Object.keys(oldValue||{}),...Object.keys(newValue||{})])){
        if(internal.has(key))continue
        compare(oldValue?.[key],newValue?.[key],[...path,key])
      }
    }else if(Array.isArray(oldValue)||Array.isArray(newValue)){
      const oldList=oldValue||[],newList=newValue||[]
      if([...oldList,...newList].every(item=>object(item)&&(item.id||item.line_id))){
        const oldMap=Object.fromEntries(oldList.map(item=>[item.id||item.line_id,item])),newMap=Object.fromEntries(newList.map(item=>[item.id||item.line_id,item]))
        compare(oldMap,newMap,path)
      }else changes.push({path,before:oldValue,after:newValue})
    }else changes.push({path,before:oldValue,after:newValue})
  }
  compare(before,after)
  if(JSON.stringify((before.boards||[]).map(board=>board.id))!==JSON.stringify((after.boards||[]).map(board=>board.id)))changes.push({path:['board_order'],before:(before.boards||[]).map(board=>board.id),after:(after.boards||[]).map(board=>board.id)})
  return changes.flatMap(change=>{
    let value={before:change.before,after:change.after}
    for(const key of [...change.path].reverse())value={[key]:value}
    return statementAuditRows(value,{...options,before,after})
  })
}
