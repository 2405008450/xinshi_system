import assert from 'node:assert/strict'
import test from 'node:test'
import { projectQuantityChoices, resolveRateQuantity, rateQuantityOptions, validQuantityBasis, calculateOrderPriceTree } from '../src/utils/translationQuantityBasis.js'

test('计价方式仅列出已填写的客户/我司统计，保留零值并排除预统计', () => {
  const matrix = { customer: { words: 100, foreign_words: 0 }, company: { pages: 2 }, preliminary: { words: 900 } }
  const choices = projectQuantityChoices(matrix)
  assert.deepEqual(choices.map(row => row.value), ['customer_auto:words', 'customer_auto:foreign_words', 'company_pages'])
  assert.equal(resolveRateQuantity(matrix, choices[1].value).quantity, 0)
  assert.equal(resolveRateQuantity(matrix, choices[2].value).quantity, 2)
})

test('未填写不能生成计价项；唯一已填写项可直接采用', () => {
  assert.deepEqual(projectQuantityChoices({}), [])
  const matrix = { company: { charactersNoSpaces: 250 } }
  const [choice] = projectQuantityChoices(matrix)
  assert.equal(choice.value, 'company_characters_no_spaces')
  assert.equal(resolveRateQuantity(matrix, choice.value).quantity, 250)
})

test('缺少数量仍可选择口径，历史口径保留，预统计不计价', () => {
  const options=rateQuantityOptions({},'words')
  for(const mode of ['customer_auto','customer_auto:words','company_pages','words']){
    assert.ok(options.some(option=>option.value===mode))
    assert.ok(validQuantityBasis(mode))
  }
  assert.equal(validQuantityBasis(''),false)
  assert.equal(validQuantityBasis('preliminary_words'),false)
  assert.equal(resolveRateQuantity({preliminary:{words:100}},'customer_auto').quantity,null)
})

test('明确口径缺失时不改用其他数量，自动口径仍可取唯一栏', () => {
  const matrix={customer:{pages:5}}
  assert.equal(resolveRateQuantity(matrix,'customer_auto:words').quantity,null)
  assert.equal(resolveRateQuantity(matrix,'customer_auto:words').metric,'words')
  assert.equal(resolveRateQuantity(matrix,'customer_auto').quantity,5)
  const order={wordCountMatrix:matrix,prices:[{languagePair:'英→中',metric:'customer_auto:words',amount:200,unitSize:1000,currency:'CNY'}]}
  assert.equal(calculateOrderPriceTree(order).incomplete,true)
  order.wordCountMatrix.customer.words=1000
  assert.deepEqual(calculateOrderPriceTree(order).totals,{CNY:'200.00'})
})
