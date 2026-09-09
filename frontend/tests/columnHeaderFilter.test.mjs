import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const annotationSource = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const configuredFilter = readFileSync(new URL('../src/components/common/ConfiguredColumnHeaderFilter.vue', import.meta.url), 'utf8')
const columnFilter = readFileSync(new URL('../src/components/common/ColumnHeaderFilter.vue', import.meta.url), 'utf8')
const agentGuidelines = readFileSync(new URL('../AGENTS.md', import.meta.url), 'utf8')

test('可多选的表头漏斗筛选统一使用暂存值并确认后提交', () => {
  assert.match(configuredFilter, /definition\.type === 'select' && props\.definition\.multiple !== false/)
  assert.match(configuredFilter, /v-model="draftValue"/)
  assert.match(configuredFilter, /@click="selectAll"/)
  assert.match(configuredFilter, /@click="cancel"/)
  assert.match(configuredFilter, /@click="confirm"/)
  assert.match(configuredFilter, /emit\('change', next\)/)
  assert.match(configuredFilter, /resolvedOptions\.length > 8/)
  assert.match(configuredFilter, /filteredOptions\.value\.forEach/)
  assert.match(columnFilter, /class="column-header-filter__trigger"/)
})

test('标注项目不再为项目进度提供重复的查询栏筛选按钮', () => {
  assert.doesNotMatch(annotationSource, /class="status-filter-trigger"/)
  assert.match(annotationSource, /<ConfiguredColumnHeaderFilter v-if="headerFilterDefinition\(column\.key\)"/)
})

test('前端协作文档约束新增页面复用公共漏斗筛选组件', () => {
  assert.match(agentGuidelines, /ConfiguredColumnHeaderFilter\.vue/)
  assert.match(agentGuidelines, /不得在页面中复制漏斗图标/)
  assert.match(agentGuidelines, /“确定”后才更新正式筛选值/)
})
