import test from 'node:test'
import assert from 'node:assert/strict'
import {newInlineTalentForm,inlineTalentPayload,inlineTalentContactFields,inlineTalentMissingFields} from '../src/utils/talentInlineRegistration.js'
test('搜索姓名预填，支持四类名字和简历路径',()=>{
 let form=newInlineTalentForm(' 张三 ')
 assert.equal(form.chineseName,'张三')
 form.wechat='test-wechat'
 form.resumePath=' C:\\人才\\张三.docx '
 form.otherNamesText='三哥\n张先生'
 const payload=inlineTalentPayload(form,true)
 assert.equal(payload.fullName,'张三')
 assert.deepEqual(payload.otherNames,['三哥','张先生'])
 assert.equal(payload.resumePath,'C:\\人才\\张三.docx')
 assert.equal(newInlineTalentForm('Alice').englishName,'Alice')
})
test('十种联系方式与资源管理一致；无权限不提交联系方式',()=>{
 const form=newInlineTalentForm('Alice');form.resumePath='D:\\人才\\Alice.pdf'
 for(const field of inlineTalentContactFields)form[field.key]='private'
 assert.equal(inlineTalentContactFields.length,10)
 const allowed=inlineTalentPayload(form,true),hidden=inlineTalentPayload(form,false)
 for(const field of inlineTalentContactFields){assert.equal(allowed[field.key],'private');assert.equal(Object.hasOwn(hidden,field.key),false)}
 assert.throws(()=>inlineTalentPayload(newInlineTalentForm()),/至少填写/)
})

for(const group of ['name','contact','resume'])test(`登记新译员缺少${group}时拒绝保存`,()=>{
 const form=newInlineTalentForm('张三');form.primaryPhone='13800000000';form.resumePath='D:\\人才\\张三.pdf'
 if(group==='name')form.chineseName='  '
 if(group==='contact')form.primaryPhone='  '
 if(group==='resume')form.resumePath='  '
 assert.equal(inlineTalentMissingFields(form).length,1)
 assert.throws(()=>inlineTalentPayload(form,true),group==='name'?/姓名至少/:group==='contact'?/联系方式至少/:/简历路径/)
})
test('备用联系方式与其他名字也可满足各填一项',()=>{
 const form=newInlineTalentForm();form.otherNamesText='别名';form.otherContact='其他联络方式';form.resumePath='D:\\简历.pdf'
 assert.deepEqual(inlineTalentMissingFields(form),[]);assert.equal(inlineTalentPayload(form,true).fullName,'别名')
})
