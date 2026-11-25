import test from 'node:test'
import assert from 'node:assert/strict'
import {projectRequirementFields, requirementModules} from '../src/utils/customerRequirements.js'

test('口译项目仅带入和同步客户要求、补充说明',()=>{
  assert.deepEqual(projectRequirementFields('interpretation'),{interpreterSpecialRequirements:'客户要求',remarks:'补充说明'})
  assert.ok(Object.hasOwn(requirementModules.interpretation.fields,'taskDescription'))
})
test('各类型均不传递具体任务和岗位职责，保留各自已有的要求说明字段',()=>{
  assert.deepEqual(projectRequirementFields('translation'),requirementModules.translation.fields)
  assert.deepEqual(projectRequirementFields('annotation'),{potentialDemand:'（潜在）需求量'})
  assert.deepEqual(projectRequirementFields('recruitment'),{remarks:'补充说明'})
})
