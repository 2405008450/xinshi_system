import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const annotationSource = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const configuredFilter = readFileSync(new URL('../src/components/common/ConfiguredColumnHeaderFilter.vue', import.meta.url), 'utf8')
const columnFilter = readFileSync(new URL('../src/components/common/ColumnHeaderFilter.vue', import.meta.url), 'utf8')
const agentGuidelines = readFileSync(new URL('../AGENTS.md', import.meta.url), 'utf8')
const clientsSource = readFileSync(new URL('../src/views/client/Clients.vue', import.meta.url), 'utf8')
const consultationsSource = readFileSync(new URL('../src/views/client/Consultations.vue', import.meta.url), 'utf8')
const translationSource = readFileSync(new URL('../src/views/project/translation/ProjectDetails.vue', import.meta.url), 'utf8')
const interpretationSource = readFileSync(new URL('../src/views/project/interpretation/InterpretationProjectDetails.vue', import.meta.url), 'utf8')
const recruitmentSource = readFileSync(new URL('../src/views/project/RecruitmentProjects.vue', import.meta.url), 'utf8')
const requestsSource = readFileSync(new URL('../src/views/resource/ResourceRequests.vue', import.meta.url), 'utf8')
const manuscriptSource = readFileSync(new URL('../src/views/manuscript/ManuscriptArrangements.vue', import.meta.url), 'utf8')

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

test('标准业务列表的非默认可配置列也能解析公共漏斗定义', () => {
  assert.match(clientsSource, /headerFilterDefinition=\(key\)=>clientFilterFields\.find/)
  assert.match(requestsSource, /resourceRequestHeaderFieldMap = \{ ownerName: 'ownerId' \}/)
  assert.match(recruitmentSource, /headerFilterDefinition=\(key\)=>recruitmentFilterFields\.find/)
  assert.doesNotMatch(recruitmentSource, /headerFilterDefinition=\(key\)=>defaultColumnKeys\.includes/)
  assert.match(interpretationSource, /timeRanges: 'scheduledDateRange'/)
  assert.match(interpretationSource, /subClientContact: 'contactName'/)
  assert.match(interpretationSource, /key: 'translatorCodes'/)
  assert.doesNotMatch(translationSource, /if \(!translationDefaultFilterKeys\.has/)
  assert.match(translationSource, /key: 'clientName'/)
  assert.match(translationSource, /key: 'subClientName'/)
  assert.match(translationSource, /projectSpecialistName: 'projectSpecialistId'/)
  assert.match(translationSource, /projectAssistantName: 'projectAssistantId'/)
  assert.match(translationSource, /layoutSpecialistName: 'layoutSpecialistId'/)
})

test('新咨询和稿件安排复用统一筛选序列化与公共漏斗组件', () => {
  assert.match(consultationsSource, /const consultationFilterFields = \[/)
  assert.match(consultationsSource, /field_filters: serializeFieldFilters\(searchForm, consultationFilterFields\)/)
  assert.match(consultationsSource, /<ConfiguredColumnHeaderFilter/)
  assert.match(manuscriptSource, /const projectFilterFields = \[/)
  assert.match(manuscriptSource, /const translatorFilterFields = \[/)
  assert.match(manuscriptSource, /const dispatchFilterFields = \[/)
  assert.match(manuscriptSource, /project_field_filters: serializeFieldFilters/)
  assert.match(manuscriptSource, /field_filters: serializeFieldFilters\(dispatchFilterModel, dispatchFilterFields\)/)
})
