import test from 'node:test'
import assert from 'node:assert/strict'
import {restoreInterpreterAssignments as restore} from '../src/utils/interpretationDraft.js'
const saved=[{translatorId:'one',clientSelected:true,translatorLabel:'测试译员（RC1）',customerRating:'',evaluationNote:''}]
test('旧空白行不会覆盖已保存译员及客户选定',()=>{assert.deepEqual(restore([{translatorId:'',clientSelected:false}],saved),saved)})
test('旧版暂存补齐姓名和新保存勾选',()=>{assert.deepEqual(restore([{translatorId:'one',clientSelected:false}],saved,undefined,true),[{translatorId:'one',clientSelected:true,translatorLabel:'测试译员（RC1）'}])})
test('相同版本未保存的取消选定继续保留',()=>{const rows=restore([{translatorId:'one',clientSelected:false}],saved,undefined,false);assert.equal(rows[0].clientSelected,false);assert.equal(rows[0].translatorLabel,saved[0].translatorLabel)})
test('有基线时采用服务器新选定，保留本人评价备注',()=>{
 const baseline=[{...saved[0],clientSelected:false}]
 const rows=restore([{...baseline[0],evaluationNote:'未保存评价'}],saved,baseline,true)
 assert.equal(rows[0].clientSelected,true);assert.equal(rows[0].evaluationNote,'未保存评价')
})
test('真实未保存的更换、增加和删除不被恢复覆盖',()=>{
 assert.deepEqual(restore([],saved,saved,true),[])
 const local=[{translatorId:'two',clientSelected:false}];assert.equal(restore(local,saved,saved,true)[0].translatorId,'two')
 assert.equal(restore([...saved,...local],saved,saved,true).length,2)
})
test('新版未改人选时带出他处保存的新译员',()=>{assert.deepEqual(restore([],saved,[],true),saved)})
