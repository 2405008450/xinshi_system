import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeForeignLanguagePriorities, languageRoleLabel } from '../src/utils/talentLanguageSkills.js'

test('未明确的外语顺序在加载、反复编辑与序列化后仍为0', () => {
  const original = [{ role: 'foreign', priority: 0 }, { role: 'foreign', priority: 0 }]
  const loaded = normalizeForeignLanguagePriorities(original)
  const saved = JSON.parse(JSON.stringify(normalizeForeignLanguagePriorities(loaded)))
  assert.deepEqual(saved, original)
  assert.equal(languageRoleLabel(saved[0]), '外语（顺序未明确）')
  assert.notEqual(loaded[0], original[0])
})

test('明示顺序与重复顺序均不被重新推定，非法值只归零', () => {
  const rows = [2, 2, '1', null, '', false, '1.5', 10, -1, undefined].map(priority => ({ role: 'foreign', priority }))
  assert.deepEqual(normalizeForeignLanguagePriorities(rows).map(row => row.priority), [2, 2, 1, 0, 0, 0, 0, 0, 0, 0])
  assert.equal(languageRoleLabel(rows[0]), '第2外语')
  assert.equal(languageRoleLabel({ role: 'native' }), '母语')
})
