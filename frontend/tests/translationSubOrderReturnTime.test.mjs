import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(
  new URL('../src/views/project/translation/SubOrderManagement.vue', import.meta.url),
  'utf8',
)

test('子订单管理页展示并可维护译员回稿时间', () => {
  assert.match(page, /<el-table-column label="译员回稿时间"/)
  assert.match(page, /:translators="row\.assignedTranslators"/)
  assert.match(page, /label: '译员回稿时间'.*formatTranslatorReturnTimes\(row\.assignedTranslators\)/)
  assert.match(page, /updateSubOrder\(row\.id, \{ assignedTranslatorCompletions: completions \}\)/)
})
