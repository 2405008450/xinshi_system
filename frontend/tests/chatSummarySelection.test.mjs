import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { issueCategories,issueParams } from '../src/utils/resourceIssues.js'
import { buildMessageMenu } from '../src/utils/chatMessageMenu.js'

test('八类分类完整且旧的独立分类菜单已移除',()=>{
  assert.deepEqual(issueCategories.map(row=>row.label),['信息同步','提出需求','想法讨论','决策批复','任务执行','问题/异常','风险隐患','规则标准'])
  const menu=buildMessageMenu({content:'正文',canClassify:true},{canCollect:true,annotationProgress:true})
  assert.equal(menu.some(row=>row.id==='classify'),false)
  assert.equal(menu.find(row=>row.id==='collect').label,'分类保存和通知')
  assert.equal(menu.find(row=>row.id==='annotation-progress').submenu,true)
  assert.equal(buildMessageMenu({content:'正文'},{annotationProgress:false}).some(row=>row.id==='annotation-progress'),false)
})
test('全部部门、全部人员分别展开为具体ID并去重，不混淆同名部门与人员',()=>{
  const source=readFileSync(new URL('../src/components/chat/SummaryAudienceSelect.vue',import.meta.url),'utf8')
  const script=source.split('<script setup>')[1].split('</script>')[0].replace(/\r\n/g,'\n').replace(/^import .*\n/gm,'')
  let result
  const change=runInNewContext(script+';change',{
    defineProps:()=>({modelValue:{},departments:[{id:'a',name:'同名'},{id:'b',name:'另一部门'}],users:[{id:'a',name:'同名'},{id:'c',name:'人员C'}]}),
    defineEmits:()=> (_,value)=>{result=value},computed:fn=>({get value(){return fn()}}),
  })
  change(['all:departments','all:users','department:a','user:a'])
  assert.deepEqual(Array.from(result.departmentIds),['a','b'])
  assert.deepEqual(Array.from(result.userIds),['a','c'])
  change([]);assert.equal(result.userIds.length+result.departmentIds.length,0)
})
test('总结保存日期与执行部门条件和列表分页共享同一参数',()=>{
  const params=issueParams({keyword:' 条件 ',category:'execution',department_id:'dept',executor_id:'person',saved_range:['2026-10-01','2026-10-22']},{page:2,limit:10})
  assert.equal(params.saved_start,'2026-10-01');assert.equal(params.saved_end,'2026-10-22')
  assert.equal(params.department_id,'dept');assert.equal(params.executor_id,'person');assert.equal(params.skip,10)
})
test('标注进度提交保持子订单ID，项目进度与客户进度使用独立接口且不切换状态',async()=>{
  const source=readFileSync(new URL('../src/api/annotationChatProgress.js',import.meta.url),'utf8').replace(/\r\n/g,'\n').replace(/^import .*\n/gm,'').replace('export function','function')
  const calls=[]
  const save=runInNewContext(source+';saveAnnotationChatProgress',{
    createCustomerProgress:async(id,data)=>{calls.push({type:'customer',id,data})},
    createAnnotatorProgress:async(id,data)=>{calls.push({type:'annotator',id,data})},
    updateAnnotationProjectStatus:async(id,data)=>{calls.push({type:'project',id,data})},
  })
  const input={projectId:'exact-child-id',projectStatus:'project_in_progress',changeNote:' 消息进度 ',effectiveOn:'2026-10-22 15:00:00'}
  await save({...input,track:'customer'});await save({...input,track:'project'})
  await save({...input,track:'annotator'})
  assert.equal(calls[2].type,'annotator');assert.equal(calls[2].id,'exact-child-id')
  assert.equal(calls[2].data.changeNote,'消息进度');assert.equal(calls[2].data.projectStatus,undefined)
  assert.equal(calls[0].type,'customer');assert.equal(calls[1].type,'project')
  assert.equal(calls[0].id,'exact-child-id');assert.equal(calls[1].id,'exact-child-id')
  assert.equal(calls[0].data.effectiveOn,'2026-10-22T15:00:00+08:00')
  assert.equal(calls[1].data.progressOnly,true);assert.equal(calls[0].data.projectStatus,undefined)
  assert.throws(()=>save({...input,track:'invalid'}));assert.throws(()=>save({...input,track:'project',changeNote:' '}))
})
