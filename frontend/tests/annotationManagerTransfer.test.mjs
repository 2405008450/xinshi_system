import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const viewSource = readFileSync(
  new URL('../src/views/project/AnnotationProjects.vue', import.meta.url),
  'utf8',
)
const dialogSource = readFileSync(
  new URL('../src/components/annotation/AnnotationManagerTransferDialog.vue', import.meta.url),
  'utf8',
)
const apiSource = readFileSync(
  new URL('../src/api/workflow.js', import.meta.url),
  'utf8',
)

test('标注项目页仅向超级管理员展示项目经理交接入口', () => {
  assert.match(viewSource, /const canDirectTransferManager = isSuperAdmin\(\)/)
  assert.match(viewSource, /v-if="canDirectTransferManager && !deleteMode"/)
})

test('离职交接支持服务端预览、逐项排除和强确认', () => {
  assert.match(dialogSource, /previewAnnotationManagerTransferAPI/)
  assert.match(dialogSource, /@selection-change="selectedProjects = \$event"/)
  assert.match(dialogSource, /inputValidator: value => String\(value \|\| ''\)\.trim\(\) === '交接'/)
  assert.match(dialogSource, /project_ids: selectedProjects\.value\.map/)
})

test('离职交接使用独立的预览和直接移交接口', () => {
  assert.match(apiSource, /project-manager-handover\/direct\/preview/)
  assert.match(apiSource, /project-manager-handover\/direct'/)
})
