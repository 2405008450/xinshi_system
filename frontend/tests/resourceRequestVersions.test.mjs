import test from 'node:test'
import assert from 'node:assert/strict'
import {mergeTaskVersions,TASK_COPY_NOTICE,taskVersionBody,hasTaskCopyNotice} from '../src/utils/resourceRequestVersions.js'
const source=text=>['发帖','询问'].map(name=>({name,content:text,copiedFromTask:true}))
test('两种空版本复制具体任务，保留截图引用和人工正文',()=>{
 const original=[{name:'发帖',content:''},{name:'询问',content:'人工询问内容'},{name:'内部',content:'内部内容'}]
 const result=mergeTaskVersions(original,source('任务\n![截图](screenshot://test)'))
 assert.equal(result[0].content,TASK_COPY_NOTICE+'\n任务\n![截图](screenshot://test)')
 assert.equal(result[0].copiedFromTask,true)
 assert.equal(result[1].content,'人工询问内容')
 assert.equal(result[2].content,'内部内容')
 assert.equal(original[0].content,'')
})
test('切换项目只更新未修改的自动内容，缺少版本可补齐',()=>{
 const result=mergeTaskVersions([{name:'发帖',content:'上一个任务',copiedFromTask:true},{name:'询问',content:'人工改过',copiedFromTask:true}],source('新任务'),'上一个任务')
 assert.equal(result[0].content,TASK_COPY_NOTICE+'\n新任务');assert.equal(result[1].content,'人工改过')
 assert.equal(mergeTaskVersions([],source('新任务')).length,2)
})
