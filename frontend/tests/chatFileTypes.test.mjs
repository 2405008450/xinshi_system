import test from 'node:test'
import assert from 'node:assert/strict'
import { chatFileCategory, chatFileMaxBytes, chatFileAccept, chatClipboardFiles } from '../src/utils/chatFileTypes.js'
test('音视频按扩展名分类且大小上限100MiB，不依赖浏览器MIME', () => {
  for (const ext of ['MP4', 'mp3', 'wav', 'm4a', 'webm']) {
    assert.equal(chatFileCategory('中文文件.' + ext), 'media')
    assert.equal(chatFileMaxBytes('中文文件.' + ext), 100 * 1024 * 1024)
    assert.ok(chatFileAccept.includes('.' + ext.toLowerCase()))
  }
  assert.equal(chatFileMaxBytes('截图.PNG'), 10 * 1024 * 1024)
  assert.equal(chatFileMaxBytes('报告.pdf'), 20 * 1024 * 1024)
})

test('粘贴读取全部类型附件，files与items同时存在时不重复', () => {
  const files = [{ name: '视频.mp4' }, { name: '音频.mp3' }, { name: '文档.pdf' }, { name: '截图.png' }]
  const clipboard = { files, items: files.map(file => ({ kind: 'file', getAsFile: () => file })) }
  assert.deepEqual(chatClipboardFiles(clipboard), files)
  assert.deepEqual(chatClipboardFiles({ files: [], items: clipboard.items }), files)
})
test('纯文字及不可读取的剪贴板项不会创建附件', () => {
  assert.deepEqual(chatClipboardFiles(null), [])
  assert.deepEqual(chatClipboardFiles({ items: [{ kind: 'string' }, { kind: 'file', getAsFile: () => null }] }), [])
})
