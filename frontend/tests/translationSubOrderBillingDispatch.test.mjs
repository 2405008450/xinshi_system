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
  assert.match(source, /validateWordCountMatrix[\s\S]*?form\.wordCountMatrixSource === 'suborder_aggregate'[\s\S]*?return callback\(\)/)
})

test('母子订单通用收费编辑器按客户字数计算税价并按币种汇总', () => {
  const source = read('src/views/project/translation/components/CustomerChargeEditor.vue')
  const projectDetails = read('src/views/project/translation/ProjectDetails.vue')
  const subOrderManagement = read('src/views/project/translation/SubOrderManagement.vue')

  assert.match(source, /normalizeWordCountMatrix\(props\.wordCountMatrix\)\.customer/)
  assert.match(source, /Number\(count\) \/ Number\(row\.unitSize\) \* Number\(unitPrice\)/)
  assert.match(source, /unitPriceExclTax/)
  assert.match(source, /unitPriceInclTax/)
  assert.match(source, /totalExclTax/)
  assert.match(source, /totalInclTax/)
  assert.match(source, /value-format="YYYY-MM"/)
  assert.match(source, /lastSuggestions/)
  assert.match(source, /sameAmount\(row\[key\], previous\)/)
  assert.match(source, /Object\.entries\(totals\)/)
  assert.equal((projectDetails.match(/<CustomerChargeEditor/g) || []).length, 2)
  assert.match(subOrderManagement, /<CustomerChargeEditor/)
  assert.doesNotMatch(subOrderManagement, /SubOrderChargeEditor/)
})

test('稿件安排回退为可编辑路径并按整目录打包', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')
  const api = read('src/api/manuscriptArrangements.js')

  assert.doesNotMatch(source, /ManuscriptFileSelector/)
  assert.doesNotMatch(source, /file_selection_mode: 'selected'/)
  assert.match(source, /v-model="mailPathForm\.dispatch_path"/)
  assert.match(source, /@click="saveMailPaths"/)
  assert.match(source, /自动将派稿文路径和参考文件路径一中的文件合并打包为 ZIP 附件/)
  assert.match(api, /batches\/\$\{dispatchId\}\/mail-paths/)
})

test('稿件安排可编辑当前订单的文件名称并随派稿保存', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')

  assert.equal((source.match(/v-model="dispatchForm\.file_name"/g) || []).length, 2)
  assert.match(source, /file_name: selectedProject\.value\?\.file_name \|\| ''/)
  assert.match(source, /file_name: dispatchForm\.file_name\.trim\(\) \|\| null/)
  assert.match(source, /保存后同步到笔译项目中的对应订单/)
})
