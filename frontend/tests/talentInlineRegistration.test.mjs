import test from 'node:test'
import assert from 'node:assert/strict'
import {newInlineTalentForm,inlineTalentPayload,inlineTalentContactFields} from '../src/utils/talentInlineRegistration.js'
test('搜索姓名预填，支持四类名字和简历路径',()=>{
 let form=newInlineTalentForm(' 张三 ')
 assert.equal(form.chineseName,'张三')
 form.resumePath=' C:\\人才\\张三.docx '
 form.otherNamesText='三哥\n张先生'
 const payload=inlineTalentPayload(form,true)
 assert.equal(payload.fullName,'张三')
 assert.deepEqual(payload.otherNames,['三哥','张先生'])
 assert.equal(payload.resumePath,'C:\\人才\\张三.docx')
 assert.equal(newInlineTalentForm('Alice').englishName,'Alice')
})
test('十种联系方式与资源管理一致；无权限不提交联系方式',()=>{
 const form=newInlineTalentForm('Alice')
 for(const field of inlineTalentContactFields)form[field.key]='private'
 assert.equal(inlineTalentContactFields.length,10)
 const allowed=inlineTalentPayload(form,true),hidden=inlineTalentPayload(form,false)
 for(const field of inlineTalentContactFields){assert.equal(allowed[field.key],'private');assert.equal(Object.hasOwn(hidden,field.key),false)}
 assert.throws(()=>inlineTalentPayload(newInlineTalentForm()),/至少填写/)
})
