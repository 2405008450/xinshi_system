import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { reactive, ref, watch, nextTick } from 'vue'

const source = readFileSync(new URL('../src/components/chat/ChatSessionFolderTree.vue', import.meta.url), 'utf8')
test('目录更新不抢占滚动且保留展开状态', () => {
  assert.equal(source.includes('()=>reveal()'), false)
  assert.equal(source.includes('if (active) expanded.value = new Set()'), false)
  assert.ok(source.includes('expanded: [...expanded.value]'))
})
