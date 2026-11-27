import {businessDateTimeInputValue} from './dateTime.js'
export const favoriteTabs=[{id:'messages',label:'消息收藏'},{id:'projects',label:'各类项目'},{id:'technical',label:'技术/开发项目'},{id:'other',label:'其他会话/群'}]
export const favoriteProjectTypes=[{id:'annotation',label:'标注项目'},{id:'translation',label:'笔译项目'},{id:'interpretation',label:'口译项目'},{id:'recruitment',label:'招聘项目'},{id:'other',label:'其他项目'}]
const modules=new Set(favoriteProjectTypes.map(row=>row.id))
const kindOf=row=>row.projectType||row.kind
export const isSessionFavorite=row=>!!(row.starred || kindOf(row)==='annotation' && row.following===true)
export function favoriteClassification(row,nodes=[]){
 const title=String(row.title||row.projectName||'')
 let node=nodes.find(item=>item.id===row.projectId)||nodes.find(item=>row.categoryIds?.includes(item.id))
 const visited=new Set()
 while(node?.parentKey&&!visited.has(node.id)){visited.add(node.id);const parent=nodes.find(item=>item.id===node.parentKey);if(!parent)break;node=parent}
 const module=row.projectModule||node?.ruleKey||kindOf(row)
 if(module==='technical'||/\bDT-\d{6}-/.test(title+' '+(row.subtitle||''))||row.technicalProjectId||/技术需求|技术\s*[/／]\s*开发|技术开发|开发项目/.test(title))return {tab:'technical',type:'technical',label:'技术/开发项目'}
 if(kindOf(row)==='direct')return {tab:'other',type:'other',label:'其他会话/群'}
 let type=modules.has(module)?module:''
 if(!type){
  const prefix=`${row.subtitle||row.orderNo||''} ${title}`.match(/\b(AP|TP|IP|RP)-\d{6}-\d+/)?.[1]
  type=({AP:'annotation',TP:'translation',IP:'interpretation',RP:'recruitment'})[prefix]||''
 }
 if(!type)type=favoriteProjectTypes.find(item=>title.includes(item.label)&&/管理讨论|管理群|业务/.test(title))?.id||''
 return type?{tab:'projects',type,label:favoriteProjectTypes.find(item=>item.id===type).label}:{tab:'other',type:'other',label:'其他会话/群'}
}
export function favoriteProjectDate(row){
 const order=String(row.subtitle||row.orderNo||'').match(/\b(?:AP|TP|IP|RP|DT)-([0-9]{6})-/)||String(row.title||'').match(/\b(?:AP|TP|IP|RP|DT)-([0-9]{6})-/)
 if(order)return order[1]
 const date=businessDateTimeInputValue(row.projectCreatedAt||row.createdAt||'').slice(0,10)
 return /^\d{4}-\d{2}-\d{2}$/.test(date)?date.replaceAll('-','').slice(2):'未设置日期'
}
export function normalizeFavoriteTypeOrder(value){
 const valid=favoriteProjectTypes.map(item=>item.id)
 return [...new Set([...(Array.isArray(value)?value:[]).filter(id=>valid.includes(id)),...valid])]
}
export function favoriteGroups(pageRows,allRows,tab,nodes=[],order=[]){
 const keys=tab==='projects'?normalizeFavoriteTypeOrder(order):[tab]
 return keys.map(type=>{
  const match=row=>{const c=favoriteClassification(row,nodes);return c.tab===tab&&(tab!=='projects'||c.type===type)}
  const total=allRows.filter(match).length,items=pageRows.filter(match)
  if(!items.length)return null
  const dates=new Map()
  if(total>8)for(const row of items){const date=favoriteProjectDate(row);if(!dates.has(date))dates.set(date,[]);dates.get(date).push(row)}
  return {id:type,label:tab==='projects'?favoriteProjectTypes.find(item=>item.id===type).label:favoriteTabs.find(item=>item.id===tab).label,total,items,dates:[...dates].sort(([a],[b])=>b.localeCompare(a)).map(([label,items])=>({label,items}))}
 }).filter(Boolean)
}
