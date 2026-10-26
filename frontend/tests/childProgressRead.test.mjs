import test from 'node:test'
import assert from 'node:assert/strict'
import {childProgressReadStorageKey,parseChildProgressRead,childProgressReadCount,markChildProgressRead} from '../src/utils/childProgressRead.js'
test('用户和母订单隔离；无效缓存不影响界面',()=>{
  assert.notEqual(childProgressReadStorageKey('a','p'),childProgressReadStorageKey('b','p'))
  assert.notEqual(childProgressReadStorageKey('a','p'),childProgressReadStorageKey('a','q'))
  assert.deepEqual(parseChildProgressRead('bad'),[])
  assert.deepEqual(parseChildProgressRead('["a","a",null,3]'),['a'])
})
test('只计当前记录；新记录和修订记录重新计为未读',()=>{
  const keys=['project:1:v1','customer:2:v1','annotator:3:v1']
  const read=markChildProgressRead(keys,[],keys[0])
  assert.equal(childProgressReadCount(keys,read),1)
  assert.equal(childProgressReadCount(['project:1:v2',...keys.slice(1)],read),0)
  assert.equal(childProgressReadCount(keys.slice(1),read),0)
  assert.deepEqual(markChildProgressRead(keys,['obsolete'],keys[1]),[keys[1]])
})
