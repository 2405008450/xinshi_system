import assert from 'node:assert/strict'
import test from 'node:test'
import {
  insertScreenshot, screenshotEditorText, screenshotParts, updateScreenshotText,
} from '../src/utils/screenshotReferences.js'

const first = '00000000-0000-4000-8000-000000000001'
const second = '00000000-0000-4000-8000-000000000002'
const reference = id => `screenshot://${id}#${'a'.repeat(64)}`

test('保留每段说明和插入截图的先后顺序', () => {
  const text = '第一段\n第二段'
  const withFirst = insertScreenshot(text, reference(first), 3)
  const withBoth = insertScreenshot(withFirst, reference(second))
  const edited = updateScreenshotText(withBoth, '第一段▧\n修订第二段▧')
  assert.deepEqual(screenshotParts(edited).map(part => part.id || part.text), [
    '第一段', first, '\n修订第二段', second,
  ])
  assert.equal(screenshotEditorText(edited), '第一段▧\n修订第二段▧')
})

test('相邻的截图标记按选区删除对应截图', () => {
  const both = insertScreenshot(insertScreenshot('', reference(first)), reference(second))
  const edited = updateScreenshotText(both, '▧', { value: '▧▧', start: 0, end: 1 })
  assert.deepEqual(screenshotParts(edited).map(part => part.id), [second])
})
