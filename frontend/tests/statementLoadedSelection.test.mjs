import test from 'node:test'
import assert from 'node:assert/strict'
import { loadedStatementOrderIds } from '../src/utils/statementLoadedSelection.js'

function context(extra = {}) {
  return { rows: [{ id: 'a', statementRequired: true }, { id: 'b', statementRequired: false },
    { id: 'c', statementRequired: false, hasStatementRequiredOrders: true }], total: 3,
    loadedQuery: { billing_month: '2026-11', client_id: 'customer' },
    currentQuery: { billing_month: '2026-11', client_id: 'customer' }, months: ['2026-11'], ...extra }
}
test('complete customer list supplies the same root IDs and required-order scope', () => {
  assert.deepEqual(loadedStatementOrderIds(context()), ['a', 'b', 'c'])
  assert.deepEqual(loadedStatementOrderIds(context({ requireStatement: true })), ['a', 'c'])
  assert.deepEqual(loadedStatementOrderIds(context({ rows: [], total: 0 })), [])
})
test('incomplete, outdated or different-month lists require a fresh query', () => {
  for (const extra of [{ total: 4 }, { loadedQuery: null }, { months: ['2026-10'] },
    { months: ['2026-11', '2026-12'] }, { currentQuery: { client_id: 'other' } }]) {
    assert.equal(loadedStatementOrderIds(context(extra)), null)
  }
  const query = { billing_month: '2026-11', statement_required: false }
  assert.equal(loadedStatementOrderIds(context({ loadedQuery: query, currentQuery: query, requireStatement: true })), null)
})
