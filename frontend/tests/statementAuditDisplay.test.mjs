import test from 'node:test'
import assert from 'node:assert/strict'
import {statementAuditRows,statementSnapshotRows} from '../src/utils/statementAuditDisplay.js'

test('开户行修改显示账单名称、修改前后，不暴露内部编号或JSON',()=>{
  const rows=statementAuditRows({board_id:'f92d83d6-c725-4d95-9110-22e22ce6b2c8',board_name:'对账单 2',fields:{bank_name:{before:'',after:'1'}}})
  assert.deepEqual(rows,[{field:'对账单 2 / 开户行',before:'未填写',after:'1'}])
})
test('多项任务修改保留订单号，零值、税口径、印章显示业务含义',()=>{
  const rows=statementAuditRows({rows:[{order_no:'TP-001',fields:{subtotal:{before:null,after:0},tax_included:{before:false,after:true},stamp_image:{before:'',after:'data:image/png;base64,secret'}}}]})
  assert.equal(rows[0].field,'任务 / TP-001 / 小计');assert.equal(rows[0].after,'0')
  assert.equal(rows[1].before,'不含税');assert.equal(rows[1].after,'含税')
  assert.equal(rows[2].after,'已设置印章');assert.ok(!JSON.stringify(rows).includes('base64'))
})
test('任务跨账单月份调配显示具体名称及月份',()=>{
  const [row]=statementAuditRows([{order_no:'TP-002',before:{board_id:'internal-a',board_name:'十月账单',month:'2026-10'},after:{board_id:'internal-b',board_name:'十一月账单',month:'2026-11'}}])
  assert.equal(row.field,'TP-002');assert.match(row.before,/十月账单/);assert.match(row.after,/2026-11/);assert.ok(!row.before.includes('internal'))
})
test('调整前后快照以字段对照展示，并显示账单排列变化',()=>{
  const first={boards:[{id:'a',name:'第一份',fields:{bank_name:''}},{id:'b',name:'第二份',fields:{}}],tasks:{}}
  const next=structuredClone(first);next.boards[0].fields.bank_name='招商银行';next.boards.reverse()
  const rows=statementSnapshotRows(first,next)
  assert.ok(rows.some(row=>row.field.includes('第一份')&&row.field.includes('开户行')&&row.after==='招商银行'))
  assert.ok(rows.some(row=>row.field==='排列顺序'&&row.before==='第一份；第二份'&&row.after==='第二份；第一份'))
})
