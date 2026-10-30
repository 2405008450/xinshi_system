import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const source = (await readFile(new URL('../src/utils/technicalDevelopment.js', import.meta.url), 'utf8')).replace("'./searchMatching'", JSON.stringify(new URL('../src/utils/searchMatching.js', import.meta.url).href))
const { canMoveTask, taskTree } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const rows = [{ id: 'a', parent_id: null, name: 'A' }, { id: 'b', parent_id: 'a', name: 'B', content: '中文 90%' }, { id: 'c', parent_id: 'b', name: 'C' }, { id: 'd', parent_id: null, name: 'D' }]
test('dragging checks the entire subtree, cycles and missing targets', () => {
  assert.equal(canMoveTask(rows, 'a', 'c'), false)
  assert.equal(canMoveTask(rows, 'a', 'd'), false)
  assert.equal(canMoveTask(rows, 'b', 'b'), false)
  assert.equal(canMoveTask(rows, 'b', 'd'), true)
  assert.equal(canMoveTask(rows, 'b', null), true)
  assert.equal(canMoveTask(rows, 'd', 'missing'), false)
})
test('search preserves ancestors and children, with literal multi-keyword matching', () => {
  const filtered = taskTree(rows, '90% 中文')
  assert.equal(filtered.length, 1)
  assert.equal(filtered[0].name, 'A')
  assert.equal(filtered[0].children[0].name, 'B')
  assert.equal(filtered[0].children[0].children[0].level, 3)
  assert.equal(taskTree(rows, '90_').length, 0)
  assert.equal(taskTree(rows, '').length, 2)
})
