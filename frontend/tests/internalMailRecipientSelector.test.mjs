import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { normalizeDepartment } from '../src/constants/departments.js'
import { matchesSearchFields } from '../src/utils/searchMatching.js'

const source = readFileSync(new URL('../src/components/common/InternalMailRecipientSelector.vue', import.meta.url), 'utf8')
  .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const users = [
  { id: 'a', full_name: '测试甲', email: 'a@example.test', is_active: true, department: 'IT部' },
  { id: 'b', full_name: '测试乙', email: 'b@example.test', is_active: true, department: '项目部' },
]

function setup(t, initialUsers) {
  const props = reactive({ users: initialUsers, modelValue: [], excludedUserIds: [], groups: [] })
  const scope = effectScope()
  t.after(() => scope.stop())
  const context = vm.createContext({
    computed, ref, watch, normalizeDepartment, matchesSearchFields,
    defineProps: () => props,
    defineEmits: () => (_, ids) => { props.modelValue = ids },
    // 本测试只执行真实 setup 和响应式逻辑，不挂载 DOM 拖拽事件。
    onBeforeUnmount() {},
  })
  const state = scope.run(() => vm.runInContext(`${source}\n;({ availableUsers, departmentGroups, selectedIds, filteredUsers, selectFiltered, clearSelected, selectDepartment })`, context))
  return { props, state }
}

test('咨询确认时成员已加载：收件人初始化、部门筛选及选择均正常', async (t) => {
  const { state } = setup(t, users)
  assert.equal(state.availableUsers.value.length, 2)
  assert.equal(state.departmentGroups.value.length, 2)
  state.selectDepartment('IT部')
  assert.equal(state.filteredUsers.value.length, 1)
  state.selectFiltered()
  await nextTick()
  assert.deepEqual(Array.from(state.selectedIds.value), ['a'])
  state.clearSelected()
  assert.equal(state.selectedIds.value.length, 0)
})

test('成员异步加载及抄送排除已选收件人仍正常', async (t) => {
  const { props, state } = setup(t, [])
  assert.equal(state.availableUsers.value.length, 0)
  props.users = users
  await nextTick()
  state.selectFiltered()
  assert.equal(state.selectedIds.value.length, 2)
  props.excludedUserIds = ['a']
  await nextTick()
  assert.deepEqual(Array.from(state.selectedIds.value), ['b'])
})
