import test from 'node:test'
import assert from 'node:assert/strict'
import {quoteSpeakerMention,clearAutomaticQuoteMention} from '../src/utils/quoteSpeakerMention.js'
const a={id:'a',name:'甲'},b={id:'b',name:'乙'},me='self'
const quote=(message,extra={})=>quoteSpeakerMention({message,currentUserId:me,content:'已有草稿',selectedUsers:[],users:[a,b],...extra})
test('引用默认插入说话人提及并携带真实人员ID，保留草稿',()=>{
 const result=quote({senderUserId:a.id})
 assert.equal(result.content,'@甲 已有草稿');assert.deepEqual(result.selectedUsers,[a])
 assert.deepEqual(result.automatic,{id:'a',token:'@甲 '})
})
test('切换引用与取消仅移除自动提及，保留手工提及',()=>{
 const first=quote({senderUserId:a.id},{content:'@乙 草稿',selectedUsers:[b]})
 const second=quote({senderUserId:b.id},{...first})
 assert.equal(second.content,'@乙 草稿');assert.deepEqual(second.selectedUsers,[b]);assert.equal(second.automatic,null)
 const cancelled=clearAutomaticQuoteMention(first.content,first.selectedUsers,first.automatic)
 assert.equal(cancelled.content,'@乙 草稿');assert.deepEqual(cancelled.selectedUsers,[b])
 const manual=quote({senderUserId:a.id},{content:'@甲 草稿',selectedUsers:[a]})
 assert.equal(manual.content,'@甲 草稿');assert.equal(manual.automatic,null)
})
test('不提及自己，不自动邀请会话外人员，不重复提及；保持20人上限',()=>{
 assert.equal(quote({senderUserId:me}).content,'已有草稿')
 assert.equal(quote({senderUserId:'gone'}).selectedUsers.length,0)
 assert.equal(quote({senderUserId:a.id},{users:[{...a,outside:true}]}).selectedUsers.length,0)
 const once=quote({senderUserId:a.id}),twice=quote({senderUserId:a.id},{...once})
 assert.equal(twice.content,'@甲 已有草稿');assert.equal(twice.selectedUsers.length,1)
 assert.match(quote({senderUserId:a.id},{selectedUsers:Array.from({length:20},(_,i)=>({id:`u${i}`,name:`U${i}`}))}).warning,/20/)
})
