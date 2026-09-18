import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/components/annotation/AnnotationProjectArrangementDialog.vue', import.meta.url), 'utf8')
const progressUtility = readFileSync(new URL('../src/utils/annotationProgress.js', import.meta.url), 'utf8')

test('具体任务列默认展示并作为项目安排入口', () => {
  assert.match(page, /defaultColumns = \[[^\]]*'taskDescription'/)
  assert.match(page, /column\.key === 'taskDescription'/)
  assert.match(page, /@click\.stop="openArrangement\(row\)"/)
  assert.match(page, /<AnnotationProjectArrangementDialog/)
})

test('项目安排支持多项目、多任务和固定底部保存', () => {
  assert.match(dialog, /v-for="project in sortedProjects"/)
  assert.match(dialog, /v-for="group in assigneeGroups"/)
  assert.match(dialog, /新增任务/)
  assert.match(dialog, /保存全部/)
  assert.match(dialog, /max-height:90vh/)
  assert.match(dialog, /overflow-y:auto/)
})

test('项目名称、执行日期、任务类型和执行人支持排序', () => {
  assert.match(dialog, /v-model="projectSortOrder"/)
  assert.match(dialog, /项目名称：升序/)
  assert.match(dialog, /项目名称：降序/)
  assert.match(dialog, /label="执行日期"[^>]*sortable[^>]*compareExecutionDate/)
  assert.match(dialog, /label="任务类型"[^>]*sortable[^>]*compareTaskType/)
  assert.match(dialog, /label="执行人"[^>]*sortable[^>]*compareAssignee/)
  assert.match(dialog, /const taskFormProp =/)
})

test('任务类型可创建维护，进度只提供补充和编辑', () => {
  assert.match(dialog, /allow-create/)
  assert.match(dialog, /任务类型管理/)
  assert.match(dialog, /补充进度/)
  assert.match(dialog, /record\.kind === 'progress'/)
  assert.doesNotMatch(dialog, /statusEntryMode|value="status"/)
  assert.match(progressUtility, /row\.entryKind === 'progress'/)
})

test('项目搜索具备 400ms 防抖、取消和旧响应保护', () => {
  assert.match(dialog, /setTimeout\(async \(\) => \{/)
  assert.match(dialog, /400 : 0/)
  assert.match(dialog, /searchController\?\.abort\(\)/)
  assert.match(dialog, /current === searchRequestId/)
  assert.match(dialog, /visible && !projectKeyword\.trim\(\) && searchProjects\(''\)/)
})
