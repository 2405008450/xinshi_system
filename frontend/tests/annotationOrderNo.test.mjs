import test from 'node:test'
import assert from 'node:assert/strict'

import {
  isValidAnnotationOrderNo,
  normalizeAnnotationOrderNo,
} from '../src/utils/annotationOrderNo.js'

test('标注订单号去除首尾空格并转为大写', () => {
  assert.equal(normalizeAnnotationOrderNo('  ap-old_2024.001  '), 'AP-OLD_2024.001')
})

test('标注订单号仅接受 AP 前缀和约定字符', () => {
  assert.equal(isValidAnnotationOrderNo('AP-260904-001'), true)
  assert.equal(isValidAnnotationOrderNo('ap-old_2024.001'), true)
  assert.equal(isValidAnnotationOrderNo('TP-260904-001'), false)
  assert.equal(isValidAnnotationOrderNo('AP-中文'), false)
  assert.equal(isValidAnnotationOrderNo('AP-WITH SPACE'), false)
  assert.equal(isValidAnnotationOrderNo(`AP-${'A'.repeat(48)}`), false)
})
