import test from 'node:test'
import assert from 'node:assert/strict'
import {quickRegistrationPayload,newQuickRegistrationRow} from '../src/utils/talentQuickRegister.js'
import {resolveIdempotencyKey} from '../src/utils/idempotency.js'

test('快速登记仅提交已选择字段，隐藏姓名与联系方式不泄漏',()=>{
  const payload=quickRegistrationPayload({nameKinds:['englishName','otherName'],contactKinds:['primaryEmail'],englishName:' Alice ',otherName:' Ali ',primaryEmail:' a@example.com ',wechat:'隐藏内容',chineseName:'隐藏姓名',punctualityLevel:'high'})
  assert.deepEqual(payload,{fullName:'Alice',capabilities:[],allowDuplicate:false,englishName:'Alice',otherNames:['Ali'],primaryEmail:'a@example.com',punctualityLevel:'high',cooperationLevel:null})
})
test('限制姓名与联系方式为一到两种，已选择但未填值不允许提交',()=>{
  const form={nameKinds:['nickname'],contactKinds:['wechat'],nickname:'小王',wechat:'wx123'}
  assert.equal(quickRegistrationPayload(form,true).allowDuplicate,true)
  for(const patch of [{nameKinds:[]},{contactKinds:[]},{nameKinds:['nickname','otherName','englishName']},{contactKinds:['wechat','primaryEmail','line']},{wechat:' '}])assert.throws(()=>quickRegistrationPayload({...form,...patch}))
})
test('批量行内容与幂等状态独立，失败行重试沿用原请求键',()=>{
  const first=newQuickRegistrationRow(),second=newQuickRegistrationRow()
  assert.notEqual(first._key,second._key)
  assert.notEqual(first._createState,second._createState)
  first.chineseName='张三';first.wechat='wx1'
  assert.equal(second.chineseName,'')
  const payload=quickRegistrationPayload({...first,nameKinds:['chineseName'],contactKinds:['wechat']})
  const key=resolveIdempotencyKey(first._createState,payload)
  resolveIdempotencyKey(second._createState,{...payload,fullName:'李四'})
  assert.equal(resolveIdempotencyKey(first._createState,payload),key)
  assert.notEqual(resolveIdempotencyKey(first._createState,{...payload,wechat:'wx2'}),key)
  assert.equal(Object.hasOwn(payload,'_key'),false)
})
