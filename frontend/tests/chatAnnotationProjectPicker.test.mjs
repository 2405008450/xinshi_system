import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { annotationStatusLabels, normalizeAnnotationStatus } from '../src/utils/annotationStatus.js'

const picker = readFileSync(new URL('../src/components/chat/ChatAnnotationProjectPicker.vue', import.meta.url), 'utf8')
function harness({ permitted = true, sessions = [], request, refresh } = {}) {
  const calls = [], events = [], state = { value: sessions }
  const context = {
    defineAsyncComponent: () => ({}), defineProps: () => ({ modelValue: true, favoriteMode: true }), defineEmits: () => (...args) => events.push(args),
    ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }), watch: () => {},
    hasPermission: () => permitted, annotationStatusLabels, normalizeAnnotationStatus,
    getAnnotationProject: async id => ({ id, projectStatus: 'project_in_progress' }),
    useAnnotationFollowed: () => ({ sessions: state, refresh: async () => refresh?.(state) }),
    annotationChatRequest: (...args) => { calls.push(args); return request ? request(...args) : Promise.resolve({ following: true }) },
  }
  const script = picker.match(/<script setup>([\s\S]+?)<\/script>/)[1].replace(/^import .+\r?\n/gm, '')
  const api = runInNewContext(script + '\n;({join, joinedIds, joining, error, feedback})', context)
  return { ...api, calls, events, state }
}
test('加入调用当前项目关注接口，重新读取项目状态归类，重复加入不重复请求', async () => {
  const api = harness({ refresh: state => { state.value = [{ kind: 'annotation', projectId: 'p1', following: true, projectStatus: 'project_in_progress' }] } })
  await api.join({ id: 'p1', projectName: '项目A', projectStatus: 'trial_preparation' })
  assert.equal(api.calls.length, 2)
  assert.equal(api.calls[0][0], 'p1')
  assert.equal(api.calls[0][1], 'start')
  assert.equal(api.calls[0][2].method, 'post')
  assert.equal(api.calls[1][1], 'following')
  assert.equal(api.calls[1][2].data.following, true)
  assert.equal(api.events[0][0], 'joined')
  assert.equal(api.events[0][1].projectStatus, 'project_in_progress')
  assert.match(api.feedback.value, /项目进行中/)
  await api.join({ id: 'p1' })
  assert.equal(api.calls.length, 2)
})
test('禁止无权限、已加入和进行中的重复请求；失败后保留重试能力', async () => {
  const denied = harness({ permitted: false })
  await denied.join({ id: 'p1' }); assert.equal(denied.calls.length, 0)
  const existing = harness({ sessions: [{ kind: 'annotation', projectId: 'p1', following: true }] })
  await existing.join({ id: 'p1' }); assert.equal(existing.calls.length, 0)
  let reject
  const api = harness({ request: () => new Promise((_, fail) => { reject = fail }) })
  const pending = api.join({ id: 'p1' })
  await Promise.resolve()
  await api.join({ id: 'p1' }); assert.equal(api.calls.length, 1)
  reject({ detail: '没有查看权限' }); await pending
  assert.equal(api.error.value, '没有查看权限')
  assert.equal(api.joinedIds.value.includes('p1'), false)
  assert.equal(api.joining.value.size, 0)
  assert.equal(api.events.length, 0)
})
test('加入后工作区显示对应状态分类并清空原搜索词；未知状态回到一级分组', () => {
  const workspace = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')
  const script = workspace.slice(workspace.indexOf('function joinedAnnotation('), workspace.indexOf('\nconst currentGroupLabel'))
  const selected = [], context = {
    keyword: { value: '旧搜索' }, applyKeyword: () => {}, annotationMode: { value: 'mention' }, pane: { value: 'contacts' },
    normalizeAnnotationStatus, folderNodes: { value: [{ id: 'status:project_in_progress' }] }, annotationFolderId: 'annotation',
    selectFolder: id => selected.push(id), emit: () => {},
  }
  runInNewContext(script + '; joinedAnnotation({projectStatus:"projectInProgress"})', context)
  assert.equal(selected[0], 'status:project_in_progress')
  assert.equal(context.keyword.value, '')
  assert.equal(context.annotationMode.value, 'group')
  runInNewContext(script + '; joinedAnnotation({projectStatus:"unknown"})', context)
  assert.equal(selected[1], 'annotation')
})
