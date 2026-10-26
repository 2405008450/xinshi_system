import test from 'node:test'
import assert from 'node:assert/strict'
import {managedProjectFilters} from '../src/utils/managedProjectFilters.js'
test('我的项目保留其他筛选并使用单个 OR 负责人条件，全部模式不添加限制',()=>{
  const original=JSON.stringify({project_status:{op:'in',value:['trial_preparation']}})
  const mine=JSON.parse(managedProjectFilters(original,true,'person-a'))
  assert.deepEqual(mine.managed_user_id,{op:'in',value:['person-a']})
  assert.deepEqual(mine.project_status,{op:'in',value:['trial_preparation']})
  assert.equal(managedProjectFilters(original,false,'person-a'),original)
  assert.equal(JSON.parse(managedProjectFilters(undefined,true,'')).managed_user_id.value[0],'00000000-0000-0000-0000-000000000000')
})
