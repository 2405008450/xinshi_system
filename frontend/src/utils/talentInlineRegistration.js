import {quickContactFields} from './talentQuickRegister.js'
export const inlineTalentNameFields=[{key:'chineseName',label:'中文姓名'},{key:'englishName',label:'外文姓名'},{key:'nickname',label:'昵称'}]
export const inlineTalentContactFields=[...quickContactFields,{key:'contactInfo',label:'兼容联系方式'}]
export function newInlineTalentForm(name=''){
 const form={chineseName:'',englishName:'',nickname:'',otherNamesText:'',resumePath:'',...Object.fromEntries(inlineTalentContactFields.map(field=>[field.key,'']))}
 form[/[\u3400-\u9fff]/.test(name)?'chineseName':/[a-z]/i.test(name)?'englishName':'chineseName']=String(name||'').trim()
 return form
}
export function inlineTalentMissingFields(form){
 const names=[...inlineTalentNameFields.map(field=>form[field.key]),...String(form.otherNamesText||'').split(/\r?\n/)]
 const missing=[]
 if(!names.some(value=>String(value||'').trim()))missing.push({prop:'nameGroup',message:'姓名至少填写一项（中文姓名、外文姓名、昵称或其他名字）'})
 if(!inlineTalentContactFields.some(field=>String(form[field.key]||'').trim()))missing.push({prop:'primaryPhone',message:'联系方式至少填写一项（手机/电话、微信、邮箱等）'})
 if(!String(form.resumePath||'').trim())missing.push({prop:'resumePath',message:'请填写简历路径'})
 return missing
}
export function inlineTalentPayload(form,contactsAllowed=false,allowDuplicate=false){
 const missing=inlineTalentMissingFields(form)
 if(missing.length)throw new Error(missing.map(item=>item.message).join('；'))
 const otherNames=String(form.otherNamesText||'').split(/\r?\n/).map(name=>name.trim()).filter(Boolean)
 const names=inlineTalentNameFields.map(field=>String(form[field.key]||'').trim())
 const fullName=[...names,...otherNames].find(Boolean)
 if(!fullName)throw new Error('中文姓名、外文姓名、昵称或其他名字至少填写一项')
 if([...names,...otherNames].some(name=>name.length>255))throw new Error('每个姓名不能超过255字')
 const payload={fullName,chineseName:names[0]||null,englishName:names[1]||null,nickname:names[2]||null,otherNames,
  resumePath:String(form.resumePath||'').trim()||null,capabilities:[{capabilityType:'interpretation',status:'active'}],registrationSource:'口译项目登记',allowDuplicate}
 if(contactsAllowed)for(const field of inlineTalentContactFields)payload[field.key]=String(form[field.key]||'').trim()||null
 return payload
}
