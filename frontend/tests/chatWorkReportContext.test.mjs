import test from 'node:test'
import assert from 'node:assert/strict'
import { displayedReportProject } from '../src/utils/chatWorkReportContext.js'

test('旧服务的口译讨论仍可带订单号，讨论室 UUID 不作为项目 ID', () => {
  assert.deepEqual(displayedReportProject({projectId:'room-id',projectType:'discussion',title:'IP-261126-002 · 广州英语陪同口译项目'}), {
    id:null,type:'interpretation',name:'IP-261126-002 · 广州英语陪同口译项目',orderNo:'IP-261126-002',
  })
  assert.equal(displayedReportProject({projectId:'room-id',projectType:'discussion',title:'内部管理群'}),null)
})

test('标注子订单保留真实项目 ID 与完整订单号', () => {
  const result=displayedReportProject({projectId:'project-id',projectType:'annotation',title:'标注项目',orderNo:'AP-261126-001.001'})
  assert.equal(result.id,'project-id')
  assert.equal(result.orderNo,'AP-261126-001.001')
})

test('通用群聊和私聊打开空白报告，不把聊天对象误当成项目', () => {
  for(const projectType of ['discussion','direct'])
    assert.equal(displayedReportProject({projectId:'chat-id',projectType,title:'日常沟通'}),null)
})
