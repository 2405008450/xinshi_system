export const pairedProjectTypes = [
  ['paired_collection_annotation', '双人采标'], ['single_collection_annotation', '单人采标'], ['multi_collection_annotation', '多人采标'],
  ['single_audio_collection', '单人音频采集'], ['paired_audio_collection', '双人音频采集'], ['multi_audio_collection', '多人音频采集'],
  ['online_dispatch', '线上派遣'], ['onsite_dispatch', '驻场派遣'],
].map(([value, label]) => ({ value, label }))
export const assessmentStatuses = [
  ['assessment_preparation', '准备考核'], ['assessment_in_progress', '考核中'], ['assessment_completed', '考核结束'],
].map(([value, label]) => ({ value, label }))
export const willingnessOptions = [
  ['pending','待确认'], ['available','可参加'], ['collection_only','只做采集不做标注'], ['annotation_only','不做采集只做标注'],
  ['no_time','没时间'], ['declined','不参与'], ['this_time_declined','仅本次不参与'], ['no_pair','不做双人采集'], ['price_low','价格低不接'],
].map(([value,label])=>({value,label}))
export const taskStatuses = [
  ['pending','待开始'], ['in_progress','进行中'], ['withdrawn','已退出'], ['completed','已完成'], ['inspected','质检完成'], ['submitted','已提交客户'], ['accepted','客户已验收'], ['archived','已归档'],
].map(([value,label])=>({value,label}))
export const recordKinds = [
  ['price','单价调整'], ['training','培训'], ['trial','试采/试标与考核'], ['progress','进度节点'], ['inspection','质检'], ['repair','返修'], ['performance','人员表现'], ['account','账号引用'],
].map(([value,label])=>({value,label}))
export const optionLabel = (options, value) => options.find(item=>item.value===value)?.label || value || '-'
export function selectCandidateRatio(rows, percentage) {
  const unique = [...new Map(rows.filter(row=>!row.joined).map(row=>[row.id,row])).values()]
  const compare=(left,right)=>left===right?0:left<right?-1:1
  unique.sort((a,b)=>compare(String(a.resource_code || '\uffff'),String(b.resource_code || '\uffff')) || compare(a.id,b.id))
  return unique.slice(0, Math.ceil(unique.length * Math.min(100, Math.max(0, percentage)) / 100))
}
export function pairedDuration(data) {
  if (!data.actual_start || !data.actual_end) return null
  return (new Date(data.actual_end) - new Date(data.actual_start)) / 60000 + Number(data.duration_adjustment_minutes || 0)
}
