import test from 'node:test'
import assert from 'node:assert/strict'
import { parsePastedRegions,buildRegionPayload,columnLetter,prepareRegionSource,removeRegionCharacters } from '../src/utils/regionMatchInput.js'
test('复制的多列多行保留空列、原行号和引号中的换行',()=>{
 const table=parsePastedRegions('籍贯\t成长地\t所在地\r\n广东深圳\t四川成都\t\r\n\r\n"上海\n浦东"\t"北京"\t杭州',true)
 assert.equal(table.rows.length,2);assert.equal(table.rows[1].source_row,4)
 assert.deepEqual(table.rows[0].values,['广东深圳','四川成都',''])
 assert.equal(table.rows[1].values[0],'上海\n浦东');assert.equal(columnLetter(26),'AA')
})
test('无表头默认不丢第一行；映射保持原始数据和列索引',()=>{
 const table=parsePastedRegions('广东\t深圳\n广西\t桂林')
 const request=buildRegionPayload(table,[0,1],{0:['ancestral_home'],1:['native_place','residence_address']},80,'all','any')
 assert.equal(request.rows[0][0],'广东');assert.equal(request.mappings[1].source_column,1)
 assert.deepEqual(request.mappings[1].target_fields,['native_place','residence_address'])
 assert.equal(request.threshold,100)
 request.rows[0][0]='changed';assert.equal(table.rows[0].values[0],'广东')
})
test('空数据、未闭合引号、过量行列和无效配置必须明确报错',()=>{
 for(const input of ['', '"广东',Array(1002).fill('广东').join('\n'),Array(51).fill('广东').join('\t')])assert.throws(()=>parsePastedRegions(input))
 const table=parsePastedRegions('深圳')
 assert.throws(()=>buildRegionPayload(table,[0],{0:[]},100,'all','any'))
 assert.equal(buildRegionPayload(table,[0],{0:['native_place']},50,'all','any').threshold,100)
 assert.throws(()=>buildRegionPayload(table,[0],{0:['native_place']},49,'all','any'))
 assert.throws(()=>buildRegionPayload(table,[0],{0:['native_place']},55,'all','any'))
})
test('去后缀只去一次、三字后缀优先，两个字保留规则可以与长名称同时使用',()=>{
 const rules={matchMode:'trim_suffix',suffixes:['市','区','县','自治州','自治区'],preserveShort:true}
 for(const [source,expected] of [['深圳市','深圳'],['房县','房县'],['延边自治州','延边'],['广西自治区','广西'],['深圳市区','深圳市'],['深圳市中心','深圳市中心']])assert.equal(prepareRegionSource(source,rules),expected)
 assert.equal(prepareRegionSource('房县',{...rules,preserveShort:false}),'房')
 assert.equal(prepareRegionSource('深圳市',{...rules,matchMode:'full'}),'深圳市')
 assert.equal(prepareRegionSource('A B-C'), 'A B-C')
})
test('按位置去字保留原文、多行覆盖与匹配规则随请求传递',()=>{
 assert.equal(removeRegionCharacters('哈哈市',[1]),'哈市')
 assert.equal(removeRegionCharacters('A😀BC',[1,3]),'AB')
 const table=parsePastedRegions('广东省\t深圳市\n广西\t桂林')
 const rules={matchMode:'trim_suffix',suffixes:['省','市'],preserveShort:true}
 const request=buildRegionPayload(table,[0,1],{0:['ancestral_home'],1:['native_place']},100,'all','any',rules,{0:{0:'广东'}})
 assert.deepEqual(request.rows,[['广东','深圳市'],['广西','桂林']])
 assert.equal(request.match_mode,'trim_suffix');assert.equal(request.preserve_short,true)
 assert.deepEqual(request.suffixes,['省','市']);assert.equal(table.rows[0].values[0],'广东省')
})
