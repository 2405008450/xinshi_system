// 以原考勤日的18:50（UTC+8）为界，跨午夜签退仍归原考勤日。
export function requiresDinnerConfirmation(day,moment=Date.now()){
  if(!day||moment==null||moment==='')return false
  let value=moment
  if(typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value))value+='+08:00'
  return new Date(value).getTime()>new Date(`${day}T18:50:00+08:00`).getTime()
}
