import test from 'node:test'
import assert from 'node:assert/strict'
import {selectRegionMatchResults,formatRegionMatchRate} from '../src/utils/regionMatchResults.js'
const rows=[
 {index:0,sourceRow:2,total:0,values:['吉林市','龙潭区']},
 {index:1,sourceRow:3,total:5,values:['延边朝鲜族自治州','敦化市']},
 {index:2,sourceRow:4,total:2,values:['吉林市','船营区']},
 {index:3,sourceRow:5,total:5,values:['吉林市','龙潭区%_\\']},
]
test('按匹配人数排序覆盖全部来源行，同人数按原行顺序且不改原数据',()=>{
 assert.deepEqual(selectRegionMatchResults(rows,[0,1],{order:'desc'}).map(row=>row.index),[1,3,2,0])
 assert.deepEqual(selectRegionMatchResults(rows,[0,1],{order:'asc'}).map(row=>row.index),[0,2,1,3])
 assert.deepEqual(rows.map(row=>row.index),[0,1,2,3])
 assert.equal(selectRegionMatchResults(rows,[0,1],{order:'desc'})[0],rows[1])
})
test('全局关键词跨来源列匹配，各列条件AND组合，通配符按普通文字处理',()=>{
 assert.deepEqual(selectRegionMatchResults(rows,[0,1],{keyword:'龙潭 吉林'}).map(row=>row.sourceRow),[2,5])
 assert.deepEqual(selectRegionMatchResults(rows,[0,1],{columnFilters:{0:'吉林',1:'船营'}}).map(row=>row.index),[2])
 assert.deepEqual(selectRegionMatchResults(rows,[0,1],{columnFilters:{1:'%_\\'}}).map(row=>row.index),[3])
 assert.equal(selectRegionMatchResults(rows,[0],{keyword:'龙潭'}).length,0)
 assert.equal(selectRegionMatchResults(rows,[0,1],{keyword:'不存在'}).length,0)
})
test('匹配率保留两位小数，缺失率不伪装为0或100',()=>{
 assert.equal(formatRegionMatchRate(87.5),'87.50%');assert.equal(formatRegionMatchRate(100),'100.00%')
 assert.equal(formatRegionMatchRate(null),'-');assert.equal(formatRegionMatchRate(undefined),'-')
})
