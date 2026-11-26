import test from 'node:test'
import assert from 'node:assert/strict'
import {emptyInterpreterRequirements,interpreterRequirementDirections} from '../src/utils/interpreterRequirements.js'
test('方向与人数取自项目信息，语种标签加载后更新展示',()=>{
 const directions=[{languageIds:['cn','en'],requiredCount:2},{languageIds:['cn','ja'],requiredCount:1},{languageIds:['',''],requiredCount:null}]
 const languages=[{id:'cn',label:'中文'},{id:'en',label:'英语'},{id:'ja',label:'日语'}]
 assert.equal(interpreterRequirementDirections(directions,languages),'中文 ↔ 英语（2人）；中文 ↔ 日语（1人）')
 assert.equal(interpreterRequirementDirections([],languages),'')
 directions[0].requiredCount=3
 assert.match(interpreterRequirementDirections(directions,languages),/英语（3人）/)
})
test('新表单要求对象相互独立',()=>{
 const first=emptyInterpreterRequirements(),second=emptyInterpreterRequirements()
 first.passport='有效期半年以上'
 assert.equal(second.passport,'')
})
