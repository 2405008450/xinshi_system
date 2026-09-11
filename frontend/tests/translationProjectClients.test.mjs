import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

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
  assert.match(page, /buildAutoProjectName\(\s*form\.clientShortName/)
})

test('列表详情和筛选均提供独立母子客户字段', () => {
  assert.match(page, /label: '母客户全称', key: 'clientName'/)
  assert.match(page, /label: '子客户全称', key: 'subClientName'/)
  assert.match(page, /key: 'subClientShortName', label: '子客户简称', type: 'text'/)
  assert.match(page, /key: 'subClientCode', label: '子客户编号', type: 'text'/)
})
