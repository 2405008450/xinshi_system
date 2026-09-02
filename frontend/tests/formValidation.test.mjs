import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ERROR_ITEM_SELECTOR,
  FOCUSABLE_CONTROL_SELECTOR,
  focusFirstInvalidField,
} from '../src/utils/formValidation.js'

test('定位、滚动并聚焦第一个校验失败字段', () => {
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

  assert.equal(focusFirstInvalidField(form), true)
  assert.deepEqual(calls, [
    ['scroll', { behavior: 'smooth', block: 'center', inline: 'nearest' }],
    ['focus', { preventScroll: true }],
  ])
})

test('表单没有错误字段时不滚动、不聚焦', () => {
  const form = { querySelector: () => null }
  assert.equal(focusFirstInvalidField(form), false)
})

test('错误项只有不可聚焦控件时仍完成滚动定位', () => {
  let scrolled = false
  const errorItem = {
    scrollIntoView: () => { scrolled = true },
    querySelector: () => null,
  }
  const form = { querySelector: () => errorItem }

  assert.equal(focusFirstInvalidField(form), true)
  assert.equal(scrolled, true)
})

test('下拉和日期控件的 readonly 输入框仍属于可聚焦目标', () => {
  assert.match(FOCUSABLE_CONTROL_SELECTOR, /input:not\(\[disabled\]\)/)
  assert.doesNotMatch(FOCUSABLE_CONTROL_SELECTOR, /input[^,]*readonly/)
})
