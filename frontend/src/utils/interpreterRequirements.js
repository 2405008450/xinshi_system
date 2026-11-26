export const interpreterRequirementFields=[
 {key:'bringVehicle',label:'带车要求',placeholder:'是否需自带车辆、车型及费用等'},
 {key:'driving',label:'开车要求',placeholder:'是否需要驾驶、驾驶场景及工作安排等'},
 {key:'drivingLicense',label:'驾照要求',placeholder:'驾照类型、准驾车型及有效期等'},
 {key:'certificates',label:'证书要求',placeholder:'翻译资质、学历或其他证书要求'},
 {key:'photos',label:'照片要求',placeholder:'照片类型、数量、格式等'},
 {key:'audio',label:'音频要求',placeholder:'录音内容、语种、时长或格式等'},
 {key:'video',label:'视频要求',placeholder:'视频内容、时长、格式等'},
 {key:'interview',label:'面试要求',placeholder:'面试方式、时间及其他安排'},
 {key:'guideLicenses',label:'导游证等证件要求',placeholder:'导游证或其他专项证件要求'},
 {key:'passport',label:'护照要求',placeholder:'护照类型、有效期等'},
 {key:'visa',label:'签证要求',placeholder:'目的地、签证类型及有效期等'},
 {key:'hongKongMacauPermit',label:'港澳通行证及签注要求',placeholder:'香港、澳门通行证及签注等要求'},
]
export const emptyInterpreterRequirements=()=>Object.fromEntries(interpreterRequirementFields.map(field=>[field.key,'']))
export function interpreterRequirementDirections(directions,languages){
 const labels=new Map(languages.map(item=>[item.id,item.label]))
 return directions.filter(item=>item.languageIds?.length>=2&&item.languageIds.every(Boolean)).map(item=>
  item.languageIds.map(id=>labels.get(id)||'语种加载中').join(' ↔ ')+(item.requiredCount?`（${item.requiredCount}人）`:'（人数待填写）')).join('；')
}
