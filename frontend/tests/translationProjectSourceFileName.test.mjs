import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('表单以真实文件名作为唯一项目名称，保存时同步兼容名称字段', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')
  const filesTab = read('src/views/project/translation/components/ProjectFilesTab.vue')

  assert.match(source, /label="项目名称" prop="sourceFileName" data-field-key="sourceFileName"/)
  assert.match(source, /v-model="form\.sourceFileName"/)
  assert.match(source, /sourceFileName: ''/)
  assert.match(source, /label: '项目名称', key: 'sourceFileName', span: 2, editable: true, required: true, maxlength: 255/)
  assert.match(source, /key: 'sourceFileName', label: '项目名称', type: 'text'/)
  assert.match(source, /NULLABLE_FIELDS = \['sourceFileName'/)
  assert.match(source, /v-model:source-file-name="form\.sourceFileName"/)
  assert.match(filesTab, /<el-form-item label="项目名称"/)
  assert.match(filesTab, /emit\('update:sourceFileName', \$event\)/)
  assert.doesNotMatch(filesTab, /直接绑定母订单，不会随项目名称的自动生成规则变化/)
  assert.doesNotMatch(source, /GeneratedProjectNameInput|syncProjectName|regenerateProjectName|projectNameManuallyEdited|v-model="form\.projectName"/)
  assert.match(source, /result\.projectName = result\.sourceFileName/)
  assert.match(source, /data-dialog-field-search-aliases="文件名称,原文文件名"/)
  assert.match(source, /sourceFileName: \[\s+\{ required: true/)
})

test('列表和详情的项目名称仅使用文件名，客户简称去掉母字', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')
  const details = source.slice(source.indexOf('const projectDetailItems = ['), source.indexOf('const subOrderDetailItems = ['))
  const filters = source.slice(source.indexOf('const translationFilterFields = ['), source.indexOf('Object.assign(searchForm'))

  assert.doesNotMatch(details, /key: 'projectName'|母订单文件名称|母客户简称/)
  assert.doesNotMatch(filters, /key: 'projectName'|母订单文件名称|母客户简称/)
  assert.match(details, /label: '客户简称', key: 'clientShortName'/)
  assert.match(filters, /key: 'clientShortName', label: '客户简称'/)
  assert.match(source, /column\.key === 'sourceFileName'[^\n]+:title="row\.sourceFileName \|\| '-'">\{\{ row\.sourceFileName \|\| '-' \}\}/)
  assert.doesNotMatch(source, /column\.key === 'projectName'/)
})

test('子订单历史字段在界面统一显示为文件名称', () => {
  const detail = read('src/views/project/translation/ProjectDetails.vue')
  const management = read('src/views/project/translation/SubOrderManagement.vue')
  const batchDialog = read('src/views/project/translation/components/SubOrderBatchCreateDialog.vue')
  const inlineEditor = read('src/views/project/translation/components/InlineSubProjectName.vue')

  for (const source of [detail, management, batchDialog, inlineEditor]) {
    assert.doesNotMatch(source, /子项目名称/)
  }
  assert.match(detail, /\{ label: '文件名称', key: 'subProjectName' \}/)
  assert.match(management, /label="文件名称" prop="subProjectName"/)
  assert.match(batchDialog, /label="文件名称前缀"/)
  assert.match(inlineEditor, /aria-label="保存文件名称"/)
})

test('列表关键词提示覆盖文件名称', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')

  assert.match(source, /placeholder="母\/子订单号、项目名称、文件名称、客户名称或客户单号"/)
})
