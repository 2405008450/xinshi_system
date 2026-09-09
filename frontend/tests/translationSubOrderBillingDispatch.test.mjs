import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('子订单新增与批量创建不再复制母订单字数', () => {
  const projectDetails = read('src/views/project/translation/ProjectDetails.vue')
  const batchDialog = read('src/views/project/translation/components/SubOrderBatchCreateDialog.vue')

  assert.match(projectDetails, /createSubOrderDefaultsFromProject[^\n]+wordCountMatrix: createEmptyWordCountMatrix\(\)/)
  assert.doesNotMatch(projectDetails, /createSubOrderDefaultsFromProject[^\n]+form\.wordCountMatrix/)
  assert.match(batchDialog, /wordCountMatrix: createEmptyWordCountMatrix\(\)/)
})

test('母订单汇总字数在列表和编辑弹窗中均为只读', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')

  assert.match(source, /:read-only="row\.wordCountMatrixSource === 'suborder_aggregate'"/)
  assert.match(source, /:read-only="form\.wordCountMatrixSource === 'suborder_aggregate'"/)
  assert.match(source, /来自 \{\{ form\.wordCountSubOrderCount \}\} 个子订单/)
})

test('子订单收费编辑器按客户字数计算并按币种汇总', () => {
  const source = read('src/views/project/translation/components/SubOrderChargeEditor.vue')

  assert.match(source, /normalizeWordCountMatrix\(props\.wordCountMatrix\)\.customer/)
  assert.match(source, /Number\(count\) \/ Number\(row\.unitSize\) \* Number\(row\.unitPrice\)/)
  assert.match(source, /Object\.entries\(totals\)/)
})

test('稿件安排逐译员保存选中文件并提示数量差异和重复名单', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')
  const selector = read('src/views/manuscript/components/ManuscriptFileSelector.vue')
  const api = read('src/api/manuscriptArrangements.js')

  assert.match(source, /file_selection_mode: 'selected'/)
  assert.match(source, /selected_files: \[\]/)
  assert.match(source, /译员预定数量合计与订单基准不一致/)
  assert.match(source, /重复分配文件：/)
  assert.match(selector, /relative_directory: currentDirectory\.value/)
  assert.match(api, /projects\/\$\{projectId\}\/dispatch-files/)
})
