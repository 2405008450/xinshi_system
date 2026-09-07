import assert from 'node:assert/strict'
import test from 'node:test'

import {
  defaultProgressSearchRange,
  isProgressSearchRangeValid,
  splitKeywordMatches,
} from '../src/utils/annotationProgressSearch.js'

test('默认检索范围为最近三个月', () => {
  assert.deepEqual(
    defaultProgressSearchRange(new Date(2026, 8, 7, 12, 0, 0)),
    ['2026-06-07', '2026-09-07'],
  )
  assert.deepEqual(
    defaultProgressSearchRange(new Date(2026, 4, 31, 12, 0, 0)),
    ['2026-02-28', '2026-05-31'],
  )
})

test('时间范围最多允许 366 个自然日', () => {
  assert.equal(isProgressSearchRangeValid(['2025-09-08', '2026-09-07']), true)
  assert.equal(isProgressSearchRangeValid(['2025-09-06', '2026-09-07']), false)
  assert.equal(isProgressSearchRangeValid(['2026-09-08', '2026-09-07']), false)
  assert.equal(isProgressSearchRangeValid([]), false)
})

test('关键词高亮保留原文并支持多处和大小写匹配', () => {
  assert.deepEqual(splitKeywordMatches('Alpha 客户 alpha', 'ALPHA'), [
    { text: 'Alpha', matched: true },
    { text: ' 客户 ', matched: false },
    { text: 'alpha', matched: true },
  ])
  assert.deepEqual(splitKeywordMatches('完成 50%_待确认', '50%_'), [
    { text: '完成 ', matched: false },
    { text: '50%_', matched: true },
    { text: '待确认', matched: false },
  ])
})
