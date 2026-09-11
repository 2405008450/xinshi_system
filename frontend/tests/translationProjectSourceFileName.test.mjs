import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('母订单文件名称独立于自动生成的项目名称保存', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')

  assert.match(source, /label="文件名称" data-field-key="sourceFileName"/)
  assert.match(source, /v-model="form\.sourceFileName"/)
  assert.match(source, /sourceFileName: ''/)
  assert.match(source, /label: '文件名称', key: 'sourceFileName'/)
  assert.match(source, /key: 'sourceFileName', label: '文件名称', type: 'text'/)
  assert.match(source, /NULLABLE_FIELDS = \['sourceFileName'/)
})

test('列表关键词提示覆盖文件名称', () => {
  const source = read('src/views/project/translation/ProjectDetails.vue')

  assert.match(source, /placeholder="母\/子订单号、项目名称、文件名称、客户名称或客户单号"/)
})
