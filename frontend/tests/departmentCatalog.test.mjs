import test from 'node:test'
import assert from 'node:assert/strict'
import { computed } from 'vue'
import { DEPARTMENT_NAMES, applyDepartmentCatalog, normalizeDepartment } from '../src/constants/departments.js'
import { canManageDepartments, canAccessRoute } from '../src/utils/permission.js'

const storage=new Map()
globalThis.localStorage={getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,String(value))}
test('部门目录更新保留所有引用并响应式更新名称和历史映射，旧响应不能覆盖新改名',()=>{
  const borrowed=DEPARTMENT_NAMES
  const departments=computed(()=>DEPARTMENT_NAMES.map(name=>({name})))
  const oldUser=computed(()=>normalizeDepartment('翻译部'))
  applyDepartmentCatalog({ready:true,items:[{id:'it',name:'技术部',revision:2},{id:'sales',name:'销售',revision:1}],aliases:{翻译部:'技术部',IT部:'技术部'}})
  assert.equal(borrowed,DEPARTMENT_NAMES)
  assert.equal(departments.value[0].name,'技术部')
  assert.equal(oldUser.value,'技术部')
  applyDepartmentCatalog({ready:true,items:[{id:'it',name:'IT部',revision:1}],aliases:{}})
  assert.equal(DEPARTMENT_NAMES[0],'技术部')
  applyDepartmentCatalog({ready:true,items:[{id:'it',name:'研发部',revision:3},{id:'sales',name:'销售',revision:1},{id:'new',name:'运营部',revision:1}],aliases:{翻译部:'研发部',IT部:'研发部',技术部:'研发部'}})
  assert.equal(borrowed.includes('运营部'),true)
  assert.equal(oldUser.value,'研发部')
})
test('部门管理路由仅允许用户名白名单和超级管理员，普通用户管理权限不能放行',()=>{
  storage.set('user_roles','[]');storage.set('user_permissions','["system:users:write"]')
  for(const name of ['ethan','Jimmy',' ETHAN ']){storage.set('user_name',name);assert.equal(canManageDepartments(),true);assert.equal(canAccessRoute({meta:{departmentManagement:true}}),true)}
  for(const name of ['other','ethan2','jimmy.admin']){storage.set('user_name',name);assert.equal(canManageDepartments(),false)}
  storage.set('user_roles','["超级管理员"]')
  assert.equal(canAccessRoute({meta:{departmentManagement:true}}),true)
})
