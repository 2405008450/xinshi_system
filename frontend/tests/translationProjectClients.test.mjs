import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { getTranslationClientDetailItems } from '../src/utils/translationClientLabels.js'

const pagePath = fileURLToPath(new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url))
const page = readFileSync(pagePath, 'utf8')

test('笔译项目表单分别绑定母客户和可选子客户', () => {
  assert.match(page, /label="母客户简称"[\s\S]*v-model="form\.clientShortName"/)
  assert.match(page, /label="子客户"[\s\S]*v-model="form\.subClientShortName"/)
  assert.match(page, /:disabled="!form\.clientShortName"/)
  assert.match(page, /@select="handleSubClientSelect"/)
  assert.match(page, /@input="handleSubClientInput"/)
  assert.match(page, /保存项目会在当前母客户下自动新增/)
  assert.match(page, /const clearSubClientSelection = \(\) =>/)
  assert.match(page, /const requestId = \+\+subClientRequestId/)
})

test('子客户仅更新独立展示字段，不参与项目名称生成', () => {
  const handler = page.match(/const handleSubClientSelect = \(selected\) => \{([\s\S]*?)\n\}/)?.[1] || ''
  assert.match(handler, /form\.subClientShortName/)
  assert.match(handler, /form\.subClientCode/)
  assert.doesNotMatch(handler, /projectName|syncProjectName|emailSubjectPreview/)
  assert.doesNotMatch(page, /buildAutoProjectName|syncProjectName/)
})

test('列表详情和筛选均提供独立母子客户字段', () => {
  assert.match(page, /label: '客户全称', key: 'clientName'/)
  assert.match(page, /label: '子客户全称', key: 'subClientName'/)
  assert.match(page, /key: 'subClientShortName', label: '子客户简称', type: 'text'/)
  assert.match(page, /key: 'subClientCode', label: '子客户编号', type: 'text'/)
  assert.match(page, /:items="getTranslationClientDetailItems\(projectDetailItems, row\)"/)
  const filters = page.slice(page.indexOf('const translationFilterFields = ['), page.indexOf('Object.assign(searchForm'))
  assert.doesNotMatch(filters, /母客户/)
})

const clientItems = [
  { key: 'clientName', label: '客户全称' },
  { key: 'clientShortName', label: '客户简称' },
  { key: 'clientCode', label: '客户编号' },
  { key: 'clientManager', label: '客户经理' },
  { key: 'managerContact', label: '客户经理联系方式' },
  { key: 'subClientShortName', label: '子客户简称' },
  { key: 'sourceFileName', label: '项目名称', editable: true, maxlength: 255 },
]

test('没有子客户简称时，客户字段均不带母字', () => {
  for (const row of [undefined, {}, { subClientShortName: null }, { subClientShortName: '' }, { subClientShortName: '  ' }]) {
    const items = getTranslationClientDetailItems(clientItems, row)
    assert.deepEqual(items.map((item) => item.label), clientItems.map((item) => item.label))
  }
})

test('存在子客户简称时，仅在详情中区分母客户，不修改字段及编辑配置', () => {
  const before = structuredClone(clientItems)
  const items = getTranslationClientDetailItems(clientItems, { subClientShortName: ' 分公司 ' })
  assert.deepEqual(items.map((item) => item.label), [
    '母客户全称', '母客户简称', '母客户编号', '母客户经理', '母客户经理联系方式', '子客户简称', '项目名称',
  ])
  assert.deepEqual(items.map((item) => item.key), clientItems.map((item) => item.key))
  assert.deepEqual(items[6], clientItems[6])
  assert.deepEqual(clientItems, before)
})
