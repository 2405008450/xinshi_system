import {emptyResumeSupplements,professionalDomains} from './talentResumeSections.js'
export const catToolOptions = ['Trados Studio','memoQ','Phrase TMS','Wordfast Pro','Smartcat','OmegaT'].map(value=>({value,label:value}))
// 名称参考各工具官方产品页；品牌名在不同语言版本中保持原名。
export const educationDegreeOptions = [
  ['primary','小学'],['junior_secondary','初中'],['senior_secondary','高中'],['secondary_vocational','中专/职高'],
  ['associate','专科'],['bachelor','本科'],['second_degree','第二学位'],['master','硕士研究生'],['doctor','博士研究生'],['other','其他'],
].map(([value,label])=>({value,label}))
export const newExperience = () => ({id:crypto.randomUUID(),period:'',organization:'',position:'',workload:'',description:'',degree:null,graduationYear:null})
export const newEducation = () => ({id:null,_key:crypto.randomUUID(),educationLevel:null,period:'',institution:'',major:'',remarks:'',institutionCategory:'',majorCategory:'',graduationYear:null,minorMajor:'',degreeName:'',sortOrder:0})
export const emptyResumeProfile = () => ({...emptyResumeSupplements(),professionalDomains:[],revision:0,resumeYear:'',internships:[],annotation:[],interpretation:[],translation:[],other:[],catTools:[],educationPeriods:{},versions:{}})
const workFields={annotation:'annotationExperience',interpretation:'interpretationExperience',translation:'translationExperience',other:'otherExperience'}
export function resumeProfileForm(value,legacy={}){
  const result={...emptyResumeProfile(),...(value||{}),professionalDomains:professionalDomains(value||{},legacy.writtenProfile)}
  for(const [key,defaultValue] of Object.entries(emptyResumeSupplements()))result[key]=Array.isArray(defaultValue)?(value?.[key]||[]).map(row=>({...row})):value?.[key]||''
  for(const [key,field] of Object.entries(workFields))result[key]=Array.isArray(value?.[key])?value[key].map(row=>({...row})):legacy[field]?[{...newExperience(),description:legacy[field]}]:[]
  result.internships=Array.isArray(value?.internships)?value.internships.map(row=>({...row})):[]
  result.catTools=[...(value?.catTools||[])];result.versions=JSON.parse(JSON.stringify(value?.versions||{}));for(const version of Object.values(result.versions))if(Array.isArray(version.professionalDomains))version.professionalDomains=professionalDomains(version);return result
}
export const educationFormRows=(rows=[],periods={})=>rows.map(row=>({...row,_key:row.id||crypto.randomUUID(),period:row.period??periods[row.id]??(row.graduationYear?`毕业：${row.graduationYear}`:''),remarks:row.remarks||''}))
export const emptyResumeVersion=()=>({...emptyResumeSupplements(),professionalDomains:[],resumeYear:'',name:'',professionalTitle:'',gender:null,birthDate:'',nationality:'',residence:'',nativePlace:'',employmentStatus:null,highestEducation:null,height:'',eyesight:'',languages:[],languageNotes:'',certificates:'',skills:'',catTools:[],educations:[],internships:[],annotation:[],interpretation:[],translation:[],other:[]})
export function ensureResumeVersion(profile,locale){profile.versions[locale]={...emptyResumeVersion(),...(profile.versions[locale]||{})};return profile.versions[locale]}
