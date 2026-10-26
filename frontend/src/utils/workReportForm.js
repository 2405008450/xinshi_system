export const projectTypes = ['笔译项目','口译项目','招聘项目','标注项目','配音项目','字幕项目','公证项目','认证项目','新咨询对接','其他项目']
export function reportBusinessDate(value=new Date()) {const date=value instanceof Date?value:new Date(value);if(Number.isNaN(date.getTime()))return '';return new Date(date.getTime()+60*60*1000).toISOString().slice(0,10)}
export const defaultWorkCategories = {
  项目工作: projectTypes,
  非项目工作: ['接待客户','研究工作','开发工作','技术支持','行政工作','人事工作'],
  外勤工作: ['拜访客户','口译现场','投标','陪标'],
  管理工作: ['查看工作报告','分析数据']
}
export function categoryValue(parent,name) {return parent==='项目工作'&&projectTypes.includes(name)?name:`${parent}::${name}`}
export function buildWorkTypeOptions(categories=defaultWorkCategories,rows=[]) {
  const groups=Object.fromEntries(Object.entries(defaultWorkCategories).map(([parent,names])=>[parent,[...(categories[parent]||names)]]))
  for(const row of rows)for(const value of rowTypes(row))if(value.includes('::')){const [parent,name]=value.split('::');if(groups[parent]&&name!=='__custom__'&&!groups[parent].includes(name))groups[parent].push(name)}
  return Object.entries(groups).map(([parent,names])=>({value:parent,label:parent,children:[...names.map(name=>({value:categoryValue(parent,name),label:name})),...(parent!=='项目工作'?[{value:`${parent}::__custom__`,label:'其他（自定义）'}]:[]),...(rows.some(row=>rowTypes(row).includes(parent))?[{value:parent,label:parent}]:[])]}))
}
export const workTypeOptions = buildWorkTypeOptions()
export const durationOptions = [...Array.from({length:6},(_,i)=>(i+1)*10),...Array.from({length:230},(_,i)=>66+i*6)]
export function durationLabel(minutes) { const n=Number(minutes)||0;return n<=60?`${n}分钟`:`${Number((n/60).toFixed(1))}小时` }
export function shiftReportDate(value,days) { const date=new Date(`${value}T12:00:00+08:00`);date.setUTCDate(date.getUTCDate()+days);return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(date) }
export function reportWeekday(value) {return value?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Hong_Kong',weekday:'long'}).format(new Date(`${value}T12:00:00+08:00`)):''}
export function rowTypes(row) {
  if(Array.isArray(row.display_metadata?.report_types))return [...row.display_metadata.report_types]
  const type=String(row.display_metadata?.project_type||''),order=String(row.display_metadata?.order_no||'')
  const inferred={translation:'笔译项目',interpretation:'口译项目',annotation:'标注项目',recruitment:'招聘项目'}[type]||({TP:'笔译项目',IP:'口译项目',AP:'标注项目',RP:'招聘项目'}[order.split('-')[0]])
  return inferred?[inferred]:projectTypes.includes(row.task_type)?[row.task_type]:['非项目工作']
}
export function normalizeReportRow(row) {return {...row,display_metadata:{...(row.display_metadata||{}),_feedback_key:row.display_metadata?._feedback_key||row.id,report_types:rowTypes(row)},duration_minutes:Number(row.duration_minutes)||0}}
export function newReportRow() {return {source_type:'manual',source_id:null,task_type:'非项目工作',task_name:'',progress_content:'',result_content:'',duration_minutes:0,display_metadata:{report_types:[]}}}
export function requiresProjectIdentity(row) {return rowTypes(row).some(type=>type!=='非项目工作'&&!type.startsWith('非项目工作::'))}
export function updateRowTypes(row,types) {types=[...new Set(types)];row.display_metadata.report_types=types;row.task_type=[...new Set(types.map(type=>projectTypes.includes(type)?'项目工作':type.split('::')[0]))].join('、')||'非项目工作'}
export function appendReportRows(rows,count=1) {const n=Number(count);if(!Number.isInteger(n)||n<1||n>100)throw new Error('新增行数须为1至100的整数');rows.push(...Array.from({length:n},newReportRow))}
export function blockReportImages(event) {
  const data=event.clipboardData||event.dataTransfer
  if([...Array.from(data?.items||[]),...Array.from(data?.files||[])].some(item=>item.type?.startsWith('image/'))||/screenshot:\/\/|data:image\//i.test(data?.getData('text/plain')||'')||/<img\b/i.test(data?.getData('text/html')||'')){event.preventDefault();event.stopPropagation();return true}
  return false
}
export function validQuantity(value) {return value===''||value==null||Number.isFinite(Number(value))&&Number(value)>=0}
