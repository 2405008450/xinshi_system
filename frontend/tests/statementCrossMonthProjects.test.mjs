import test from 'node:test'
import assert from 'node:assert/strict'
import {orderNumberMonth,crossMonthStatementProjects} from '../src/utils/statementCrossMonthProjects.js'

test('original month is parsed from order number, never from dates or billing labels',()=>{
  assert.equal(orderNumberMonth('TP-261025-001.2.3'),'2026-10')
  for(const invalid of ['TP-261325-001','TP-260025-001','unknown',''])assert.equal(orderNumberMonth(invalid),null)
})
test('cross-month projects are deduplicated and scoped to the actual destination board',()=>{
  const line={root_id:'root',order_no:'TP-261025-001.1',project_name:'跨月项目'}
  const tasks={a:{board_id:'b',month:'2026-11',rows:[line,line]},b:{board_id:'b',month:'2026-11',rows:[{...line,order_no:'TP-261025-001.2'}]},
    c:{board_id:'other',month:'2026-11',rows:[line]},d:{board_id:'b',month:'2026-10',rows:[line]},e:{board_id:'b',month:'2026-12',pending:true,rows:[line]}}
  assert.deepEqual(crossMonthStatementProjects(tasks,'b'),[{orderNo:'TP-261025-001',projectName:'跨月项目',sourceMonth:'2026-10',billingMonth:'2026-11',rootId:'root'}])
})
