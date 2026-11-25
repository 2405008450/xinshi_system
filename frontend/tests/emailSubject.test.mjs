import test from 'node:test'
import assert from 'node:assert/strict'
import {buildEmailSubject, notifyEmailSubjectGenerated, extractSubjectPrefix} from '../src/utils/emailSubject.js'

const source = {subjectPrefix:'优先处理',orderNo:'IP-261124-001',clientShortName:'客户',managerContact:'13800009999',customerOrderNo:'客户单号',projectName:'测试项目'}
test('口译主题可排除联系方式，同时保留前缀和客户标识',()=>{
  const result=buildEmailSubject(source,{includeManagerContact:false})
  assert.equal(result.subject,'优先处理，IP-261124-001，客户，客户单号，测试项目')
  assert.deepEqual(result.missingFields,[])
  assert.equal(extractSubjectPrefix(result.subject,{...source,subjectPrefix:''},{includeManagerContact:false}),'优先处理')
})
test('排除联系方式时，不要求填写联系方式；既有默认调用仍兼容',()=>{
  const {managerContact,...withoutContact}=source
  assert.deepEqual(buildEmailSubject(withoutContact,{includeManagerContact:false}).missingFields,[])
  assert.ok(buildEmailSubject(source).subject.includes(managerContact))
})
test('主题生成入口写入的预览也排除联系方式',()=>{
  const form={...source}
  const messages={success(){},warning(){}}
  assert.equal(notifyEmailSubjectGenerated(form,messages,{includeManagerContact:false}),true)
  assert.ok(!form.emailSubjectPreview.includes(source.managerContact))
})
