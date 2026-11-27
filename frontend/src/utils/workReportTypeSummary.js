import {rowTypes,projectTypes} from './workReportForm.js'

function typesFor(item){
  let types=rowTypes(item)
  if(!Array.isArray(item.display_metadata?.report_types)&&types[0]==='非项目工作'&&item.task_type)types=[item.task_type]
  return [...new Set(types)].filter(Boolean)
}
const minutesFor=item=>Number.isFinite(Number(item.duration_minutes))?Math.max(0,Number(item.duration_minutes)):0
const compareTypes=(a,b)=>a.localeCompare(b,'zh-CN')

function categoryFor(type,item){
  if(projectTypes.includes(type))return {parent:'项目工作',child:type==='其他项目'?item.display_metadata?.custom_project_type||type:type}
  const parts=type.includes('::')?type.split('::'):type.split(/\s*[／/]\s*/)
  const parent=parts.shift().trim()||'未分类'
  let child=parts.join(' / ').trim()
  if(child==='__custom__')child=item.display_metadata?.custom_work_types?.[parent]||'其他'
  return {parent,child:child||'未细分'}
}

function addTask(tasks,item,minutes){
  const key=JSON.stringify([item.display_metadata?.project_id||'',item.display_metadata?.order_no||'',item.task_name||'',String(item.progress_content||'').trim()])
  if(!tasks.has(key))tasks.set(key,{key,name:item.task_name||'非项目任务',content:item.progress_content||'',minutes:0,count:0})
  const task=tasks.get(key)
  task.minutes+=minutes;task.count++
}

export function summarizeReportTypes(items=[]){
  const groups=new Map()
  for(const item of items){
    const parents=new Map()
    for(const type of typesFor(item)){
      const {parent,child}=categoryFor(type,item)
      if(!parents.has(parent))parents.set(parent,new Set())
      parents.get(parent).add(child)
    }
    for(const [parent,children] of parents){
      if(!groups.has(parent))groups.set(parent,{type:parent,label:parent,minutes:0,tasks:new Map(),children:new Map()})
      const group=groups.get(parent),minutes=minutesFor(item)
      group.minutes+=minutes
      addTask(group.tasks,item,minutes)
      for(const child of children){
        if(!group.children.has(child))group.children.set(child,{type:child,label:child,minutes:0,tasks:new Map()})
        const subgroup=group.children.get(child)
        subgroup.minutes+=minutes
        addTask(subgroup.tasks,item,minutes)
      }
    }
  }
  return [...groups.values()].sort((a,b)=>compareTypes(a.type,b.type)).map(group=>({...group,tasks:[...group.tasks.values()],children:[...group.children.values()].sort((a,b)=>compareTypes(a.type,b.type)).map(child=>({...child,tasks:[...child.tasks.values()]}))}))
}

export function reportItemsSortedByType(items=[]){
  const category=item=>categoryFor(typesFor(item)[0]||'未分类',item)
  return items.map((item,index)=>({item,index})).sort((a,b)=>{
    const left=category(a.item),right=category(b.item)
    return compareTypes(left.parent,right.parent)||compareTypes(left.child,right.child)||a.index-b.index
  })
}
