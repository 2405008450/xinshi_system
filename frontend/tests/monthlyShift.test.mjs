import test from 'node:test'
import assert from 'node:assert/strict'
import {currentShiftMonth,shiftMonth,shiftMonthTitle} from '../src/utils/monthlyShift.js'
import {canAccessRoute,setStoredHrAccess,canManageHr} from '../src/utils/permission.js'
test('月度排班按 UTC+8 日历月份，跨年跨月正确',()=>{
 assert.equal(currentShiftMonth(new Date('2026-10-31T17:00:00Z')),'2026-11')
 assert.equal(shiftMonth('2026-12',1),'2027-01')
 assert.equal(shiftMonth('2026-01',-1),'2025-12')
 assert.equal(shiftMonthTitle('2026-11'),'2026年11月班次安排')
})
test('人事管理仅遵循行政部门服务端标志，超级管理员不绕过，用户隔离',()=>{
 const values=new Map();globalThis.localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,String(value))}
 localStorage.setItem('user_id','user-a');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']))
 setStoredHrAccess(false);assert.equal(canAccessRoute({meta:{hrManagement:true}}),false)
 setStoredHrAccess(true);assert.equal(canManageHr(),true)
 localStorage.setItem('user_id','user-b');assert.equal(canManageHr(),false)
})
