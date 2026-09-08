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

test('标注项目页仅向超级管理员展示一个交接入口', () => {
  assert.match(viewSource, /const canDirectTransferManager = isSuperAdmin\(\)/)
  assert.match(viewSource, /v-if="canDirectTransferManager && !deleteMode"/)
  assert.equal(viewSource.match(/>交接<\/el-button>/g)?.length, 1)
  assert.doesNotMatch(viewSource, />项目经理交接<\/el-button>/)
  assert.doesNotMatch(viewSource, />客户经理交接<\/el-button>/)
  assert.doesNotMatch(viewSource, /:manager-type="managerTransferType"/)
  assert.match(dialogSource, /<el-radio-button label="project_manager">项目经理<\/el-radio-button>/)
  assert.match(dialogSource, /<el-radio-button label="client_manager">客户经理<\/el-radio-button>/)
  assert.match(dialogSource, /@change="handleManagerTypeChange"/)
  assert.match(dialogSource, /:validate-on-rule-change="false"/)
  assert.match(dialogSource, /async function handleManagerTypeChange\(\)[\s\S]*await nextTick\(\)[\s\S]*clearValidate\(\)/)
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
  assert.match(apiSource, /client-manager-handover\/direct\/preview/)
  assert.match(apiSource, /client-manager-handover\/direct'/)
  assert.match(dialogSource, /selectedManagerType\.value === 'client_manager'/)
  assert.match(dialogSource, /directTransferAnnotationClientManagerAPI/)
})
