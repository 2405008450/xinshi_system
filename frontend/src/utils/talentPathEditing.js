export const pathFields = [
  {key:'resourceCode',label:'人才编号',width:155,max:50,required:true},
  {key:'fullName',label:'姓名',width:155,max:255,required:true},
  {key:'ancestralHome',label:'籍贯',width:155,max:255},
  {key:'nativePlace',label:'主要成长地',width:165,max:255},
  {key:'residenceAddress',label:'目前所在地',width:180,max:500},
  {key:'resumePath',label:'路径',width:300,max:20000},
]
export const pathContactFields = [
  {key:'primaryPhone',label:'主要电话',max:50},{key:'secondaryPhone',label:'备用电话',max:50},
  {key:'primaryEmail',label:'主要邮箱',max:255},{key:'secondaryEmail',label:'备用邮箱',max:255},
  {key:'wechat',label:'微信号',max:100},{key:'whatsapp',label:'WhatsApp',max:100},
  {key:'skype',label:'Skype',max:100},{key:'line',label:'Line',max:100},
  {key:'otherContact',label:'其他联系方式',max:255},{key:'contactInfo',label:'兼容联系方式',max:500},
]
export const allPathFields = [...pathFields,...pathContactFields]
export const pathSnapshot = row => Object.fromEntries(allPathFields.map(field=>[field.key,row[field.key]??null]))
export const pathChanges = row => {
  const changes={},expectedValues={}
  for(const field of allPathFields){
    if(row.contactRestricted&&pathContactFields.some(item=>item.key===field.key))continue
    if(String(row[field.key]??'')!==String(row._original?.[field.key]??'')){
      changes[field.key]=row[field.key]??null;expectedValues[field.key]=row._original?.[field.key]??null
    }
  }
  return {changes,expectedValues}
}
