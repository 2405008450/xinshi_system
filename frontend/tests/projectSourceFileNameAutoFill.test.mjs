import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('原文路径支持自动读取并填充项目名称', () => {
  const component = read('src/views/project/translation/components/ProjectFilesTab.vue')
  const projectDetails = read('src/views/project/translation/ProjectDetails.vue')
  const api = read('src/api/projectFiles.js')

  assert.match(api, /source-path\/inspect/)
  assert.match(component, /@blur="handleSourcePathBlur"/)
  assert.match(component, />\s*读取文件名\s*</)
  assert.match(component, /emit\('update:sourceFileName', response\.source_file_name \|\| ''\)/)
  assert.match(component, /fillSourceFileNameFromPath,/)
  assert.match(projectDetails, /await projectFilesTabRef\.value\?\.fillSourceFileNameFromPath/)
})

// 执行组件中的真实异步读取函数，模拟请求与用户输入发生在不同时间。
function reader(initialName = '') {
  const component = read('src/views/project/translation/components/ProjectFilesTab.vue')
  const functionSource = component.slice(component.indexOf('async function fillSourceFileNameFromPath('), component.indexOf('\nfunction handleSourcePathBlur'))
  const pending = []
  let notifyReady
  const ready = new Promise(resolve => { notifyReady = resolve })
  const props = { sourceFileName: initialName }
  const pathGroupForm = { storage_path: '/原文' }
  const context = vm.createContext({
    props, pathGroupForm, sourceNameLoading: { value: false },
    loadedProjectId: null, loadFiles: async () => {},
    sourceNameRequest: null, sourceNameRequestPath: '', sourceNameRequestId: 0,
    inspectProjectSourcePath: (path) => new Promise((resolve, reject) => {
      pending.push({ path, resolve, reject })
      notifyReady()
    }),
    emit: (_, value) => { props.sourceFileName = value },
    ElMessage: { success() {}, error() {} }, getLocalizedErrorMessage: () => '读取失败',
  })
  vm.runInContext(functionSource, context)
  return { context, pending, props, pathGroupForm, ready, fill: context.fillSourceFileNameFromPath }
}

test('自动读取只填空值，主动读取可以替换手填文件名', async () => {
  const state = reader('手填文件.docx')
  await state.fill()
  assert.equal(state.pending.length, 0)
  const request = state.fill({ force: true })
  state.pending[0].resolve({ source_file_name: '路径文件.pdf；附件.xlsx', file_count: 2 })
  await request
  assert.equal(state.props.sourceFileName, '路径文件.pdf；附件.xlsx')
})

test('请求过程中输入的名称不会被自动读取响应覆盖', async () => {
  const state = reader()
  const request = state.fill()
  state.props.sourceFileName = '请求中手填.docx'
  state.pending[0].resolve({ source_file_name: '自动读取.pdf', file_count: 1 })
  await request
  assert.equal(state.props.sourceFileName, '请求中手填.docx')
})

test('主动读取不复用尚未完成的自动读取，按明确操作替换手填内容', async () => {
  const state = reader()
  const automatic = state.fill()
  state.props.sourceFileName = '手填.docx'
  const forced = state.fill({ force: true })
  state.pending[1].resolve({ source_file_name: '主动读取.pdf', file_count: 1 })
  await forced
  state.pending[0].resolve({ source_file_name: '旧自动读取.pdf', file_count: 1 })
  await automatic
  assert.equal(state.props.sourceFileName, '主动读取.pdf')
})

test('历史项目先等待路径加载，再读取真实文件名', async () => {
  const state = reader()
  state.props.projectId = '隔离项目'
  let loaded = false
  state.context.loadFiles = async () => {
    state.pathGroupForm.storage_path = '/历史项目原文'
    loaded = true
  }
  const request = state.fill()
  await state.ready
  assert.equal(loaded, true)
  assert.equal(state.pending[0].path, '/历史项目原文')
  state.pending[0].resolve({ source_file_name: '历史原文.docx', file_count: 1 })
  await request
  assert.equal(state.props.sourceFileName, '历史原文.docx')
})

test('切换路径后旧响应失效，读取失败后仍可手填', async () => {
  const state = reader()
  const first = state.fill()
  state.pathGroupForm.storage_path = '/新原文'
  const second = state.fill()
  state.pending[1].resolve({ source_file_name: '新路径.pdf', file_count: 1 })
  await second
  state.pending[0].resolve({ source_file_name: '旧路径.pdf', file_count: 1 })
  await first
  assert.equal(state.props.sourceFileName, '新路径.pdf')
  const failed = state.fill({ force: true })
  state.pending[2].reject(new Error('不可读'))
  await assert.rejects(failed)
  state.props.sourceFileName = '手填可保存.docx'
  await state.fill()
  assert.equal(state.props.sourceFileName, '手填可保存.docx')
  assert.equal(state.context.sourceNameLoading.value, false)
})

test('保存前先读取文件名，再进行 AppForm 整表校验', () => {
  const component = read('src/views/project/translation/ProjectDetails.vue')
  const submit = component.slice(component.indexOf('const handleSubmit = async'), component.indexOf('const onProjectDialogClosed'))
  assert.ok(submit.indexOf('fillSourceFileNameFromPath') < submit.indexOf('formRef.value.validate()'))
})
