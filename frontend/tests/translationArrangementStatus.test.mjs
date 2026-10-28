import test from 'node:test'
import assert from 'node:assert/strict'
import {getProjectStatusLabel,normalizeProjectStatus,getProjectStatusOptions} from '../src/utils/projectStatus.js'

test('笔译状态包含初步咨询，统一显示中文并可用于筛选',()=>{
  assert.equal(getProjectStatusOptions('translation')[0].value,'initial_consultation')
  for(const value of ['initial_consultation','INITIAL_CONSULTATION','初步咨询']){
    assert.equal(normalizeProjectStatus('translation',value),'initial_consultation')
    assert.equal(getProjectStatusLabel('translation',value),'初步咨询')
  }
})

test('已安排统一显示中文并兼容状态值空格和历史中文值',()=>{
  for(const value of ['arranged',' arranged ','ARRANGED','已安排']){
    assert.equal(normalizeProjectStatus('translation',value),'arranged')
    assert.equal(getProjectStatusLabel('translation',value),'已安排')
  }
  assert.equal(normalizeProjectStatus('translation',' pending '),'pending_confirmation')
  assert.equal(getProjectStatusLabel('translation','pending'),'待确认')
})
