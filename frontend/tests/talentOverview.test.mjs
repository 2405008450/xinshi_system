import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { TALENT_RESOURCE_VIEWS } from '../src/config/talentResourceViews.js'
import {
  appendTalentOverviewColumn,
  appendTalentOverviewRow,
  calculateTalentColumnTotals,
  calculateTalentGrandTotal,
  calculateTalentRowTotal,
  filterTalentOverviewRows,
  formatTalentCount,
  TALENT_OVERVIEW_BLANK_FILTER_VALUE,
} from '../src/utils/talentOverview.js'

const overviewData = JSON.parse(readFileSync(
  new URL('../../data/talent_overview.json', import.meta.url),
  'utf8',
))
const TALENT_OVERVIEW_COLUMNS = overviewData.columns
const TALENT_OVERVIEW_ROWS = overviewData.rows

test('人才概览保留 132 行和 14 个来源列，并规范明确的简称', () => {
  assert.equal(TALENT_OVERVIEW_ROWS.length, 132)
  assert.equal(TALENT_OVERVIEW_COLUMNS.length, 14)
  assert.equal(new Set(TALENT_OVERVIEW_ROWS.map(row => row.language)).size, 132)
  assert.ok(TALENT_OVERVIEW_ROWS.some(row => row.language === '阿拉伯语'))
  assert.ok(TALENT_OVERVIEW_ROWS.some(row => row.language === '中文（繁体·台湾）'))
  assert.ok(TALENT_OVERVIEW_ROWS.some(row => row.language === '班巴拉语'))
  assert.ok(TALENT_OVERVIEW_ROWS.some(row => row.language === '达里语'))
  const zulu = TALENT_OVERVIEW_ROWS.find(row => row.overview_key === 'lang-zu')
  const afrikaans = TALENT_OVERVIEW_ROWS.find(row => row.overview_key === 'lang-af')
  assert.ok(zulu.aliases.includes('南非zulu语'))
  assert.ok(afrikaans.aliases.includes('afrikaans'))
})

test('人才概览列合计和总计与源表一致', () => {
  const totals = calculateTalentColumnTotals(TALENT_OVERVIEW_ROWS)
  assert.deepEqual(
    TALENT_OVERVIEW_COLUMNS.map(column => totals[column.key]),
    [8657, 8972, 10215, 1164, 2853, 2288, 2083, 172, 4612, 513, 75, 0, 79, 764],
  )
  assert.equal(calculateTalentGrandTotal(TALENT_OVERVIEW_ROWS), 42447)
})

test('人才概览代表行合计准确，空白和零保持不同显示', () => {
  const expected = new Map([
    ['英语', 9596],
    ['粤语', 1501],
    ['未知语种', 5146],
    ['客家话', 311],
    ['西南官话', 1],
  ])
  expected.forEach((total, language) => {
    const row = TALENT_OVERVIEW_ROWS.find(item => item.language === language)
    assert.equal(calculateTalentRowTotal(row), total)
  })
  assert.equal(formatTalentCount(null), '')
  assert.equal(formatTalentCount(0), '0')
})

test('人才资源导航把人才概览放在人才总库左侧', () => {
  assert.deepEqual(
    TALENT_RESOURCE_VIEWS.map(item => item.label),
    ['人才概览', '人才总库', '笔译资源', '口译资源', '标注员', '招聘人才库'],
  )
  assert.equal(TALENT_RESOURCE_VIEWS[0].path, '/resource-management/talent-overview')
})

test('新增来源列追加到所属分组末尾并为已有行补充空单元格', () => {
  const columns = [
    { key: 'sheetA', group: 'sheet' },
    { key: 'wecomA', group: 'wecom' },
  ]
  const rows = [{ overviewKey: 'row-a', counts: { sheetA: 1, wecomA: 0 } }]
  const result = appendTalentOverviewColumn(columns, rows, {
    key: 'sheetB', label: '资料表 B', group: 'sheet', width: 120,
  })

  assert.deepEqual(result.columns.map(item => item.key), ['sheetA', 'sheetB', 'wecomA'])
  assert.equal(result.rows[0].counts.sheetB, null)
  assert.equal(rows[0].counts.sheetB, undefined)
})

test('新增语种行包含全部来源列且默认值为空', () => {
  const rows = appendTalentOverviewRow([], [{ key: 'a' }, { key: 'b' }], {
    overviewKey: 'row-new', language: '', updatedAt: '2026-09-20',
  })
  assert.deepEqual(rows[0].counts, { a: null, b: null })
})

test('人才概览页面提供权限编辑、增行增列、整表保存和全屏交互', () => {
  const page = readFileSync(new URL('../src/views/resource/TalentOverview.vue', import.meta.url), 'utf8')
  const api = readFileSync(new URL('../src/api/talents.js', import.meta.url), 'utf8')

  assert.match(page, /hasPermission\(\['talents:write', 'translators:write'\]\)/)
  assert.match(page, /新增列/)
  assert.match(page, /新增行/)
  assert.match(page, /<el-button :icon="Plus" @click="addRow">新增行<\/el-button>/)
  assert.match(page, /overviewTableRef\.value\?\.setScrollTop\?\.\(Number\.MAX_SAFE_INTEGER\)/)
  assert.match(page, /requestFullscreen\(\)/)
  assert.match(page, /document\.exitFullscreen\(\)/)
  assert.match(api, /api\.put\('\/talents\/overview'/)
  assert.match(api, /counts: Object\.fromEntries/)
})

test('人才概览表头筛选支持同字段多选、跨字段组合及空白值', () => {
  const columns = [{ key: 'sourceA' }, { key: 'sourceB' }]
  const rows = [
    { language: '英语', updatedAt: '2026-09-20', counts: { sourceA: 1, sourceB: 2 } },
    { language: '粤语', updatedAt: null, counts: { sourceA: 1, sourceB: null } },
    { language: '日语', updatedAt: '2026-09-20', counts: { sourceA: 3, sourceB: 2 } },
  ]

  assert.deepEqual(
    filterTalentOverviewRows(rows, columns, { language: ['英语', '粤语'] }).map(row => row.language),
    ['英语', '粤语'],
  )
  assert.deepEqual(
    filterTalentOverviewRows(rows, columns, {
      language: ['英语', '粤语'],
      counts: { sourceB: [2] },
    }).map(row => row.language),
    ['英语'],
  )
  assert.deepEqual(
    filterTalentOverviewRows(rows, columns, {
      updatedAt: [TALENT_OVERVIEW_BLANK_FILTER_VALUE],
      counts: { sourceB: [TALENT_OVERVIEW_BLANK_FILTER_VALUE] },
    }).map(row => row.language),
    ['粤语'],
  )
})

test('人才概览复用公共多选漏斗筛选组件并让汇总跟随筛选结果', () => {
  const page = readFileSync(new URL('../src/views/resource/TalentOverview.vue', import.meta.url), 'utf8')

  assert.match(page, /ConfiguredColumnHeaderFilter/)
  assert.match(page, /v-model="filterValues\.language"/)
  assert.match(page, /filterValues\.counts\[column\.key\]/)
  assert.match(page, /v-model="filterValues\.rowTotal"/)
  assert.match(page, /calculateTalentColumnTotals\(filteredRows\.value/)
})
