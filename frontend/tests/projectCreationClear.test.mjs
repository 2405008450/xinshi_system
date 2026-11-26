import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'

const AsyncFunction=Object.getPrototypeOf(async()=>{}).constructor
const pages=[
  ['口译','interpretation/InterpretationProjectDetails.vue'],
  ['标注','AnnotationProjects.vue'],
  ['招聘','RecruitmentProjects.vue'],
]
for(const [name,path] of pages){
  const source=readFileSync(new URL(`../src/views/project/${path}`,import.meta.url),'utf8')
  const body=source.match(/const clearNewProject\s*=\s*async\s*\([^)]*\)\s*=>\s*\{([\s\S]*?)\n\}/)?.[1]
  assert.ok(body,`${name}清空处理函数存在`)
  function scenario({id='',busy=false,cancel=false}={}){
    const calls=[],form={id,projectName:'未保存项目',socialPostRequest:'未保存需求'},ref=value=>({value})
    const context={form,submitLoading:ref(busy),saving:ref(busy),submitLocked:false,
      ElMessageBox:{confirm:async()=>{calls.push('confirm');if(cancel)throw Error('cancel')}},
      ElMessage:{success:()=>calls.push('success')},clearDraft:()=>calls.push('clear-draft'),
      clearTimeout:()=>{},autoNameTimer:null,namePreviewRequestId:4,nameLoading:ref(false),
      resetForm:()=>{calls.push('reset');form.projectName='';form.socialPostRequest=''},
      clientManagerBaseline:ref('old'),localStorage:{getItem:()=> 'current-user'},
      projectCreateIdempotencyKey:ref('old'),createIdempotencyKey:()=> 'new-key',
      resetEditorScroll:async()=>calls.push('scroll'),formRef:ref({clearValidate:()=>calls.push('clear-validation')}),
      startFreshDraft:key=>calls.push(`fresh:${key}`),editorTab:ref('material'),managerEditBaseline:ref({}),
      annotationApi:{resetAnnotationProjectIdempotency:()=>calls.push('new-key')},
      createClearGeneration:ref(0),resetRecruitmentProjectIdempotency:()=>calls.push('new-key'),
      activeProject:ref({id:'old'}),candidateRows:ref([{}]),
    }
    return {context,calls,run:()=>new AsyncFunction(...Object.keys(context),body)(...Object.values(context))}
  }
  test(`${name}：取消清空保留内容和草稿`,async()=>{
    const s=scenario({cancel:true});await s.run()
    assert.equal(s.context.form.projectName,'未保存项目')
    assert.deepEqual(s.calls,['confirm'])
  })
  test(`${name}：清空完成后重新启用新草稿，不能恢复旧内容`,async()=>{
    const s=scenario();await s.run()
    assert.equal(s.context.form.projectName,'')
    assert.equal(s.context.form.socialPostRequest,'')
    if(name!=='标注')assert.equal(s.context.clientManagerBaseline.value,'current-user')
    assert.ok(s.calls.indexOf('clear-draft')<s.calls.indexOf('reset'))
    assert.ok(s.calls.indexOf('reset')<s.calls.indexOf('fresh:create'))
    if(name==='标注')assert.equal(s.context.createClearGeneration.value,1)
    if(name==='口译')assert.equal(s.context.projectCreateIdempotencyKey.value,'new-key')
  })
  test(`${name}：编辑态与保存期间均不清空`,async()=>{
    for(const options of [{id:'existing'},{busy:true}]){
      const s=scenario(options);await s.run()
      assert.equal(s.context.form.projectName,'未保存项目')
      assert.deepEqual(s.calls,[])
    }
  })
}
