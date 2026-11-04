import assert from 'node:assert/strict'
import test from 'node:test'
import {currentStatementMonth,previousStatementMonth} from '../src/utils/statementRequirementMonth.js'
import {applyStatementRequirementResult} from '../src/utils/statementRequirementSync.js'

test('上个月跨年和本月格式',()=>{
  assert.equal(previousStatementMonth('2026-01'),'2025-12')
  assert.equal(previousStatementMonth('2026-11'),'2026-10')
  assert.match(currentStatementMonth(),/^\d{4}-(0[1-9]|1[0-2])$/)
})

test('子窗口同步字段，同版本推进主表单，旧版本保留并继续阻止覆盖',()=>{
  const result={statementRequired:false,previousUpdatedAt:'2026-11-04T09:00:00+08:00',updatedAt:'2026-11-04T09:01:00+08:00'}
  const fresh={statementRequired:true,updatedAt:'2026-11-04 09:00:00'}
  applyStatementRequirementResult(fresh,result)
  assert.equal(fresh.statementRequired,false)
  assert.equal(fresh.updatedAt,result.updatedAt)
  const stale={statementRequired:true,updatedAt:'2026-11-04T08:00:00+08:00'}
  applyStatementRequirementResult(stale,result)
  assert.equal(stale.statementRequired,false)
  assert.equal(stale.updatedAt,'2026-11-04T08:00:00+08:00')
})
