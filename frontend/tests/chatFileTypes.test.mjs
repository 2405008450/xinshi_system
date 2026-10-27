import test from 'node:test'
import assert from 'node:assert/strict'
import { chatFileCategory, chatFileMaxBytes, chatFileAccept } from '../src/utils/chatFileTypes.js'
test('音视频按扩展名分类且大小上限100MiB，不依赖浏览器MIME', () => {
  for (const ext of ['MP4', 'mp3', 'wav', 'm4a', 'webm']) {
    assert.equal(chatFileCategory('中文文件.' + ext), 'media')
    assert.equal(chatFileMaxBytes('中文文件.' + ext), 100 * 1024 * 1024)
    assert.ok(chatFileAccept.includes('.' + ext.toLowerCase()))
  }
  assert.equal(chatFileMaxBytes('截图.PNG'), 10 * 1024 * 1024)
  assert.equal(chatFileMaxBytes('报告.pdf'), 20 * 1024 * 1024)
})
