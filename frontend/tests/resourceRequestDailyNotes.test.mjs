import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/resource/ResourceRequests.vue', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/views/resource/components/ResourceRequestDailyNotesDialog.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/resourceRequests.js', import.meta.url), 'utf8')

test('资源需求页提供需求说明入口和富文本编辑器', () => {
  assert.match(page, />需求说明<\/el-button>/)
  assert.match(page, /<ResourceRequestDailyNotesDialog/)
  assert.match(dialog, /<RichTextComposer/)
  assert.match(dialog, /format-colors/)
  assert.match(dialog, /<RichTextContent/)
})

test('需求说明按日期维护并显示最新优先的历史记录', () => {
  assert.match(dialog, /value-format="YYYY-MM-DD"/)
  assert.match(dialog, /默认按说明日期从新到旧排列/)
  assert.match(dialog, /right\.noteDate\.localeCompare\(left\.noteDate\)/)
  assert.match(dialog, /existingNote\.value\?\.updatedAt/)
  assert.match(api, /resource-requests\/daily-notes/)
})

test('需求说明弹窗使用全局可拖拽长表单布局并保护未保存修改', () => {
  assert.match(dialog, /<DraggableFormDialog/)
  assert.match(dialog, /resource-request-notes-dialog/)
  assert.match(dialog, /max-height:\s*90vh/)
  assert.match(dialog, /\.el-dialog__body\s*\{[^}]*overflow-y:\s*auto/)
  assert.match(dialog, /confirmDiscard/)
})
