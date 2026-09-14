import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import {
  DEFAULT_TRANSLATION_EXPORT_TIME_FIELD,
  TRANSLATION_EXPORT_TYPES,
  buildTranslationExportFilename,
  buildTranslationExportParams,
} from '../src/utils/translationProjectExport.js'


test('导出参数继承现有筛选并覆盖同一时间口径', () => {
  const params = buildTranslationExportParams({
    keyword: 'TP-260901',
    field_filters: JSON.stringify({
      project_status: { op: 'in', value: ['confirmed'] },
      customer_reception_time: { op: 'between', from: '2026-08-01', to: '2026-08-31' },
      customer_deadline_time: { op: 'between', from: '2026-09-15', to: '2026-09-30' },
    }),
  }, {
    timeField: DEFAULT_TRANSLATION_EXPORT_TIME_FIELD,
    dateRange: ['2026-09-01', '2026-09-10'],
  }, 'unfinished_first_order_no_desc')

  const filters = JSON.parse(params.field_filters)
  assert.deepEqual(filters.project_status.value, ['confirmed'])
  assert.deepEqual(filters.customer_reception_time, {
    op: 'between', from: '2026-09-01', to: '2026-09-10',
  })
  assert.deepEqual(filters.customer_deadline_time, {
    op: 'between', from: '2026-09-15', to: '2026-09-30',
  })
  assert.equal(params.keyword, 'TP-260901')
  assert.equal(params.sort, 'unfinished_first_order_no_desc')
})


test('导出文件名包含时间口径和日期范围', () => {
  assert.equal(
    buildTranslationExportFilename('created_at', ['2026-09-01', '2026-09-30']),
    '笔译项目导出_创建时间_2026-09-01_至_2026-09-30.xlsx',
  )
  assert.equal(
    buildTranslationExportFilename(
      'customer_reception_time',
      ['2026-09-01', '2026-09-30'],
      TRANSLATION_EXPORT_TYPES.RECONCILIATION,
    ),
    '笔译项目对账单_客户接单时间_2026-09-01_至_2026-09-30.xlsx',
  )
  assert.equal(
    buildTranslationExportFilename(
      'customer_deadline_time',
      ['2026-09-01', '2026-09-30'],
      TRANSLATION_EXPORT_TYPES.TRANSLATOR_RECONCILIATION,
    ),
    '笔译项目译员对账单_客户交稿时间_2026-09-01_至_2026-09-30.xlsx',
  )
})


test('笔译项目页通过统一入口提供三种导出选项', () => {
  const page = fs.readFileSync(
    new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url),
    'utf8',
  )
  const api = fs.readFileSync(new URL('../src/api/projects.js', import.meta.url), 'utf8')

  assert.match(page, /<el-dropdown[\s\S]*?@command="openExportDialog"/)
  assert.match(page, /<el-dropdown-item command="projects">导出项目 Excel<\/el-dropdown-item>/)
  assert.match(page, /<el-dropdown-item command="reconciliation">导出客户对账单<\/el-dropdown-item>/)
  assert.match(page, /<el-dropdown-item command="translator_reconciliation">导出译员对账单<\/el-dropdown-item>/)
  assert.match(page, /TRANSLATOR_RECONCILIATION/)
  assert.match(page, /exportTranslationTranslatorReconciliation/)
  assert.match(api, /\/projects\/translation\/translator-reconciliation-export/)
})
