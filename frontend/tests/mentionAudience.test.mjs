import test from 'node:test'
import assert from 'node:assert/strict'
import { mentionAudience } from '../src/utils/mentionAudience.js'
import { projectMentionOrder } from '../src/utils/projectMentionOrder.js'
const members = [{id:'self',name:'我'}, {id:1,name:'同名'}]
const outside = [{id:'1',name:'同名'}, {id:2,name:'同名',username:'outside'}, {id:3,name:'其他'}]
test('默认只显示群内成员和所有人，排除本人及重复ID',()=>{
  assert.deepEqual(mentionAudience(members,outside,{currentUserId:'self'}).map(p=>p.id),['__all__',1])
})
test('展开后保留群内顺序并区分可邀请人员，收起恢复默认',()=>{
  assert.deepEqual(mentionAudience(members,outside,{expanded:true,currentUserId:'self'}).map(p=>[p.id,p.outside]),[['__all__',false],[1,false],[2,true],[3,true]])
})
test('姓名和账号搜索可补全群外人员，同名不同ID保留独立选项',()=>{
  assert.deepEqual(mentionAudience(members,outside,{query:'同名',currentUserId:'self'}).map(p=>p.id),[1,2])
  assert.deepEqual(mentionAudience(members,outside,{query:'outside',currentUserId:'self'}).map(p=>p.id),[2])
})
test('选中的群外人员在清空搜索后仍保留标签对应选项',()=>{
  assert.deepEqual(mentionAudience(members,outside,{selected:[2],currentUserId:'self'}).map(p=>p.id),['__all__',1,2])
})
test('群外项目经理也放在群外分区，不能混入群内经理名单',()=>{
  const list = mentionAudience(members,outside,{expanded:true,currentUserId:'self'})
  const ordered = projectMentionOrder(list,{projectManagerId:2})
  assert.equal(ordered.at(-1).outside,true)
  assert.ok(ordered.filter(p=>p.outside).every(p=>p.mentionSection==='群外人员 · 发送后邀请入群'))
  assert.ok(ordered.findIndex(p=>p.id===1)<ordered.findIndex(p=>p.id===2))
})
