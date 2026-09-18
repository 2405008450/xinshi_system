import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/components/annotation/AnnotationProjectArrangementQuickDialog.vue', import.meta.url), 'utf8')
const progressUtility = readFileSync(new URL('../src/utils/annotationProgress.js', import.meta.url), 'utf8')

test('具体任务列默认展示但不再绕过安排池', () => {
  assert.match(page, /defaultColumns = \[[^\]]*'taskDescription'/)
  assert.match(page, /column\.key === 'taskDescription'/)
  assert.doesNotMatch(page, /column\.key === 'taskDescription'[\s\S]{0,300}@click\.stop="openArrangement\(row\)"/)
  assert.match(page, /<AnnotationProjectArrangementQuickDialog/)
  assert.match(page, /row\.arrangementIncluded/)
})

test('项目操作列只保留高频安排入口，编辑和移出收进更多菜单', () => {
  assert.match(page, /label="操作" width="150"/)
  assert.match(page, /edit-in-more/)
  assert.match(page, /command: 'arrangement-remove', label: '移出安排'/)
  assert.doesNotMatch(page, />移出<\/el-button>/)
})

test('加入安排前必须填写备注并随成员关系保存', () => {
  assert.match(page, /ElMessageBox\.prompt\('请填写将该项目加入安排池的备注'/)
  assert.match(page, /if\(!normalized\)return '请填写备注'/)
  assert.match(page, /\{included,membershipNote,expectedUpdatedAt:/)
  assert.match(page, /row\.arrangementMembershipNote=result\.membershipNote/)
})

test('项目安排改为单项目轻量无遮罩窗口', () => {
  assert.match(dialog, /:modal="false"/)
  assert.match(dialog, /:lock-scroll="false"/)
  assert.match(dialog, /width="min\(920px, calc\(100vw - 32px\)\)"/)
  assert.doesNotMatch(dialog, /搜索订单号、项目名称或客户名称/)
  assert.doesNotMatch(dialog, /project-summary-panel/)
  assert.match(dialog, /v-for="group in assigneeGroups"/)
  assert.match(dialog, /新增任务/)
  assert.match(dialog, />保存</)
  assert.match(dialog, /max-height:86vh/)
  assert.match(dialog, /overflow-y:auto/)
})

test('执行日期、任务类型、执行人和任务内容保持可编辑', () => {
  assert.match(dialog, /label="执行日期"/)
  assert.match(dialog, /label="任务类型"/)
  assert.match(dialog, /label="执行人"/)
  assert.match(dialog, /label="任务内容"/)
  assert.match(dialog, /const taskProp =/)
})

test('任务类型可创建维护且轻量窗口不再承载项目进度', () => {
  assert.match(dialog, /allow-create/)
  assert.match(dialog, /任务类型管理/)
  assert.doesNotMatch(dialog, /补充进度|statusEntryMode|value="status"/)
  assert.match(progressUtility, /row\.entryKind === 'progress'/)
})

test('切换项目和关闭窗口具备脏数据保护', () => {
  assert.match(dialog, /保存并切换/)
  assert.match(dialog, /放弃并切换/)
  assert.match(dialog, /distinguishCancelAndClose:true/)
  assert.match(dialog, /项目安排存在未保存修改/)
})
