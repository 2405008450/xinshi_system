import assert from 'node:assert/strict'
import test from 'node:test'
import {pathSnapshot,pathChanges} from '../src/utils/talentPathEditing.js'
test('只保存实际修改的字段及对应原值，不把其他资料发回覆盖',()=>{
 const row={id:'1',resourceCode:'RC1',fullName:'原姓名',nativePlace:'广州',wechat:'old'};row._original=pathSnapshot(row)
 row.nativePlace='深圳';row.whatsapp='wa';row.unrelated='ignored'
 assert.deepEqual(pathChanges(row),{changes:{nativePlace:'深圳',whatsapp:'wa'},expectedValues:{nativePlace:'广州',whatsapp:null}})
})
test('空字符串与空值等价，受限账号的遮罩联系方式不作为修改发送',()=>{
 const row={fullName:'甲',contactRestricted:true,wechat:'******',resumePath:null};row._original=pathSnapshot(row)
 row.resumePath='';row.wechat='cannot-send';assert.deepEqual(pathChanges(row),{changes:{},expectedValues:{}})
 row.fullName='乙';assert.deepEqual(pathChanges(row).changes,{fullName:'乙'})
})
