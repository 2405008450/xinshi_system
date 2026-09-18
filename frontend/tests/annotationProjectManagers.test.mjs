import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../src/views/project/AnnotationProjects.vue', import.meta.url),
  'utf8',
)

test('标注项目表单支持多选项目经理并提交全部负责人', () => {
  assert.match(source, /v-model="projectManagerIds"\s+multiple/)
  assert.match(source, /const projectManagerIds=computed\(/)
  assert.match(source, /\.filter\(\(item\)=>\(item\.roleCode\|\|item\.role_code\)==='project_manager'\)/)
  assert.match(source, /projectManagerIds:isClientManager\?roleAssignmentIds\(row,'project_manager'\):\(value\|\|\[\]\)/)
})

test('标注项目列表项目经理快捷编辑使用多选并合并姓名展示', () => {
  assert.match(source, /:multiple="column\.key === 'projectManagerName'"/)
  assert.match(source, /roleAssignmentNames\(row,roleCode\)\.join\('、'\)/)
})
