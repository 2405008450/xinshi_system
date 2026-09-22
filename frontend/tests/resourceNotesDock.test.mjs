import assert from 'node:assert/strict'
import test from 'node:test'
import { useResourceNotesDock } from '../src/composables/useResourceNotesDock.js'

test('不同页面共享同一个说明窗口，重复打开和恢复不创建新窗口', () => {
  const firstPage = useResourceNotesDock()
  const secondPage = useResourceNotesDock()
  firstPage.closeNotes()
  firstPage.openNotes()
  firstPage.minimizeNotes()
  assert.equal(secondPage.state.open, true)
  assert.equal(secondPage.state.minimized, true)
  secondPage.openNotes()
  assert.equal(firstPage.state.minimized, false)
  assert.equal(firstPage.state, secondPage.state)
  secondPage.closeNotes()
})

test('退出公共布局清理窗口状态，关闭后不能再次最小化出幽灵入口', () => {
  const dock = useResourceNotesDock()
  dock.openNotes()
  dock.minimizeNotes()
  dock.closeNotes()
  dock.minimizeNotes()
  assert.deepEqual({ ...dock.state }, { open: false, minimized: false })
})
