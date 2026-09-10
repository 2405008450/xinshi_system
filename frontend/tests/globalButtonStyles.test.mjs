import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const appStyles = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')

test('全局主按钮样式不覆盖 plain、link、text 和 disabled 状态', () => {
  assert.doesNotMatch(appStyles, /\.el-button--primary\s*\{/)

  const solidPrimarySelector =
    '.el-button--primary:not(.is-plain):not(.is-link):not(.is-text):not(.is-disabled)'

  assert.match(appStyles, new RegExp(`${solidPrimarySelector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{`))
  assert.match(appStyles, /background-color:\s*var\(--color-primary\)/)
})
