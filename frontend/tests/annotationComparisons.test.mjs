import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../src/views/project/AnnotationComparisons.vue', import.meta.url), 'utf8')
const workspace = fs.readFileSync(new URL('../src/views/project/AnnotationWorkspace.vue', import.meta.url), 'utf8')
const detail = fs.readFileSync(new URL('../src/components/annotation/AnnotationProjectDetailPopover.vue', import.meta.url), 'utf8')
const projects = fs.readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')

test('标注工作区提供独立项目对比页签', () => {
  assert.match(workspace, /label="项目对比" name="comparisons"/)
  assert.match(workspace, /AnnotationComparisons\.vue/)
})

test('比较组支持防抖搜索、删除管理和二至十个项目校验', () => {
  assert.match(page, /setTimeout\(search,400\)/)
  assert.match(page, /BatchDeleteToolbar/)
  assert.match(page, /count<2/)
  assert.match(page, /count>10/)
})

test('比较区采用横向矩阵并复用项目详情组件', () => {
  assert.match(page, /comparison-matrix/)
  assert.match(page, /AnnotationProjectDetailPopover/)
  assert.match(projects, /AnnotationProjectDetailPopover/)
  assert.match(detail, /annotationApi\.getAnnotationProject\(props\.projectId\)/)
})

test('比较说明只在组级区域展示', () => {
  assert.match(page, /class="comparison-description"/)
  assert.doesNotMatch(page, /key:'description',label:'比较说明'/)
})
