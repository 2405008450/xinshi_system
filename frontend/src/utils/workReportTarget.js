const types = {笔译项目:'translation',配音项目:'translation',字幕项目:'translation',公证项目:'translation',认证项目:'translation',口译项目:'interpretation',标注项目:'annotation',招聘项目:'recruitment',新咨询对接:'consultation'}
const prefixes = {TP:'笔译项目',IP:'口译项目',AP:'标注项目',RP:'招聘项目'}
export function reportProjectIdentity(row) {
  const metadata = row?.display_metadata || {}
  const orderNo = String(metadata.order_no || '').trim()
  if(metadata.technical_task_id)return {category:'开发工作',sourceType:'technical',projectId:String(metadata.technical_task_id),orderNo}
  const selected = metadata.selected_project_type
  const category = types[selected] ? selected : (metadata.report_types || []).find(type => types[type]) || prefixes[orderNo.split('-')[0]]
  const sourceType = types[category] || (['translation','interpretation','annotation','recruitment'].includes(metadata.project_type) ? metadata.project_type : '')
  const projectId = metadata.project_id || metadata.consultation_id
  return {category:category || Object.keys(types).find(key=>types[key]===sourceType),sourceType,projectId:projectId ? String(projectId) : '',orderNo}
}
// 搜索为模糊匹配，跳转必须再核对完整订单号；多个匹配时不能猜测目标。
export function exactReportProject(items, orderNo) {
  const matches = (items || []).filter(item=>String(item.order_no || '').trim().toLowerCase()===orderNo.trim().toLowerCase())
  return matches.length===1 ? matches[0] : null
}
