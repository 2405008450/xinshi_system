import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { TALENT_RESOURCE_VIEWS } from '../src/config/talentResourceViews.js'
import {
  calculateTalentColumnTotals,
  calculateTalentGrandTotal,
  calculateTalentRowTotal,
  formatTalentCount,
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
