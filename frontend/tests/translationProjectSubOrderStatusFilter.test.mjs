import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { filterTranslationSubOrdersByStatus } from '../src/utils/projectStatus.js'

const projectDetailsPath = fileURLToPath(
  new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url),
)
const projectDetailsSource = readFileSync(projectDetailsPath, 'utf8')

const subOrders = [
  { id: 'confirmed', status: 'confirmed' },
  { id: 'sent', status: 'sent_to_translator' },
  { id: 'returned', status: 'translator_returned' },
  { id: 'legacy-progress', status: 'in_progress' },
]

test('未选择状态时保留全部子订单', () => {
  assert.deepEqual(filterTranslationSubOrdersByStatus(subOrders, []), subOrders)
  assert.deepEqual(filterTranslationSubOrdersByStatus(subOrders, ''), subOrders)
})

test('单个状态仅保留状态命中的子订单', () => {
  assert.deepEqual(
    filterTranslationSubOrdersByStatus(subOrders, 'sent_to_translator').map((item) => item.id),
    ['sent'],
  )
})

test('多个状态按任一命中规则过滤子订单', () => {
  assert.deepEqual(
    filterTranslationSubOrdersByStatus(
      subOrders,
      ['sent_to_translator', 'translator_returned'],
    ).map((item) => item.id),
    ['sent', 'returned'],
  )
})

test('筛选值和子订单状态均兼容历史状态别名', () => {
  assert.deepEqual(
    filterTranslationSubOrdersByStatus(subOrders, ['confirmed']).map((item) => item.id),
    ['confirmed', 'legacy-progress'],
  )
  assert.deepEqual(
    filterTranslationSubOrdersByStatus(subOrders, ['in_progress']).map((item) => item.id),
    ['confirmed', 'legacy-progress'],
  )
})

test('没有命中项或子订单数据异常时返回空列表', () => {
  assert.deepEqual(filterTranslationSubOrdersByStatus(subOrders, ['paused']), [])
  assert.deepEqual(filterTranslationSubOrdersByStatus(null, ['confirmed']), [])
})

test('笔译项目列表以状态命中集合统一驱动展开、数量和预览数据', () => {
  assert.match(
    projectDetailsSource,
    /const getSubOrderCount = \(row\) => getFilteredSubOrders\(row\)\.length/,
  )
  assert.match(projectDetailsSource, /v-if="getSubOrderCount\(row\)"/)
  assert.match(
    projectDetailsSource,
    /匹配 \{\{ getSubOrderCount\(row\) \}\} \/ 共 \{\{ getTotalSubOrderCount\(row\) \}\} 条/,
  )
  assert.match(
    projectDetailsSource,
    /\[\.\.\.getFilteredSubOrders\(row\)\][\s\S]*?\.slice\(0, SUB_ORDER_PREVIEW_LIMIT\)/,
  )
})

test('状态筛选查询及翻页后自动展开存在命中子订单的母订单', () => {
  assert.match(
    projectDetailsSource,
    /const handleSearch = \(\) => \{[\s\S]*?fetchData\(\{ expandSubOrders: hasSubOrderListFilter\(\) \}\)[\s\S]*?\}/,
  )
  assert.match(
    projectDetailsSource,
    /const applyPagination = \(\) => \{[\s\S]*?fetchData\(\{ expandSubOrders: hasSubOrderListFilter\(\) \}\)[\s\S]*?\}/,
  )
  assert.match(
    projectDetailsSource,
    /if \(expandSubOrders\) \{\s*expandedProjectIds\.value = expandableProjectIds/,
  )
})

test('子订单状态列位于子项目名称和翻译方向之间以对齐母订单状态列', () => {
  const subProjectNameColumn = projectDetailsSource.indexOf(
    `isSubOrderColumnVisible('subProjectName')`,
  )
  const statusColumn = projectDetailsSource.indexOf(
    `isSubOrderColumnVisible('status')`,
    subProjectNameColumn,
  )
  const languagePairColumn = projectDetailsSource.indexOf(
    `isSubOrderColumnVisible('languagePair')`,
    statusColumn,
  )

  assert.ok(subProjectNameColumn >= 0)
  assert.ok(statusColumn > subProjectNameColumn)
  assert.ok(languagePairColumn > statusColumn)
})

test('译员回稿时间排序启用时过滤没有有效回稿时间的子订单', () => {
  assert.match(
    projectDetailsSource,
    /const hasTranslatorReturnSubOrderFilter = \(\) => \([\s\S]*?TRANSLATION_PROJECT_TIME_SORT_MODES\.translatorReturnTime[\s\S]*?\)/,
  )
  assert.match(
    projectDetailsSource,
    /hasSubOrderStatusFilter\(\) \|\| hasTranslatorReturnSubOrderFilter\(\)/,
  )
  assert.match(
    projectDetailsSource,
    /hasTranslatorReturnSubOrderFilter\(\)[\s\S]*?statusMatched\.filter\(hasTranslationSubOrderReturnTime\)/,
  )
  assert.match(projectDetailsSource, /v-if="hasSubOrderListFilter\(\)"/)
})
