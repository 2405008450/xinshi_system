import test from 'node:test'
import assert from 'node:assert/strict'
import { isCopyableBusinessField, selectedFieldText } from '../src/utils/fieldCopy.js'

test('客户、项目名称与母子订单号识别，其他字段保持原操作', () => {
  for(const label of ['客户名称','客户全称','客户简称','子客户名称','母客户简称','项目名称','订单号','母订单号','子订单号','三级订单号','当前订单号','新订单号','客户单号']) {
    assert.equal(isCopyableBusinessField(label),true,label)
  }
  for(const label of ['客户经理','项目状态','联系方式','订单金额','联系电话']) {
    assert.equal(isCopyableBusinessField(label),false,label)
  }
  for(const key of ['client_short_name','projectName','orderNo','sub_order_no'])assert.equal(isCopyableBusinessField('',key),true,key)
})

test('仅复制当前字段内部选区，忽略其他单元格或跨字段选区', () => {
  const inside={},outside={}
  const scope={contains:node=>node===inside}
  const selection=(start,end)=>({isCollapsed:false,rangeCount:1,getRangeAt:()=>({startContainer:start,endContainer:end}),toString:()=> '选中的字'})
  assert.equal(selectedFieldText(scope,null,selection(inside,inside)),'选中的字')
  assert.equal(selectedFieldText(scope,null,selection(inside,outside)),'')
  assert.equal(selectedFieldText(scope,null,selection(outside,outside)),'')
})
