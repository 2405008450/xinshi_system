import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_TRANSLATION_PROJECT_SORT,
  TRANSLATION_PROJECT_TIME_SORT_MODES,
  getTranslationProjectTimeSortTitle,
  isTranslationProjectTimeSortActive,
  nextTranslationProjectTimeSortMode,
} from '../src/utils/translationProjectTimeSort.js'

test('两个时间列使用既有紧急优先排序参数', () => {
  assert.deepEqual(TRANSLATION_PROJECT_TIME_SORT_MODES, {
    customerDeadlineTime: 'customer_deadline_time_asc',
    translatorReturnTime: 'translator_return_time_asc',
  })
})

test('时间排序为互斥两态并可恢复默认排序', () => {
  const customerSort = nextTranslationProjectTimeSortMode(
    DEFAULT_TRANSLATION_PROJECT_SORT,
    'customerDeadlineTime',
  )
  assert.equal(customerSort, 'customer_deadline_time_asc')

  const translatorSort = nextTranslationProjectTimeSortMode(
    customerSort,
    'translatorReturnTime',
  )
  assert.equal(translatorSort, 'translator_return_time_asc')
  assert.equal(isTranslationProjectTimeSortActive(translatorSort, 'customerDeadlineTime'), false)
  assert.equal(isTranslationProjectTimeSortActive(translatorSort, 'translatorReturnTime'), true)
  assert.equal(
    nextTranslationProjectTimeSortMode(translatorSort, 'translatorReturnTime'),
    DEFAULT_TRANSLATION_PROJECT_SORT,
  )
})

test('排序按钮文案区分待交稿、待回稿和恢复默认', () => {
  assert.equal(
    getTranslationProjectTimeSortTitle(
      DEFAULT_TRANSLATION_PROJECT_SORT,
      'customerDeadlineTime',
      '客户交稿时间',
    ),
    '客户交稿时间：待交稿紧急优先',
  )
  assert.equal(
    getTranslationProjectTimeSortTitle(
      DEFAULT_TRANSLATION_PROJECT_SORT,
      'translatorReturnTime',
      '译员回稿时间',
    ),
    '译员回稿时间：待回稿紧急优先',
  )
  assert.equal(
    getTranslationProjectTimeSortTitle(
      'translator_return_time_asc',
      'translatorReturnTime',
      '译员回稿时间',
    ),
    '译员回稿时间：恢复默认排序',
  )
})
