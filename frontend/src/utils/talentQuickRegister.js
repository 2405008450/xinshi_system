export const quickNameFields = [
  {key:'chineseName',label:'中文姓名'}, {key:'englishName',label:'外文姓名'},
  {key:'nickname',label:'昵称'}, {key:'otherName',label:'其他姓名'},
]
export const quickContactFields = [
  {key:'primaryPhone',label:'手机/电话'}, {key:'secondaryPhone',label:'备用电话'},
  {key:'wechat',label:'微信'}, {key:'whatsapp',label:'WhatsApp'},
  {key:'primaryEmail',label:'邮箱'}, {key:'secondaryEmail',label:'备用邮箱'},
  {key:'skype',label:'Skype'}, {key:'line',label:'Line'}, {key:'otherContact',label:'其他联系方式'},
]
export function quickRegistrationPayload(form, allowDuplicate=false){
  const names=quickNameFields.filter(field=>form.nameKinds.includes(field.key))
  const contacts=quickContactFields.filter(field=>form.contactKinds.includes(field.key))
  if(names.length<1||names.length>2||contacts.length<1||contacts.length>2)throw new Error('姓名和联系方式均须选择1～2种')
  const result={fullName:'',capabilities:[],allowDuplicate}
  for(const field of [...names,...contacts]){
    const value=String(form[field.key]||'').trim()
    if(!value)throw new Error(`请填写${field.label}`)
    if(field.key==='otherName')result.otherNames=[value]
    else result[field.key]=value
    if(names.includes(field)&&!result.fullName)result.fullName=value
  }
  for(const key of ['punctualityLevel','cooperationLevel'])result[key]=form[key]||null
  return result
}
export function newQuickRegistrationRow(){
  return Object.assign(Object.fromEntries([...quickNameFields,...quickContactFields].map(field=>[field.key,''])),{
    _key:crypto.randomUUID(),_createState:{key:'',signature:''},_error:'',_existing:null,punctualityLevel:null,cooperationLevel:null,
  })
}
