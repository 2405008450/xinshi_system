import test from 'node:test'
import assert from 'node:assert/strict'
import {givenLocalRootPath,localFolderCandidates} from '../src/utils/localRootPath.js'
test('extracts actual root from supplied native path or registered project path',()=>{
  assert.equal(givenLocalRootPath('客户资料',{files:[{path:'D:\\项目\\客户资料\\下层\\a.pdf'}]}),'D:\\项目\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['D:\\项目\\客户资料']}),'D:\\项目\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['\\\\server\\share\\客户资料\\a.pdf']}),'\\\\server\\share\\客户资料')
})

test('本地选择不沿用项目残留 UNC，保留人工填写及本机路径',()=>{
  const project={originalStoragePath:'\\\\server\\share\\客户资料',networkFilePath:'\\\\server\\share\\客户资料',sourceFolderPath:'D:\\项目\\客户资料'}
  assert.equal(givenLocalRootPath('客户资料',{candidates:localFolderCandidates('',project)}),'D:\\项目\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{candidates:localFolderCandidates('',{originalStoragePath:project.originalStoragePath})}),'')
  assert.equal(givenLocalRootPath('客户资料',{candidates:localFolderCandidates('E:\\修改\\客户资料',project)}),'E:\\修改\\客户资料')
  assert.equal(givenLocalRootPath('客户资料',{files:[{path:'G:\\实际\\客户资料\\a.pdf'}],candidates:localFolderCandidates('',project)}),'G:\\实际\\客户资料')
})
test('retains edited matching root, ignores wrong roots, relative paths and fake browser path',()=>{
  assert.equal(givenLocalRootPath('客户资料',{candidates:['E:\\修改\\客户资料','D:\\原路径\\客户资料']}),'E:\\修改\\客户资料')
  assert.equal(givenLocalRootPath('新目录',{candidates:['D:\\旧目录']}),'')
  assert.equal(givenLocalRootPath('客户资料',{files:[{webkitRelativePath:'客户资料/a.pdf'}]}),'')
  assert.equal(givenLocalRootPath('客户资料',{candidates:['C:\\fakepath\\客户资料','D:\\父目录\\..\\客户资料']}),'')
})
