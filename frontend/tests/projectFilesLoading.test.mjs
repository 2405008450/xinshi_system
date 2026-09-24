import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

// 执行组件的真实加载逻辑，用可控 Promise 模拟慢请求及乱序响应。
function setup() {
  const source = readFileSync(new URL('../src/views/project/translation/components/ProjectFilesTab.vue', import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  const props = { projectId: 'A', active: true, sourceFileName: '' }
  const requests = []
  const watchers = []
  const context = vm.createContext({
    defineEmits: () => () => {}, defineProps: () => props, defineExpose: () => {},
    computed: fn => ({ get value() { return fn() } }), reactive: value => value,
    ref: value => ({ value }), watch: (...args) => watchers.push(args), onBeforeUnmount: () => {},
    hasPermission: () => true, ElMessage: { warning() {}, error() {} },
    getLocalizedErrorMessage: (_error, fallback) => fallback,
    getProjectFilesByProject: id => new Promise((resolve, reject) => requests.push({ id, resolve, reject })),
  })
  vm.runInContext(script + '\n globalThis.api = { loadFiles, resetPathGroup, validatePathGroup, pathGroupForm, fileLoading, fileLoadError }', context)
  return { ...context.api, props, requests, change: watchers[0][1] }
}

test('旧订单的迟到响应不能覆盖新订单，也不能提前结束 loading', async () => {
  const s = setup()
  const first = s.loadFiles()
  s.props.projectId = 'B'
  s.resetPathGroup()
  const second = s.loadFiles()
  s.requests[0].resolve([{ storage_path: 'old' }])
  await first
  assert.equal(s.fileLoading.value, true)
  assert.equal(s.pathGroupForm.storage_path, '')
  s.requests[1].resolve([{ storage_path: 'new' }])
  await second
  assert.equal(s.pathGroupForm.storage_path, 'new')
})

test('加载成功后切换页签不重新请求、不覆盖未保存输入', async () => {
  const s = setup()
  const pending = s.loadFiles()
  s.requests[0].resolve([])
  await pending
  s.pathGroupForm.storage_path = 'unsaved'
  s.change(['A', false], ['A', true])
  s.change(['A', true], ['A', false])
  assert.equal(s.requests.length, 1)
  assert.equal(s.pathGroupForm.storage_path, 'unsaved')
})

test('失败和加载期间禁止保存，重试成功后恢复', async () => {
  const s = setup()
  let pending = s.loadFiles()
  assert.equal(await s.validatePathGroup(), false)
  s.requests[0].reject(new Error('timeout'))
  await pending
  assert.ok(s.fileLoadError.value)
  assert.equal(await s.validatePathGroup(), false)
  pending = s.loadFiles()
  s.requests[1].resolve([])
  await pending
  assert.equal(s.fileLoadError.value, '')
  assert.equal(await s.validatePathGroup(), true)
})

test('关闭重置后迟到失败不会污染下一次表单', async () => {
  const s = setup()
  const pending = s.loadFiles()
  s.resetPathGroup()
  s.requests[0].reject(new Error('timeout'))
  await pending
  assert.equal(s.fileLoadError.value, '')
  assert.equal(s.fileLoading.value, false)
})
