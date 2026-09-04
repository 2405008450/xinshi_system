import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTranslatorAssignmentDetailUpdates,
  normalizeTranslatorAssignmentDetails,
  toNullablePrice,
} from '../src/utils/translatorAssignmentDetails.js'

test('译员价格兼容 Decimal 字符串、零值和空值', () => {
  assert.equal(toNullablePrice('0.1234'), 0.1234)
  assert.equal(toNullablePrice(0), 0)
  assert.equal(toNullablePrice(null), null)
  assert.equal(toNullablePrice(''), null)
  assert.equal(toNullablePrice('invalid'), null)
})

test('派稿译员数据同时兼容驼峰和下划线字段', () => {
  const normalized = normalizeTranslatorAssignmentDetails([
    {
      arrangementId: 'arrangement-1',
      translatorName: '陈彦嘉',
      translatorReturnTime: '2026-09-04T09:00:00',
      translatorUnitPrice: '0.1234',
      translatorTotalPrice: '100.00',
    },
    {
      arrangement_id: 'arrangement-2',
      translator_name: '测试译员',
      translator_unit_price: 0,
      translator_total_price: null,
    },
  ])

  assert.equal(normalized[0].translatorUnitPrice, 0.1234)
  assert.equal(normalized[0].translatorTotalPrice, 100)
  assert.equal(normalized[1].translatorUnitPrice, 0)
  assert.equal(normalized[1].translatorTotalPrice, null)
})

test('保存载荷保留零值、清空价格并整理完成情况', () => {
  const updates = buildTranslatorAssignmentDetailUpdates([{
    arrangementId: 'arrangement-1',
    completionRemarks: '  已完成  ',
    translatorUnitPrice: 0,
    translatorTotalPrice: '',
  }])

  assert.deepEqual(updates, [{
    arrangementId: 'arrangement-1',
    completionRemarks: '已完成',
    translatorUnitPrice: 0,
    translatorTotalPrice: null,
  }])
})
