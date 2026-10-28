import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { reactive, ref, watch, nextTick } from 'vue'

const source = readFileSync(new URL('../src/components/chat/ChatSessionFolderTree.vue', import.meta.url), 'utf8')
const navigationWatch = source.split('\n').find(line => line.startsWith('watch(') && line.includes('()=>reveal()'))

function observeSelection() {
  const props = reactive({ selected: 'selected' })
  const nodes = ref([{ id: 'selected' }])
  let calls = 0
  const stop = runInNewContext(navigationWatch, { props, nodes, watch, reveal: () => calls++ })
  return { props, nodes, stop, calls: () => calls }
}

test('分组轮询替换数据及新增无关分组时，不重复定位打断手动滚动', async () => {
  const state = observeSelection()
  try {
    assert.equal(state.calls(), 1)
    state.nodes.value = [{ id: 'selected' }]
    await nextTick()
    state.nodes.value = [{ id: 'selected' }, { id: 'other' }]
    await nextTick()
    assert.equal(state.calls(), 1)
  } finally { state.stop() }
})

test('用户切换选择以及所选分组延迟加载完成时，仍正常定位', async () => {
  const state = observeSelection()
  try {
    state.props.selected = 'later'
    await nextTick()
    assert.equal(state.calls(), 2)
    state.nodes.value = [{ id: 'selected' }, { id: 'later' }]
    await nextTick()
    assert.equal(state.calls(), 3)
    state.nodes.value = state.nodes.value.map(row => ({ ...row }))
    await nextTick()
    assert.equal(state.calls(), 3)
  } finally { state.stop() }
})
