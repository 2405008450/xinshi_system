import test from 'node:test'
import assert from 'node:assert/strict'
import {selectCandidateRatio,pairedDuration,pairedProjectTypes} from '../src/utils/annotationPaired.js'
test('比例先按人才去重、排除已加入，再向上取整并稳定排序',()=>{
  const rows=[{id:'b',resource_code:'R2'},{id:'a',resource_code:'R1'},{id:'b',resource_code:'R2'},{id:'c',resource_code:'R3',joined:true}]
  assert.deepEqual(selectCandidateRatio(rows,10).map(item=>item.id),['a'])
  assert.deepEqual(selectCandidateRatio(rows,100).map(item=>item.id),['a','b'])
})
test('耗时保持时间差语义并允许人工调整',()=>{
  assert.equal(pairedDuration({actual_start:'2026-10-24T01:00:00Z',actual_end:'2026-10-24T10:00:00+08:00',duration_adjustment_minutes:-5}),55)
  assert.equal(pairedDuration({}),null)
})
test('纯采集和采标使用独立类型',()=>{
  assert.ok(pairedProjectTypes.some(item=>item.value==='paired_collection_annotation'))
  assert.ok(pairedProjectTypes.some(item=>item.value==='paired_audio_collection'))
})
