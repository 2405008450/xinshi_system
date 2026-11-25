import test from 'node:test'
import assert from 'node:assert/strict'
import {emptyInterpretationLocation,normalizeInterpretationLocations,interpretationLocationText,interpretationLocationPayload} from '../src/utils/interpretationLocations.js'
test('历史地点原样作为详细地址，不推断国家城市',()=>{
 const [item]=normalizeInterpretationLocations(null,['深圳南山区某会场'])
 assert.deepEqual(item,{countryProvince:'',city:'',address:'深圳南山区某会场'})
 assert.equal(interpretationLocationText(item),'深圳南山区某会场')
})
test('地点分字段保存并合成完整地址，空行不进入提交',()=>{
 const items=interpretationLocationPayload([{countryProvince:' 中国广东省 ',city:' 深圳市 ',address:' 科苑路 '},emptyInterpretationLocation()])
 assert.equal(items.length,1)
 assert.equal(interpretationLocationText(items[0]),'中国广东省 深圳市 科苑路')
 const copies=normalizeInterpretationLocations(items)
 copies[0].city='广州'
 assert.equal(items[0].city,'深圳市')
})
