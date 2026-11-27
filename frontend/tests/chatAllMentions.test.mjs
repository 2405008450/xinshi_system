import test from 'node:test'
import assert from 'node:assert/strict'
import {mentionParts,mentionedDocument} from '../src/utils/chatMentions.js'
test('@所有人只对真实提及接收者高亮，普通文字不触发',()=>{
 const message={content:'@所有人 查看',metadata:{mentionAll:true},mentions:[{mentionedUserId:'member',mentionedUserName:'成员'}]}
 assert.equal(mentionParts(message,'member').some(part=>part.highlight&&part.text==='@所有人'),true)
 assert.equal(mentionParts(message,'outsider').some(part=>part.highlight),false)
 assert.equal(mentionParts({...message,mentions:[]},'member').some(part=>part.highlight),false)
 assert.equal(mentionedDocument(message,'member').content[0].content[0].marks[0].type,'highlight')
})

test('管理角色提及只给真实收件人高亮，普通文本不伪造提醒',()=>{
 const message={content:'@所有项目经理+客户经理 查看',mentions:[{mentionedUserId:'manager',mentionedUserName:'经理'}]}
 assert.ok(mentionParts(message,'manager').some(part=>part.highlight))
 assert.ok(!mentionParts(message,'outside').some(part=>part.highlight))
})
