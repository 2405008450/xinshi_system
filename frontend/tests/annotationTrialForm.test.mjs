import assert from 'node:assert/strict'
import test from 'node:test'
import { conversionPercent, conversionRate, trialFormValues, trialRules, trialPayload, customFieldRules } from '../src/utils/annotationTrialForm.js'

const validate = (rule, value) => new Promise(resolve => rule.validator(rule, value, resolve))

test('人数策略保留低于1%的合法转化率及四位接口精度', () => {
  for (const rate of [0.0001, 0.005, 0.1234, 1]) assert.equal(conversionRate(conversionPercent(String(rate))), rate)
})

test('真实接口 Decimal 字符串回显后可以直接编辑保存，草稿不污染列表值', async () => {
  const row = { quoteAmount: '12.123456', customValues: { a: '原值' } }
  const form = trialFormValues(row)
  assert.equal(form.quoteAmount, 12.123456)
  assert.equal(await validate(trialRules({}).quoteAmount[0], form.quoteAmount), undefined)
  form.customValues.a = '未保存'
  assert.equal(row.customValues.a, '原值')
  assert.equal(trialFormValues({ quoteAmount: null }).quoteAmount, null)
})

test('报价与结果说明按条件标记必填，零报价不能保存', async () => {
  assert.equal(trialRules({ billingUnit: 'item' }).quoteAmount[0].required, true)
  assert.equal(trialRules({ quoteAmount: 10 }).billingUnit[0].required, true)
  assert.equal(trialRules({ quoteAmount: null }).billingUnit.length, 0)
  assert.equal(trialRules({ trialResult: 'partially_passed' }).resultNote[0].whitespace, true)
  assert.equal(trialRules({ trialResult: 'passed' }).resultNote.length, 0)
  assert.match((await validate(trialRules({}).quoteAmount[0], 0)).message, /大于 0/)
})

test('轮次、评分和时间范围与后端一致', async () => {
  const rules = trialRules({ startedAt: '2026-09-28 10:00:00' })
  for (const value of [null, 0, 1.5]) assert.ok(await validate(rules.roundNo[1], value))
  assert.equal(await validate(rules.roundNo[1], 2), undefined)
  assert.ok(await validate(rules.overallScore[0], 2.5))
  assert.equal(await validate(rules.overallScore[0], null), undefined)
  assert.ok(await validate(rules.deadlineAt[0], '2026-09-28 09:00:00'))
})

test('自定义必填字段拒绝空白和空数组，但接受 false 与 0', async () => {
  const rule = customFieldRules({ isRequired: true, fieldLabel: '测试字段' })[0]
  for (const value of [null, '', '  ', []]) assert.ok(await validate(rule, value))
  for (const value of [false, 0, '已填写']) assert.equal(await validate(rule, value), undefined)
})

test('清空可选字段发送 null，不修改原表单', () => {
  const form = { id: 'record', sequenceNo: 1, billingUnit: '', trialResult: '', platformAccountId: '', quoteAmount: null }
  const payload = trialPayload(form)
  assert.equal(payload.billingUnit, null)
  assert.equal(payload.trialResult, null)
  assert.equal(payload.platformAccountId, null)
  assert.equal('id' in payload, false)
  assert.equal('sequenceNo' in payload, false)
  assert.equal(form.billingUnit, '')
})
