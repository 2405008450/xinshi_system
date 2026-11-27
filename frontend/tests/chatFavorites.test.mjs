import test from 'node:test'
import assert from 'node:assert/strict'
import {favoriteTabs,isSessionFavorite,favoriteClassification,favoriteGroups,normalizeFavoriteTypeOrder,favoriteProjectDate} from '../src/utils/chatFavorites.js'
test('四类收藏及历史个人关注合并，未收藏会话保持排除',()=>{
 assert.deepEqual(favoriteTabs.map(x=>x.id),['messages','projects','technical','other'])
 assert.equal(isSessionFavorite({kind:'annotation',following:true}),true)
 assert.equal(isSessionFavorite({kind:'discussion',starred:true}),true)
 assert.equal(isSessionFavorite({kind:'discussion',following:true}),false)
 assert.equal(favoriteClassification({kind:'discussion',subtitle:'DT-261127-001'}).tab,'technical')
 assert.equal(favoriteClassification({kind:'discussion',title:'全体大群'}).tab,'other')
 assert.equal(favoriteClassification({kind:'discussion',subtitle:'IP-261127-001'}).type,'interpretation')
})
test('按全部匹配记录决定日期目录，分页不会改变阈值与类型排序',()=>{
 const rows=Array.from({length:9},(_,i)=>({kind:'annotation',title:String(i),subtitle:`AP-26112${i%2+6}-001`}))
 assert.equal(favoriteGroups(rows,rows,'projects')[0].dates.length,2)
 assert.equal(favoriteGroups(rows.slice(0,2),rows,'projects')[0].total,9)
 assert.equal(favoriteGroups(rows.slice(0,8),rows.slice(0,8),'projects')[0].dates.length,0)
 assert.equal(favoriteProjectDate(rows[0]),'261126')
 assert.deepEqual(normalizeFavoriteTypeOrder(['translation','translation','deleted']).slice(0,2),['translation','annotation'])
})
