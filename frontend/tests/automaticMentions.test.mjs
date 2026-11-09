import test from 'node:test'
import assert from 'node:assert/strict'
import {undisplayedMentions} from '../src/utils/chatMentions.js'
test('自动项目消息展示真实提及，正文不变，当前用户高亮',()=>{
 const message={content:'项目通知',mentions:[{mentionedUserId:'a',mentionedUserName:'少妃'},{mentioned_user_id:'b',mentioned_user_name:'Thomas'}]}
 assert.deepEqual(undisplayedMentions(message,'a').map(item=>[item.label,item.highlight]),[['@少妃',true],['@Thomas',false]])
 assert.equal(message.content,'项目通知')
})
test('手工 @ 不重复展示；无关系不伪造提醒；全体仅显示一次；撤回不显示',()=>{
 assert.equal(undisplayedMentions({content:'@少妃 请查看',mentions:[{mentionedUserId:'a',mentionedUserName:'少妃'}]},'a').length,0)
 assert.equal(undisplayedMentions({content:'@少妃 项目通知'},'a').length,0)
 const message={content:'项目通知',mentions:[{mentionedUserId:'a',isAll:true},{mentionedUserId:'b',isAll:true}]}
 assert.deepEqual(undisplayedMentions(message,'a'),[{id:'all',label:'@所有人',highlight:true}])
 assert.equal(undisplayedMentions({...message,recalledAt:'2026-11-09T12:00:00+08:00'},'a').length,0)
})
