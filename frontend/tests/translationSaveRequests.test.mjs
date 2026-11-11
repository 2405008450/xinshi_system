import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'

test('笔译保存独立等待120秒；创建超时重试沿用同一个幂等标识',async()=>{
 const calls=[];let fail=true
 const harness={api:{post:async(...args)=>{calls.push(args);if(fail){fail=false;throw Object.assign(new Error('timeout'),{code:'ECONNABORTED'})}return {id:'p1',order_no:'TP-261109-999'}},put:async(...args)=>{calls.push(args);return {id:'p1'}}},invalidateOptionCache:()=>{},exportProjectWorkbook:()=>{}}
 globalThis.__translationSaveHarness=harness
 let source=await readFile(new URL('../src/api/projects.js',import.meta.url),'utf8')
 source=source.replace("import api from './index'",'const {api,invalidateOptionCache,exportProjectWorkbook}=globalThis.__translationSaveHarness')
 source=source.replace("import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'",`import { clearIdempotencyKey, resolveIdempotencyKey } from '${new URL('../src/utils/idempotency.js',import.meta.url).href}'`)
 source=source.replace("import { invalidateOptionCache } from '@/utils/optionCache'",'').replace("import { exportProjectWorkbook } from './projectExports'",'')
 const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
 try{
  const payload={projectName:'测试目录',initialFolderImport:{rootPath:'D:\\测试目录',entries:[{relativePath:'测试目录',files:['文件.docx']}]}}
  await assert.rejects(api.createProject(payload),error=>error.code==='ECONNABORTED')
  const saved=await api.createProject(payload)
  assert.equal(saved.orderNo,'TP-261109-999');assert.equal(calls[0][2].timeout,120000)
  assert.equal(calls[0][2].headers['X-Idempotency-Key'],calls[1][2].headers['X-Idempotency-Key'])
  assert.deepEqual(calls[0][1].initial_folder_import.entries[0].files,['文件.docx'])
  await api.updateProject('p1',{projectName:'更新.docx'})
  assert.equal(calls[2][2].timeout,120000);assert.equal(calls[2][1].project_name,'更新.docx')
 }finally{delete globalThis.__translationSaveHarness}
})
