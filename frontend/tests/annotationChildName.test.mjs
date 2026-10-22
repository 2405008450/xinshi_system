import test from 'node:test'
import assert from 'node:assert/strict'
import { annotationChildName } from '../src/utils/annotationChildName.js'

test('子订单名称使用单语种或实际语言方向', () => {
  assert.equal(annotationChildName('A', '英语'), '英语-A')
  assert.equal(annotationChildName('A', '中文', '英语'), '中文→英语-A')
  assert.equal(annotationChildName('A', '英语', '中文'), '英语→中文-A')
  assert.equal(annotationChildName('', '英语'), '')
})
