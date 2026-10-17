import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import test from 'node:test'
import { createRenderer, nextTick, ref } from 'vue'

// 只替换网络与消息框，使用真实 Vue 生命周期测试共享控制器。
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@/api/annotationOps') return { url: 'mock:progress-api', shortCircuit: true }
    if (specifier === 'element-plus') return { url: 'mock:progress-messages', shortCircuit: true }
    if (specifier.startsWith('@/')) return nextResolve(new URL(`../src/${specifier.slice(2)}.js`, import.meta.url).href, context)
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url === 'mock:progress-api') return { format: 'module', shortCircuit: true, source: `
      export const getCustomerProgress = (...args) => globalThis.progressControllerTest.api.get(...args)
      export const createCustomerProgress = (...args) => globalThis.progressControllerTest.api.create(...args)
      export const updateCustomerProgress = (...args) => globalThis.progressControllerTest.api.update(...args)
    ` }
    if (url === 'mock:progress-messages') return { format: 'module', shortCircuit: true, source: `
      export const ElMessage = Object.fromEntries(['success','warning','error'].map(key => [key, text => globalThis.progressControllerTest.messages.push([key,text])]))
      export const ElMessageBox = { confirm: (...args) => globalThis.progressControllerTest.confirm(...args) }
    ` }
    return nextLoad(url, context)
  },
})
const { useAnnotationCustomerProgress } = await import('../src/composables/useAnnotationCustomerProgress.js')
hooks.deregister()

const renderer = createRenderer({
  createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
  parentNode: () => null, nextSibling: () => null,
})
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const row = { id: 'customer-1', changeNote: '客户反馈', effectiveOn: '2026-10-14T10:00:00+08:00', updatedAt: '2026-10-14T10:00:00.123456+08:00' }
function mount(overrides = {}) {
  const calls = [], messages = []
  const state = { messages, confirm: async () => {}, api: {
    get: async (...args) => { calls.push(['get', ...args]); return [row] },
    create: async (...args) => { calls.push(['create', ...args]); return row },
    update: async (...args) => { calls.push(['update', ...args]); return row },
    ...overrides.api,
  } }
  globalThis.progressControllerTest = state
  const projectId = ref('project-1'), active = ref(false), busy = ref(false)
  const entryRef = ref({ validate: async () => true, clearValidate() {}, focusEntry() {}, applyServerErrors() {} })
  let progress
  const app = renderer.createApp({ setup() { progress = useAnnotationCustomerProgress({ projectId, active, busy, entryRef, onEdit: () => calls.push(['edit']), onSaved: async () => calls.push(['saved']), ...overrides.options }); return () => null } })
  app.mount({})
  return { progress, projectId, active, busy, entryRef, calls, state, unmount: () => app.unmount() }
}

test('查看与填写激活共享已加载记录，隐藏再显示保留草稿且不重复查询', async (t) => {
  const c = mount(); t.after(c.unmount)
  c.active.value = true; await nextTick(); await nextTick()
  c.progress.form.changeNote = '未保存客户草稿'
  c.active.value = false; await nextTick(); c.active.value = true; await nextTick()
  assert.equal(c.calls.filter(([kind]) => kind === 'get').length, 1)
  assert.equal(c.progress.form.changeNote, '未保存客户草稿')
})

test('客户草稿仅修改时间也需要关闭保护，恢复后不再提示', (t) => {
  const c = mount(); t.after(c.unmount)
  const initialTime = c.progress.form.effectiveOn
  assert.equal(c.progress.hasDraft(), false)
  c.progress.form.effectiveOn = '2026-10-10 17:30:00'
  assert.equal(c.progress.hasDraft(), true)
  c.progress.form.effectiveOn = initialTime
  assert.equal(c.progress.hasDraft(), false)
})

test('首次加载与沟通带入并发时复用请求，等待后追加来源与内容', async (t) => {
  const loading = deferred(), calls = []
  const c = mount({ api: { get: (...args) => { calls.push(args); return loading.promise } } }); t.after(c.unmount)
  c.active.value = true; await nextTick()
  const accepting = c.progress.acceptDraft({ changeNote: '报价确认', effectiveOn: '2026-10-14 11:00:00', source: { messageCount: 1, senderSummary: '客户经理' } })
  assert.equal(calls.length, 1)
  loading.resolve([row]); await accepting
  assert.equal(c.progress.form.changeNote, '报价确认')
  assert.equal(c.progress.draftSource.messageCount, 1)
})

