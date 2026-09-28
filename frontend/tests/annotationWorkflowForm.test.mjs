import assert from 'node:assert/strict'
import test from 'node:test'
import { workflowFormValues, workflowRules } from '../src/utils/annotationWorkflowForm.js'
import { customFieldRules } from '../src/utils/annotationCustomFieldRules.js'

const validate = (rule, value) => new Promise(resolve => rule.validator(rule, value, resolve))

test('正式安排回显 Decimal 字符串，保留零时长与可选空值', async () => {
  const form = workflowFormValues({ amount: '12.123456', unit: 'item', audioDurationValue: '0.000', audioDurationUnit: 'hour' })
  assert.equal(form.amount, 12.123456)
  assert.equal(form.audioDurationValue, 0)
  assert.equal(await validate(workflowRules(form).amount[0], form.amount), undefined)
  assert.equal(workflowFormValues({ amount: null }).amount, null)
})

test('正式安排可以不报价，填写报价时金额必须大于零且具备单位', async () => {
  assert.equal(await validate(workflowRules({}).amount[0], null), undefined)
  assert.ok(await validate(workflowRules({}).amount[0], 10))
  assert.ok(await validate(workflowRules({ unit: 'item' }).amount[0], 0))
  assert.ok(await validate(workflowRules({ unit: 'item' }).amount[0], null))
  assert.equal(await validate(workflowRules({ unit: 'item' }).amount[0], 10), undefined)
})

test('音频长度允许零，但不能遗漏单位或填入负数', async () => {
  assert.equal(await validate(workflowRules({ audioDurationUnit: 'hour' }).audioDurationValue[0], 0), undefined)
  assert.ok(await validate(workflowRules({}).audioDurationValue[0], 0))
  assert.ok(await validate(workflowRules({ audioDurationUnit: 'hour' }).audioDurationValue[0], -1))
})

test('自定义字段支持零和 false 选项并拒绝过期选项', async () => {
  const rule = customFieldRules({ dataType: 'single_select', fieldLabel: '选项', isRequired: true, options: [{ value: 0 }, { value: false }] })[0]
  assert.equal(await validate(rule, 0), undefined)
  assert.equal(await validate(rule, false), undefined)
  assert.ok(await validate(rule, '失效值'))
  assert.ok(await validate(customFieldRules({ dataType: 'number', fieldLabel: '数量' })[0], Infinity))
})
