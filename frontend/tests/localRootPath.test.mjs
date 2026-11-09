import test from 'node:test'
import assert from 'node:assert/strict'
import {givenLocalRootPath} from '../src/utils/localRootPath.js'
test('extracts actual root from supplied native path or registered project path',()=>{
  assert.equal(givenLocalRootPath('客户资料',{files:[{path:'D:\\项目\\客户资料\\下层\\a.pdf'}]}),'D:\\项目\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['D:\\项目\\客户资料']}),'D:\\项目\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['\\\\server\\share\\客户资料\\a.pdf']}),'\\\\server\\share\\客户资料')
})
test('retains edited matching root, ignores wrong roots, relative paths and fake browser path',()=>{
  assert.equal(givenLocalRootPath('客户资料',{candidates:['E:\\修改\\客户资料','D:\\原路径\\客户资料']}),'E:\\修改\\客户资料')
  assert.equal(givenLocalRootPath('新目录',{candidates:['D:\\旧目录']}),'')
  assert.equal(givenLocalRootPath('客户资料',{files:[{webkitRelativePath:'客户资料/a.pdf'}]}),'')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['C:\\fakepath\\客户资料','D:\\父目录\\..\\客户资料']}),'')
})
