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
