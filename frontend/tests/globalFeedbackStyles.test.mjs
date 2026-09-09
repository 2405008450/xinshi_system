import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const mainEntry = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')

test('全局反馈组件显式加载样式，避免提示框和按钮失去定位', () => {
  for (const stylesheet of [
    'element-plus/theme-chalk/el-message.css',
    'element-plus/theme-chalk/el-message-box.css',
    'element-plus/theme-chalk/el-notification.css',
  ]) {
    assert.match(mainEntry, new RegExp(`import ['"]${stylesheet.replaceAll('/', '\\/')}['"]`))
  }
})
