import test from 'node:test'
import assert from 'node:assert/strict'
import {applyFolderRootPath,restoreFolderRootPath} from '../src/utils/translationFolderPaths.js'

test('选定本地目录同步母单、隐藏字段和项目文件草稿，保留其他资料',()=>{
  const form={originalStoragePath:'\\\\server\\old',networkFilePath:'\\\\server\\old',filePathDraft:{storage_path:'\\\\server\\old',reference_path:'保留参考路径'},pendingSubOrderDetails:{'001':{languagePair:'中文→英语'}}}
  applyFolderRootPath(form,'D:\\实际项目')
  assert.equal(form.originalStoragePath,'D:\\实际项目')
  assert.equal(form.networkFilePath,'D:\\实际项目')
  assert.deepEqual(form.filePathDraft,{storage_path:'D:\\实际项目',reference_path:'保留参考路径'})
  assert.equal(form.pendingSubOrderDetails['001'].languagePair,'中文→英语')
})

test('旧格式草稿修复一次，随后保留主动修改',()=>{
  const form={pendingFolderImport:{rootPath:'D:\\实际项目'},filePathDraft:{storage_path:'\\\\server\\old'}}
  restoreFolderRootPath(form)
  assert.equal(form.filePathDraft.storage_path,'D:\\实际项目')
  form.originalStoragePath='E:\\人工修改'
  restoreFolderRootPath(form)
  assert.equal(form.originalStoragePath,'E:\\人工修改')
  const plain={originalStoragePath:'保留'}
  restoreFolderRootPath(plain)
  assert.deepEqual(plain,{originalStoragePath:'保留'})
})
