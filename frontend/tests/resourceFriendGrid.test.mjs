import test from 'node:test'
import assert from 'node:assert/strict'
import { friendRowsToGrid, friendGridToRows, parseFriendPaste, parseFriendCount } from '../src/utils/resourceFriendGrid.js'
const accounts=[{key:'e1',channel:'enterprise'},{key:'w1',channel:'wechat'}]
const line=(key,count)=>({column_key:key,channel:accounts.find(a=>a.key===key).channel,language_value:'lang1',language_type:'dialect',overview_key:'row1',count})
test('账号明细合并为语种行，再保存不丢失零和空白',()=>{
 const original=[line('e1',0),line('w1',null)]
 const grid=friendRowsToGrid(original)
 assert.equal(grid.length,1)
 assert.deepEqual(friendGridToRows(grid,accounts),original)
 grid[0].cells.w1=8
 assert.equal(friendGridToRows(grid,accounts)[1].count,8)
})
test('新语种暂未填人数时保留为未填写',()=>{
 const row={language_value:'新方言',language_type:'dialect',overview_key:'__new__',cells:{},channels:{}}
 assert.equal(friendGridToRows([row],accounts)[0].count,null)
 assert.equal(friendGridToRows([row],accounts)[0].language_value,'新方言')
})
test('Excel矩形粘贴保留空白零值及行列边界',()=>{
 assert.deepEqual(parseFriendPaste('0\t12\t\r\n3\t4\t5\r\n'),[[0,12,null],[3,4,5]])
 assert.deepEqual(parseFriendPaste(' 8 '),[[8]])
 for(const value of ['1.5','-1','1000001','HR1']) assert.throws(()=>parseFriendPaste(value))
 assert.equal(parseFriendCount(''),null)
 assert.equal(parseFriendCount('0'),0)
})
