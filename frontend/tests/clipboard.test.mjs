import test from 'node:test'
import assert from 'node:assert/strict'

import { copyTextToClipboard } from '../src/utils/clipboard.js'

const createLegacyDocument = ({ copyResult = true, throwOnCopy = false } = {}) => {
  const calls = []
  const textarea = {
    style: {},
    setAttribute: (...args) => calls.push(['setAttribute', ...args]),
    focus: () => calls.push(['focus']),
    select: () => calls.push(['select']),
    setSelectionRange: (...args) => calls.push(['setSelectionRange', ...args]),
    remove: () => calls.push(['remove']),
  }
  const documentRef = {
    body: { appendChild: (element) => calls.push(['appendChild', element]) },
    createElement: (tag) => {
      calls.push(['createElement', tag])
      return textarea
    },
    execCommand: (command) => {
      calls.push(['execCommand', command])
      if (throwOnCopy) throw new Error('copy denied')
      return copyResult
    },
  }
  return { calls, documentRef, textarea }
}

test('优先使用现代 Clipboard API', async () => {
  const copiedValues = []
  const clipboard = { writeText: async (value) => copiedValues.push(value) }

  assert.equal(await copyTextToClipboard('\\\\server\\source', { clipboard }), true)
  assert.deepEqual(copiedValues, ['\\\\server\\source'])
})

test('Clipboard API 被拒绝时降级到传统复制方式', async () => {
  const clipboard = { writeText: async () => { throw new Error('not allowed') } }
  const { calls, documentRef, textarea } = createLegacyDocument()

  assert.equal(await copyTextToClipboard('\\\\server\\dispatch', { clipboard, documentRef }), true)
  assert.equal(textarea.value, '\\\\server\\dispatch')
  assert.deepEqual(calls.filter(([name]) => ['execCommand', 'remove'].includes(name)), [
    ['execCommand', 'copy'],
    ['remove'],
  ])
})

test('传统复制失败时返回 false 并清理临时文本框', async () => {
  const { calls, documentRef } = createLegacyDocument({ throwOnCopy: true })

  assert.equal(await copyTextToClipboard('\\\\server\\source', { clipboard: null, documentRef }), false)
  assert.equal(calls.some(([name]) => name === 'remove'), true)
})

test('空文本不写入剪贴板', async () => {
  const clipboard = { writeText: async () => { throw new Error('不应调用') } }

  assert.equal(await copyTextToClipboard('', { clipboard }), false)
})
