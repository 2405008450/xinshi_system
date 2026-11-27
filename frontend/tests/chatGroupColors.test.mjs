import test from 'node:test'
import assert from 'node:assert/strict'
import {chatGroupPalette,chatGroupStyle} from '../src/utils/chatGroupColors.js'
test('技术需求优先使用浅橙色，不随所属标注项目变绿',()=>{
 assert.equal(chatGroupPalette({title:'技术需求 · 标注项目',projectModule:'annotation'}).accent,'#edb57b')
 assert.equal(chatGroupPalette({title:'技术/开发沟通',kind:'discussion'}).soft,'#fff4e8')
})
test('项目类型与资源分组使用确认的对应识别色',()=>{
 assert.equal(chatGroupPalette({projectType:'translation'}).accent,'#91b9dd')
 assert.equal(chatGroupPalette({title:'资源开拓与讨论'}).accent,'#88beb6')
 assert.notEqual(chatGroupPalette({projectType:'interpretation'}).accent,chatGroupPalette({projectType:'translation'}).accent)
})
test('讨论室继承文件夹颜色，循环父级不会卡住',()=>{
 const nodes=[{id:'root',name:'资源开拓与讨论'},{id:'date',parentKey:'root'},{id:'room',parentKey:'date'}]
 assert.equal(chatGroupStyle({projectId:'room'},nodes)['--chat-group-accent'],'#88beb6')
 assert.ok(chatGroupPalette({projectId:'a'},[{id:'a',parentKey:'b'},{id:'b',parentKey:'a'}]).accent)
})
