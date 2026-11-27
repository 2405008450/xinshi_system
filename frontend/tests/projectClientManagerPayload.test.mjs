import test from 'node:test'
import assert from 'node:assert/strict'
import {projectClientManagerPayload,interpretationProjectWritePayload} from '../src/utils/projectClientManagerPayload.js'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'

test('新增默认提交填写人，编辑译员时不重复提交未变更的客户经理',()=>{
  const form={clientManagerId:'manager',currentClientManager:'赵震锋',clientManagerChangeReason:'',interpreterAssignments:[{translatorId:'talent'}]}
  assert.deepEqual(projectClientManagerPayload(form,'manager',true),{clientManagerId:'manager',clientManagerChangeReason:null})
  assert.deepEqual(projectClientManagerPayload(form,'manager'),{})
  assert.deepEqual(projectClientManagerPayload({clientManagerId:''},''),{})
})

test('主动更换和清空客户经理仍提交变更及原因，不提交显示姓名',()=>{
  assert.deepEqual(projectClientManagerPayload({clientManagerId:' new ',clientManagerChangeReason:' 客户交接 ',currentClientManager:'旧经理'},'old'),{clientManagerId:'new',clientManagerChangeReason:'客户交接'})
  assert.deepEqual(projectClientManagerPayload({clientManagerId:'',clientManagerChangeReason:'解除分配'},'old'),{clientManagerId:null,clientManagerChangeReason:'解除分配'})
})

test('真实口译新增和编辑接口过滤旧姓名字段，保留经理ID调整、译员和路径',async()=>{
  const requests=[]
  const ctx={Object,interpretationProjectWritePayload,api:{post:async(url,data)=>{requests.push({url,data});return {}},put:async(url,data)=>{requests.push({url,data});return {}}},invalidateOptionCache(){},resolveIdempotencyKey:()=> 'key',clearIdempotencyKey(){}}
  vm.createContext(ctx)
  const source=readFileSync(new URL('../src/api/interpretationProjects.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/^export /gm,'')
  vm.runInContext(source+'\nglobalThis.actions={createInterpretationProject,updateInterpretationProject}',ctx)
  const value={currentClientManager:'赵震锋',current_client_manager:'旧姓名',clientManagerId:'manager',clientManagerChangeReason:'客户交接',interpreterAssignments:[{translatorId:'person'}],filePath:'D:\\项目'}
  await ctx.actions.createInterpretationProject(value)
  await ctx.actions.updateInterpretationProject('project',value)
  for(const {data} of requests){
    assert.equal(Object.hasOwn(data,'current_client_manager'),false)
    assert.equal(data.client_manager_id,'manager')
    assert.equal(data.client_manager_change_reason,'客户交接')
    assert.equal(data.interpreter_assignments[0].translator_id,'person')
    assert.equal(data.file_path,'D:\\项目')
  }
  assert.equal(requests.length,2)
  assert.equal(value.currentClientManager,'赵震锋')
  assert.equal(value.current_client_manager,'旧姓名')
})
