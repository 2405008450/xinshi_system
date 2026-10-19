import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ERROR_ITEM_SELECTOR,
  FOCUSABLE_CONTROL_SELECTOR,
  focusFirstInvalidField,
} from '../src/utils/formValidation.js'

test('定位、滚动并聚焦第一个校验失败字段', async () => {
  const calls = []
  const control = {
    getAttribute: () => null,
    focus: (options) => calls.push(['focus', options]),
  }
  const errorItem = {
    scrollIntoView: (options) => calls.push(['scroll', options]),
    querySelector: (selector) => {
      assert.equal(selector, FOCUSABLE_CONTROL_SELECTOR)
      return control
    },
  }
  const form = {
    querySelector: (selector) => {
      assert.equal(selector, ERROR_ITEM_SELECTOR)
      return errorItem
    },
  }

  assert.equal(await focusFirstInvalidField(form), true)
  assert.deepEqual(calls, [
    ['scroll', { behavior: 'smooth', block: 'center', inline: 'nearest' }],
    ['focus', { preventScroll: true }],
  ])
})

test('表单没有错误字段时不滚动、不聚焦', async () => {
  const form = { querySelector: () => null }
  assert.equal(await focusFirstInvalidField(form), false)
})

test('字段标签包含下拉框时，校验错误仍聚焦正文输入框', async () => {
  const focused = []
  const auxiliary = { getAttribute: () => null, focus: () => focused.push('label-select') }
  const textarea = { getAttribute: () => null, focus: () => focused.push('textarea') }
  const content = { querySelector: () => textarea }
  const errorItem = {
    matches: (selector) => selector === '.el-form-item',
    querySelector: (selector) => selector === '.el-form-item__content' ? content : auxiliary,
    scrollIntoView() {},
  }
  assert.equal(await focusFirstInvalidField({ querySelector: () => errorItem }), true)
  assert.deepEqual(focused, ['textarea'])
})

test('错误项只有不可聚焦控件时仍完成滚动定位', async () => {
  let scrolled = false
  const errorItem = {
    scrollIntoView: () => { scrolled = true },
    querySelector: () => null,
  }
  const form = { querySelector: () => errorItem }

  assert.equal(await focusFirstInvalidField(form), true)
  assert.equal(scrolled, true)
})

test('下拉和日期控件的 readonly 输入框仍属于可聚焦目标', () => {
  assert.match(FOCUSABLE_CONTROL_SELECTOR, /input:not\(\[disabled\]\)/)
  assert.doesNotMatch(FOCUSABLE_CONTROL_SELECTOR, /input[^,]*readonly/)
})
