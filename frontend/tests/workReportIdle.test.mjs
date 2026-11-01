import test from 'node:test'
import assert from 'node:assert/strict'
import {validIdleMinutes} from '../src/utils/workReportIdle.js'
test('空闲时间要求明确的整数分钟，零有效，空值和越界无效',()=>{
 for(const value of [0,30,1440])assert.equal(validIdleMinutes(value),true)
 for(const value of [null,undefined,'',false,'30',-1,1.5,1441,NaN])assert.equal(validIdleMinutes(value),false)
})
