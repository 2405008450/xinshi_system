import test from 'node:test'
import assert from 'node:assert/strict'
import {revenueChange,normalizedRange,rankShortcuts,amountShortcuts} from '../src/utils/revenueStatistics.js'

test('营收变化处理零基期和无对应周期',()=>{
  assert.equal(revenueChange({state:'new',rate:null}),'基期为0')
  assert.equal(revenueChange({state:'zero',rate:null}),'无变化')
  assert.equal(revenueChange({state:'normal',rate:'-100'}),'-100.00%')
  assert.equal(revenueChange({state:'unavailable'}),'无可比周期')
})
test('区间倒序归一、零金额保留并覆盖指定快捷区间',()=>{
  assert.deepEqual(normalizedRange(10000,5000),[5000,10000])
  assert.deepEqual(normalizedRange(0,null),[0,undefined])
  assert.deepEqual(rankShortcuts.map(item=>[item.min,item.max]),[[1,10],[20,50]])
  assert.equal(amountShortcuts.length,7)
  assert.deepEqual(amountShortcuts.find(item=>item.label==='10000–5000'),{label:'10000–5000',min:5000,max:10000})
})
