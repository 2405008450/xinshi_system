import test from 'node:test'
import assert from 'node:assert/strict'
import { matchesSearch, matchesSearchFields, searchTerms } from '../src/utils/searchMatching.js'

test('多关键词包含匹配：连写、分隔、反向、大小写和各种空白', () => {
  for (const text of ['AABB', 'AAA BBB', 'BB / aa']) assert.equal(matchesSearch(text, ' AA　BB '), true)
  assert.equal(matchesSearch('only AA', 'AA BB'), false)
  assert.equal(matchesSearch(null, ' \t '), true)
  assert.deepEqual(searchTerms('AA aa\tBB'), ['aa', 'bb'])
  assert.equal(matchesSearchFields(['客户AA', '联系人BB'], 'AA BB'), true)
})
test('百分号、下划线、反斜杠和正则符号是字面文本', () => {
  assert.equal(matchesSearch('100%_\\abc [x]', '% _ \\ [x]'), true)
  assert.equal(matchesSearch('100xxx', '% _'), false)
})
