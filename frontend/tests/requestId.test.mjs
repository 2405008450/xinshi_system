import test from 'node:test'
import assert from 'node:assert/strict'
import {createRequestId,ensureRequestId,isRequestId} from '../src/utils/requestId.js'
import {normalizeApiError,getLocalizedErrorMessage} from '../src/utils/errorMessages.js'

test('现代、旧版及无 Web Crypto 浏览器均生成标准 UUID',()=>{
  const native='12345678-1234-4234-8234-123456789abc'
  assert.equal(createRequestId({randomUUID:()=>native}),native)
  for(const cryptoApi of [null,{}, {getRandomValues:bytes=>bytes.fill(37)}, {randomUUID:()=>{throw Error('unsupported')}}, {randomUUID:()=>'',getRandomValues:()=>{throw Error('blocked')}}]){
    const ids=Array.from({length:100},()=>createRequestId(cryptoApi))
    assert.ok(ids.every(isRequestId))
    if(!cryptoApi?.getRandomValues) assert.equal(new Set(ids).size,100)
  }
  assert.equal(ensureRequestId(native),native)
  assert.ok(isRequestId(ensureRequestId('')))
})

test('考勤去重标识提示可执行的恢复方法，客户接口保留客户语义',()=>{
  const detail=[{loc:['body','client_id'],type:'uuid_parsing',msg:'标识格式不正确'}]
  for(const url of ['/attendance/leave','/api/attendance/delay-start','/attendance/comp-time','/attendance/clock-corrections']){
    const error={config:{url},response:{status:422,data:{detail}}}
    const message=normalizeApiError(error).detail
    assert.equal(message,'申请提交校验失败，请保留填写内容并刷新页面后重试')
    assert.equal(getLocalizedErrorMessage(error),message)
  }
  assert.equal(getLocalizedErrorMessage({config:{url:'/projects'},response:{status:422,data:{detail}}}),'客户：标识格式不正确')
})
