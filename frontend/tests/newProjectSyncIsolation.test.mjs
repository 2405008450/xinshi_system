import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {reactive,watch} from 'vue'

test('新增表单同步关闭后立即解绑旧记录，重新进入编辑才重新绑定',()=>{
  const source=readFileSync(new URL('../src/components/common/AppForm.vue',import.meta.url),'utf8').replace(/\r\n/g,'\n')
  const binding=source.match(/const bindLiveModel=.*\nwatch\(.*flush:'sync'.*\)/)?.[0]
  assert.ok(binding)
  const calls=[],props=reactive({savedSyncEnabled:true}),liveInstance={},model={id:'old-project'}
  const context={props,watch,liveInstance,liveAttrs:{model},bindSavedForm:()=>calls.push('bind'),unbindSavedForm:()=>calls.push('unbind')}
  vm.createContext(context)
  vm.runInContext(binding+'\nthis.update=bindLiveModel',context)
  context.update()
  model.id=''
  props.savedSyncEnabled=false
  assert.deepEqual(calls,['bind','unbind'])
  context.update()
  assert.equal(calls.at(-1),'unbind')
  model.id='new-edit-project'
  props.savedSyncEnabled=true
  assert.equal(calls.at(-1),'bind')
})
