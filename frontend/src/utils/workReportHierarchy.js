import {newReportRow,rowTypes} from './workReportForm.js'

export const reportRowKey=row=>row.display_metadata?._feedback_key||row.id
export const parentRowKey=row=>row.display_metadata?.parent_item_key||''
const orderKey=row=>String(row.display_metadata?.order_no||'').trim().toLocaleLowerCase()
export function ensureReportKeys(rows){for(const row of rows){row.display_metadata||={};row.display_metadata._feedback_key||=row.id||crypto.randomUUID()}}
export function reportRoot(rows,row){const parent=parentRowKey(row);return parent?rows.find(item=>reportRowKey(item)===parent)||row:row}
function inherit(child,parent){
 child.task_type=parent.task_type;child.task_name=parent.task_name
 const target=child.display_metadata,source=parent.display_metadata||{}
 target.parent_item_key=reportRowKey(parent);target.order_no=source.order_no||'';target.report_types=rowTypes(parent)
 for(const key of ['custom_project_type','custom_work_types']){if(source[key]!=null)target[key]=JSON.parse(JSON.stringify(source[key]));else delete target[key]}
}
export function syncReportChildren(rows){
 ensureReportKeys(rows)
 for(const row of rows){if(!parentRowKey(row))continue;const parent=rows.find(item=>reportRowKey(item)===parentRowKey(row));if(parent&&parent!==row&&!parentRowKey(parent))inherit(row,parent);else delete row.display_metadata.parent_item_key}
}
export function groupReportRows(rows){
 const roots=rows.filter(row=>!parentRowKey(row)),result=[]
 for(const root of roots){result.push(root,...rows.filter(row=>parentRowKey(row)===reportRowKey(root)))}
 rows.splice(0,rows.length,...result)
}
export function nestDuplicateOrder(rows,row){
 ensureReportKeys(rows)
 if(parentRowKey(row)||!orderKey(row))return false
 const candidate=rows.find(item=>item!==row&&orderKey(item)===orderKey(row))
 if(!candidate)return false
 const parent=reportRoot(rows,candidate)
 if(parent===row)return false
 for(const child of rows.filter(item=>parentRowKey(item)===reportRowKey(row)))inherit(child,parent)
 inherit(row,parent);groupReportRows(rows);return true
}
export function appendChildRows(rows,row,count=1){
 const number=Number(count)
 if(!Number.isInteger(number)||number<1||number>100)throw new Error('新增下级行数须为1至100的整数')
 ensureReportKeys(rows);const parent=reportRoot(rows,row)
 const children=Array.from({length:number},()=>{const child=newReportRow();ensureReportKeys([child]);inherit(child,parent);return child})
 rows.push(...children);groupReportRows(rows);return children
}
export function reportOutline(rows){
 const roots=rows.filter(row=>!parentRowKey(row)),counts=new Map()
 return rows.map(row=>{if(!parentRowKey(row))return String(roots.indexOf(row)+1);const key=parentRowKey(row),index=roots.findIndex(item=>reportRowKey(item)===key);if(index<0)return String(rows.indexOf(row)+1);const count=(counts.get(key)||0)+1;counts.set(key,count);return `${index+1}.${count}`})
}