test('切换项目取消旧请求，晚到的响应不能覆盖新项目记录', async (t) => {
  const requests = []
  const c = mount({ api: { get: (id, { signal }) => { const pending = deferred(); requests.push({ id, signal, ...pending }); return pending.promise } } }); t.after(c.unmount)
  c.active.value = true; await nextTick()
  c.progress.form.changeNote = '旧项目草稿'
  c.projectId.value = 'project-2'; await nextTick()
  assert.equal(requests[0].signal.aborted, true)
  assert.equal(c.progress.form.changeNote, '')
  requests[1].resolve([{ ...row, id: 'new-record' }]); await nextTick(); await nextTick()
  requests[0].resolve([row]); await nextTick(); await nextTick()
  assert.equal(c.progress.rows[0].id, 'new-record')
})

test('校验前锁定提交，重复点击只保存一次，时间明确携带 +08:00', async (t) => {
  const validation = deferred()
  const c = mount(); t.after(c.unmount)
  c.entryRef.value.validate = () => validation.promise
  c.progress.form.changeNote = '  等待客户验收  '; c.progress.form.effectiveOn = '2026-10-14 11:00:00'
  const saving = c.progress.save(); await c.progress.save()
  assert.equal(c.progress.validating, true)
  assert.equal(c.progress.submitting, false)
  validation.resolve(true); await saving
  const writes = c.calls.filter(([kind]) => kind === 'create')
  assert.equal(writes.length, 1)
  assert.equal(writes[0][2].changeNote, '等待客户验收')
  assert.equal(writes[0][2].effectiveOn, '2026-10-14T11:00:00+08:00')
  assert.equal(c.progress.form.changeNote, '')
  assert.equal(c.progress.submitting, false)
})

test('保存失败保留草稿，编辑保存回传未截断的并发版本', async (t) => {
  const c = mount(); t.after(c.unmount)
  await c.progress.edit(row)
  c.progress.form.changeNote = '修改后的反馈'
  c.entryRef.value.applyServerErrors = () => {
    assert.equal(c.progress.submitting, false)
    assert.equal(c.progress.validating, true)
  }
  c.state.api.update = async () => { throw { detail: '记录已由其他人更新' } }
  await c.progress.save()
  assert.equal(c.progress.form.changeNote, '修改后的反馈')
  assert.equal(c.progress.editingId, row.id)
  c.state.api.update = async (...args) => { c.calls.push(['update', ...args]); return row }
  await c.progress.save()
  assert.equal(c.calls.find(([kind]) => kind === 'update')[2].expectedUpdatedAt, row.updatedAt)
})

test('校验失败不禁用表单写入状态，释放防重复锁并保留输入', async (t) => {
  const c = mount(); t.after(c.unmount)
  c.progress.form.changeNote = '校验未通过的草稿'
  c.entryRef.value.validate = async () => {
    assert.equal(c.progress.validating, true)
    assert.equal(c.progress.submitting, false)
    return false
  }
  await c.progress.save()
  assert.equal(c.progress.validating, false)
  assert.equal(c.progress.form.changeNote, '校验未通过的草稿')
  assert.ok(!c.calls.some(([kind]) => kind === 'create'))
})

test('有草稿时取消覆盖编辑，原草稿和编辑状态保持不变', async (t) => {
  const c = mount(); t.after(c.unmount)
  c.progress.form.changeNote = '已有草稿'
  c.state.confirm = async () => { throw 'cancel' }
  await c.progress.edit(row)
  assert.equal(c.progress.form.changeNote, '已有草稿')
  assert.equal(c.progress.editingId, '')
})

test('刷新失败不会把已经成功的写入报告为保存失败', async (t) => {
  const c = mount({ options: { onSaved: async () => { throw new Error('刷新失败') } } }); t.after(c.unmount)
  c.progress.form.changeNote = '已保存反馈'
  await c.progress.save()
  assert.equal(c.progress.form.changeNote, '')
  assert.ok(c.state.messages.some(([kind]) => kind === 'warning'))
  assert.ok(!c.state.messages.some(([kind]) => kind === 'error'))
})
