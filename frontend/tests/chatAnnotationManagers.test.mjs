import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { managerIds } from '../src/utils/annotationManagerChange.js'

const source = readFileSync(new URL('../src/components/chat/ChatAnnotationManagers.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
function harness({ failSave = false, detail = null, managerRole = 'project_manager' } = {}) {
  const writes = [], signals = [], messages = []
  const project = detail || { id: 'project-a', orderNo: 'AP-261022-001', updatedAt: '2026-10-22T12:00:00+08:00', roleAssignments: [{ roleCode: 'project_manager', assigneeId: 'old' }] }
  const api = runInNewContext(script + ';({load,save,form,formRef,loaded,error,project,visible,currentIds,requiresReason})', {
    defineProps: () => ({ projectId: project.id, managerRole }),
    defineExpose: () => {},
    ref: value => ({ value }), reactive: value => value,
    computed: getter => ({ get value() { return getter() } }), onBeforeUnmount: () => {},
    hasPermission: () => true, chatOverlayZIndex: () => 2200, managerIds, AbortController,
    getAnnotationProject: async () => project,
    getAnnotationManagerOptions: async () => [{ id: 'old', full_name: '原经理' }, { id: 'new', full_name: '普通账号' }, { id: 'other', full_name: '其他账号' }],
    updateAnnotationProjectManagers: async (id, payload) => { if (failSave) throw { response: { status: 409 } }; writes.push({ id, payload }) },
    notifyAnnotationManagersUpdated: id => signals.push(id), ElMessage: { success: message => messages.push(message) },
  })
  api.formRef.value = { validate: async () => true }
  return { api, writes, signals, messages }
}

test('只读加载不写库；提交所选全部经理、携带版本及原因', async () => {
  const { api, writes, signals } = harness()
  await api.load()
  assert.equal(writes.length, 0)
  assert.equal(api.requiresReason.value, true)
  assert.deepEqual(Array.from(api.form.managerIds), ['old'])
  api.form.managerIds = ['old', 'new', 'other', 'new']
  api.form.reason = '增加项目协作经理'
  await api.save()
  assert.equal(writes.length, 1)
  assert.equal(writes[0].id, 'project-a')
  assert.deepEqual(Array.from(writes[0].payload.projectManagerIds), ['old', 'new', 'other'])
  assert.equal(writes[0].payload.expectedUpdatedAt, '2026-10-22T12:00:00+08:00')
  assert.equal(writes[0].payload.reason, '增加项目协作经理')
  assert.equal('clientManagerId' in writes[0].payload, false)
  assert.deepEqual(signals, ['project-a'])
})

test('版本冲突后要求重新加载，不覆盖别人修改、不发送成功同步信号', async () => {
  const { api, writes, signals } = harness({ failSave: true })
  await api.load(); api.form.managerIds = ['new']; api.form.reason = '协作'
  await api.save()
  assert.equal(api.loaded.value, false)
  assert.match(api.error.value, /重新加载/)
  assert.equal(signals.length, 0); assert.equal(writes.length, 0)
})

test('首次分配免原因，清空过经理但有分配历史时仍要求原因', async () => {
  for (const history of [false, true]) {
    const { api } = harness({ detail: { id: 'child-order', roleAssignments: [], managerAssignmentHistory: { project_manager: history }, updatedAt: '2026-10-22T12:00:00+08:00' } })
    await api.load(); assert.equal(api.requiresReason.value, history)
  }
})

test('窗口未读或加载失败时不能提交未知项目版本', async () => {
  const { api, writes } = harness()
  api.form.managerIds = ['new']; await api.save()
  assert.equal(writes.length, 0)
})

test('移除经理及清空全部经理提交真实的剩余名单，未修改时不写库', async () => {
  for (const remaining of [['new'], []]) {
    const { api, writes, signals } = harness()
    await api.load(); await api.save()
    assert.equal(writes.length, 0)
    api.form.managerIds = remaining; api.form.reason = '调整负责人'
    await api.save()
    assert.deepEqual(Array.from(writes[0].payload.projectManagerIds), remaining)
    assert.deepEqual(signals, ['project-a'])
  }
})

test('客户经理可替换或移除，只提交客户经理字段，保留项目经理', async () => {
  for (const selected of ['new', '']) {
    const { api, writes } = harness({ managerRole: 'client_manager', detail: {
      id: 'project-a', clientManagerId: 'old', roleAssignments: [{roleCode:'project_manager',assigneeId:'other'}], updatedAt: '2026-10-22T12:00:00+08:00',
    } })
    await api.load()
    assert.equal(api.form.clientManagerId, 'old')
    assert.equal(api.requiresReason.value, true)
    api.form.clientManagerId = selected; api.form.reason = '客户经理调整'
    await api.save()
    assert.equal(writes[0].payload.clientManagerId, selected || null)
    assert.equal('projectManagerIds' in writes[0].payload, false)
  }
})

test('同页与其他标签页收到项目经理变更后刷新，注销后不再触发', () => {
  const sync = readFileSync(new URL('../src/utils/annotationManagerSync.js', import.meta.url), 'utf8').replaceAll('export ', '')
  const listeners = new Map(), events = [], stored = []
  const win = { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name), dispatchEvent: event => listeners.get(event.type)?.(event) }
  const api = runInNewContext(sync + ';({notifyAnnotationManagersUpdated,subscribeAnnotationManagersUpdated})', {
    window: win, localStorage: { setItem: (key, value) => stored.push({ key, value }) }, CustomEvent: class { constructor(type, { detail }) { this.type = type; this.detail = detail } },
  })
  const stop = api.subscribeAnnotationManagersUpdated(id => events.push(id))
  api.notifyAnnotationManagersUpdated('project-a')
  listeners.get('storage')({ key: stored[0].key, newValue: JSON.stringify({ projectId: 'project-b' }) })
  assert.deepEqual(events, ['project-a', 'project-b'])
  stop(); assert.equal(listeners.size, 0)
})
