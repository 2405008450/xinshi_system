import test from 'node:test'
import assert from 'node:assert/strict'
import {applyTextFormat,formatText,formatRuns,rebaseTextFormat,runStyle,hasTextFormatting,documentFromRuns} from '../src/utils/chatTextFormat.js'
import {discussionMessagePayload} from '../src/utils/discussionMessagePayload.js'

test('普通文字、引用和截图不生成空格式字段，旧失败草稿重试也清除空格式',()=>{
 const content='@同事 [截图](screenshot://11111111-1111-4111-8111-111111111111?sig=test)'
 assert.equal(rebaseTextFormat(null,'',content),null)
 const plain=documentFromRuns([{text:content,marks:[]}])
 assert.equal(hasTextFormatting(plain),false)
 const result=discussionMessagePayload({content,contentJson:plain,clientMessageId:'same-id',replyToId:'123',mentionedUserIds:['colleague']})
 assert.equal(Object.hasOwn(result,'contentJson'),false)
 assert.equal(result.content,content)
 assert.equal(result.clientMessageId,'same-id')
 assert.equal(result.replyToId,'123')
 assert.deepEqual(result.mentionedUserIds,['colleague'])
 const formatted=applyTextFormat(content,null,0,3,'bold')
 assert.deepEqual(discussionMessagePayload({content,contentJson:formatted}).contentJson,formatted)
})
test('文字颜色、高亮与下划线颜色可独立叠加，清除不改变正文',()=>{
 let doc=applyTextFormat('测试文字',null,0,2,'textColor','#dc2626')
 doc=applyTextFormat('测试文字',doc,0,4,'underline','#2563eb')
 doc=applyTextFormat('测试文字',doc,1,3,'highlight','#dbeafe')
 assert.equal(formatText(doc),'测试文字')
 assert.ok(formatRuns(doc).some(r=>r.marks.length===3))
 assert.equal(runStyle(formatRuns(doc)[1].marks).textDecorationColor,'#2563eb')
 const clear=applyTextFormat('测试文字',doc,0,4,'clear')
 assert.ok(formatRuns(clear).every(r=>!r.marks.length))
})
test('文字编辑与插入提及时格式范围正确移动，删除后无残留',()=>{
 const doc=applyTextFormat('前重点后',null,1,3,'bold')
 const changed=rebaseTextFormat(doc,'前重点后','@所有人 前重点后')
 assert.equal(formatText(changed),'@所有人 前重点后')
 assert.equal(formatRuns(changed).filter(r=>r.marks.length).map(r=>r.text).join(''),'重点')
 assert.equal(rebaseTextFormat(changed,'@所有人 前重点后',''),null)
 assert.deepEqual(runStyle([{type:'textColor',attrs:{color:'url(bad)'}}]),{})
})
