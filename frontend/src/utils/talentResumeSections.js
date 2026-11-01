// 所有语言复用字段；本人自述不等于公司评级。
export const resumeSupplementSections = [
  {key:'selfAssessment',label:'自我评价',english:'Self assessment',group:'intro'},
  {key:'jobIntention',label:'求职意向',english:'Career objectives',group:'intro'},
  {key:'otherSkills',label:'其他技能',english:'Other skills',group:'skills'},
  {key:'interests',label:'兴趣爱好',english:'Interests',group:'skills'},
  {key:'training',label:'培训经历',english:'Training',group:'experience',entries:true},
  {key:'awardsHonors',label:'奖励和荣誉',english:'Awards and honors',group:'experience'},
  {key:'campusPositions',label:'校内职务',english:'Campus positions',group:'experience',entries:true},
  {key:'campusAwards',label:'校内奖励',english:'Campus awards',group:'experience',entries:true},
]
export const emptyResumeSupplements=()=>Object.fromEntries(resumeSupplementSections.map(s=>[s.key,s.entries?[]:'']))
export function resumeNames(detail={}) {
  const name=String(detail.fullName||'').trim(),rawChinese=String(detail.chineseName||'').trim()
  const chinese=/[\u3400-\u9fff]/.test(rawChinese)?rawChinese:''
  return {chineseName:chinese||(!detail.englishName&&/^[\u3400-\u9fff·\s]+$/.test(name)?name:''),englishName:detail.englishName||(!chinese&&rawChinese?rawChinese:!chinese&&!/[\u3400-\u9fff]/.test(name)?name:'')}
}
export const professionalDomains=(profile={},written={})=>Array.isArray(profile.professionalDomains)?profile.professionalDomains:[...(written?.domainSkills||[])]

export function resumeNamesWithAliases(detail={}) {
  const names=resumeNames(detail),aliases=[...(detail.otherNames||[])]
  const oldChinese=String(detail.chineseName||'').trim()
  if(oldChinese&&oldChinese!==names.chineseName&&oldChinese!==names.englishName)aliases.push(oldChinese)
  return {...names,otherNames:[...new Set(aliases)]}
}
