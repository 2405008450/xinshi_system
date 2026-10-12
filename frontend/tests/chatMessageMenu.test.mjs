import assert from 'node:assert/strict'
import test from 'node:test'
import { buildMessageMenu, clampMessageMenu } from '../src/utils/chatMessageMenu.js'
import { parseTopicNavigation, topicNavigationKey } from '../src/composables/useChatTopicNavigation.js'
const handlers = Object.fromEntries(['copy','reply','favorite','acknowledge','progress','select','recall'].map(key=>[key,()=>{}]))
test('消息菜单按照消息状态和权限限制操作',()=>{
  const row={content:'正文',messageType:'user',senderUserId:'other',canClassify:true,canRecall:true}
  assert.deepEqual(buildMessageMenu(row,{handlers,currentUserId:'me',canCollect:true,canProgress:true}).map(x=>x.id),['copy','reply','favorite','acknowledge','classify','collect','progress','select','recall'])
  assert.deepEqual(buildMessageMenu({...row,recalledAt:'已撤回'},{handlers}),[])
  assert.deepEqual(buildMessageMenu({...row,messageType:'handover'},{handlers,canCollect:true}).map(x=>x.id),['copy','favorite'])
  assert.deepEqual(buildMessageMenu({...row,canClassify:false,canRecall:false,senderUserId:'me'},{handlers,currentUserId:'me'}).map(x=>x.id),['copy','reply','favorite'])
  assert.equal(buildMessageMenu(row,{handlers:{...handlers,canAcknowledge:()=>false}}).some(x=>x.id==='acknowledge'),false)
  assert.equal(buildMessageMenu({...row,content:''},{handlers,canCollect:true,canProgress:true}).some(x=>['collect','progress','select'].includes(x.id)),false)
})
test('选中文字、收藏及自己的撤回文案',()=>{
 const items=buildMessageMenu({content:'文字',senderUserId:'me',isFavorited:true,canRecall:true},{handlers,currentUserId:'me',excerpt:'选中',canProgress:true})
 assert.equal(items.find(x=>x.id==='copy').label,'复制选中内容')
 assert.equal(items.find(x=>x.id==='favorite').label,'取消收藏')
 assert.equal(items.find(x=>x.id==='progress').label,'添加选中内容为进度')
 assert.equal(items.find(x=>x.id==='recall').label,'撤回')
})
test('菜单在视口边缘向内移动，保留边距',()=>{
 assert.deepEqual(clampMessageMenu({x:388,y:840},{width:218,height:310},{width:390,height:844}),{left:164,top:526})
 assert.deepEqual(clampMessageMenu({x:-5,y:-10},{width:218,height:310},{width:390,height:844}),{left:8,top:8})
})
test('主题折叠配置按账号隔离、验证并清理损坏数据',()=>{
 assert.notEqual(topicNavigationKey('a'),topicNavigationKey('b'))
 assert.deepEqual(parseTopicNavigation({collapsed:false,expanded:[]}),{collapsed:false,expanded:[]})
 assert.deepEqual(parseTopicNavigation({collapsed:true,expanded:['root','root',null,2]}),{collapsed:true,expanded:['root']})
 assert.throws(()=>parseTopicNavigation({collapsed:'yes',expanded:[]}))
 assert.throws(()=>parseTopicNavigation({collapsed:false,expanded:{}}))
})
