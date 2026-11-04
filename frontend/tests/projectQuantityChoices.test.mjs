import assert from 'node:assert/strict'
import test from 'node:test'
import { projectQuantityChoices, resolveRateQuantity } from '../src/utils/translationQuantityBasis.js'

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
