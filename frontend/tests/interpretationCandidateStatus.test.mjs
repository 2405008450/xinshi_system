import test from 'node:test'
import assert from 'node:assert/strict'
import {statusLabel,statusType} from '../src/utils/interpretationProjectDetail.js'
import {getProjectStatusLabel} from '../src/utils/projectStatus.js'

test('自动人选状态中文、人数与共用状态目录一致',()=>{
 assert.equal(statusLabel('candidates_provided',2),'已提供人选（2人）')
 assert.equal(statusLabel('client_selected'),'客户已定人选')
 assert.equal(statusLabel('client_changed'),'客户改变人选')
 assert.equal(getProjectStatusLabel('interpretation','candidates_provided'),'已提供人选')
 assert.equal(statusType('client_changed'),'warning')
})
