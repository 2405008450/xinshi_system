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

test('稿件安排按译员勾选派稿文件并提交文件清单', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')
  const selector = read('src/views/manuscript/components/ManuscriptFileSelector.vue')
  const api = read('src/api/manuscriptArrangements.js')

  assert.match(source, /import ManuscriptFileSelector/)
  assert.match(source, /file_selection_mode: 'selected'/)
  assert.match(source, /selected_files: \[\]/)
  assert.match(source, /请至少选择一个派稿文件/)
  assert.doesNotMatch(source, /<label class="is-required">派稿文件<\/label>/)
  assert.doesNotMatch(source, /<el-form-item label="派稿文件" required>/)
  assert.doesNotMatch(source, /function validateDispatchForm\(\) \{[\s\S]*?file_selection_mode === 'selected'[\s\S]*?请选择至少一个派稿文件[\s\S]*?return ''/)
  assert.match(source, /可先确认安排，之后在“发送”阶段填写派稿文路径并选择文件/)
  assert.match(source, /selected_files: \(item\.selected_files \|\| \[\]\)\.map/)
  assert.match(selector, /relative_directory: currentDirectory\.value/)
  assert.match(api, /projects\/\$\{projectId\}\/dispatch-files/)
  assert.match(source, /v-model="mailPathForm\.dispatch_path"/)
  assert.match(source, /@click="saveMailPaths"/)
  assert.match(source, /class="mail-path-input-row"/)
  assert.match(source, /当前译员已勾选的派稿文件与参考文件路径一中的文件合并打包为 ZIP 附件/)
  assert.match(api, /batches\/\$\{dispatchId\}\/mail-paths/)
  assert.match(source, /<label>本次派稿文件<\/label>/)
  assert.match(source, /@click="saveActiveSelectedFiles"/)
  assert.match(source, /@click="savePreviewSelectedFiles"/)
  assert.match(source, /function allPendingAssignmentsHaveSelectedFiles/)
  assert.match(api, /arrangements\/\$\{arrangementId\}\/selected-files/)
  assert.match(selector, /import DraggableFormDialog/)
  assert.match(selector, /<DraggableFormDialog[\s\S]*?append-to-body[\s\S]*?class="file-selector-dialog"/)
  assert.match(selector, /<el-descriptions-item label="文件名称">[\s\S]*?fileName \|\| '-'/)
  assert.equal((source.match(/:file-name="dispatchForm\.file_name \|\| selectedProject\.file_name \|\| ''"/g) || []).length, 4)
  assert.doesNotMatch(selector, /<el-popover/)
})

test('稿件安排可编辑当前订单的文件名称并随派稿保存', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')

  assert.equal((source.match(/v-model="dispatchForm\.file_name"/g) || []).length, 2)
  assert.match(source, /file_name: selectedProject\.value\?\.file_name \|\| ''/)
  assert.match(source, /file_name: dispatchForm\.file_name\.trim\(\) \|\| null/)
  assert.match(source, /保存后同步到笔译项目中的对应订单/)
})

test('点击稿件安排记录会选中对应批次并回填译员派稿信息', () => {
  const source = read('src/views/manuscript/ManuscriptArrangements.vue')

  assert.match(source, /class="dispatch-records-table"[\s\S]*?@row-click="selectDispatchRecord"/)
  assert.match(source, /const selectedDispatchId = ref\(''\)/)
  assert.match(source, /function selectDispatchRecord\(row, _column, event\)[\s\S]*?selectedProject\.value = matchedProject[\s\S]*?file_name: matchedProject\.file_name \|\| row\.file_name \|\| ''[\s\S]*?selectedDispatchId\.value = row\.id[\s\S]*?hydrateDispatchForm\(row\)/)
  assert.match(source, /const selectedProjectDispatch = computed\([\s\S]*?selectedDispatchId\.value[\s\S]*?selectedDispatch \|\| activeDispatchFor/)
  assert.match(source, /:label="assignmentTranslatorName\(assignment\)"/)
})
