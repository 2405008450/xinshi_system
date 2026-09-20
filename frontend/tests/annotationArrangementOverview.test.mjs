import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../src/views/project/AnnotationArrangementOverview.vue', import.meta.url), 'utf8')
const dialog = fs.readFileSync(new URL('../src/components/annotation/AnnotationProjectArrangementQuickDialog.vue', import.meta.url), 'utf8')
const projects = fs.readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const router = fs.readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const layout = fs.readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const workspace = fs.readFileSync(new URL('../src/views/project/AnnotationWorkspace.vue', import.meta.url), 'utf8')
const api = fs.readFileSync(new URL('../src/api/annotationOps.js', import.meta.url), 'utf8')
const dailyArrangement = fs.readFileSync(new URL('../src/components/annotation/AnnotationDailyArrangement.vue', import.meta.url), 'utf8')

test('标注项目安排概览位于现有标注项目工作区', () => {
  assert.match(workspace, /label="项目安排" name="arrangements"/)
  assert.match(workspace, /arrangements:\s*defineAsyncComponent/)
  assert.match(router, /path:\s*'annotation-arrangements'/)
  assert.match(router, /section:\s*'arrangements'/)
  assert.doesNotMatch(layout, /index="\/annotation-arrangements"/)
})

test('概览常驻日期、安排状态、项目进度和关键字筛选', () => {
  assert.match(page, /昨日/)
  assert.match(page, /今日/)
  assert.match(page, /明日/)
  assert.match(page, /aria-label="安排状态"/)
  assert.match(page, /aria-label="项目进度"/)
  assert.match(page, /搜索订单号、项目名称或客户名称/)
  assert.match(page, /setTimeout\(runSearch, 400\)/)
})

test('概览包含项目和人员两个视图并使用轻量安排窗口', () => {
  assert.match(page, /label="项目视图"/)
  assert.match(page, /label="人员视图"/)
  assert.match(page, /AnnotationProjectArrangementQuickDialog/)
  assert.match(page, /:default-execution-date="filters\.executionDate"/)
  assert.match(page, /AnnotationProjectDetailPopover/)
  assert.match(page, /TableColumnSettings/)
})

test('概览提供可编辑、可全屏查看的今日安排', () => {
  assert.match(page, /label="今日安排" name="today"/)
  assert.match(page, /AnnotationDailyArrangement/)
  assert.match(dailyArrangement, /<RichTextComposer/)
  assert.match(dailyArrangement, /<RichTextContent/)
  assert.match(dailyArrangement, /requestFullscreen\(\)/)
  assert.match(dailyArrangement, /document\.exitFullscreen\(\)/)
  assert.match(dailyArrangement, /fallbackFullscreen\.value = true/)
  assert.match(dailyArrangement, /全屏查看/)
  assert.match(api, /project-arrangements\/daily-notes/)
})

test('概览 API、安排池和弹窗日期覆盖均已接入', () => {
  assert.match(api, /getProjectArrangementOverview/)
  assert.match(api, /getProjectArrangementWorkloads/)
  assert.match(dialog, /defaultExecutionDate/)
  assert.match(dialog, /props\.defaultExecutionDate/)
  assert.match(dialog, /: tomorrowString\(\)/)
  assert.match(api, /setProjectArrangementMembership/)
  assert.match(projects, /canManageArrangementPool = isSuperAdmin\(\)/)
  assert.match(projects, /加入安排/)
  assert.match(projects, /移出/)
})
