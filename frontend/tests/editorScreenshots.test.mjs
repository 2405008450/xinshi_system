import test from 'node:test'
import assert from 'node:assert/strict'
import { screenshotIds,screenshotText,screenshotValue,rememberScreenshotGrant,screenshotGrantHeaders } from '../src/utils/screenshotReferences.js'
import { clampWindow,moveWindow } from '../src/composables/useWindowGeometry.js'
import { registerScreenshotUpload,waitForScreenshotUploads } from '../src/utils/screenshotUploads.js'
const id='aabbccdd-1122-3344-5566-aabbccddeeff'
test('截图引用往返且普通文字空白不改变',()=>{
  const text='项目说明\n\n  '
  assert.equal(screenshotValue(text,[]),text)
  assert.equal(screenshotText(text),text)
  const value=screenshotValue('说明',[id])
  assert.deepEqual(screenshotIds(value),[id]);assert.equal(screenshotText(value),'说明')
})
test('编辑及移除截图时保留服务端引用签名，界面文字不出现签名',()=>{
  const reference=`screenshot://${id}#${'a'.repeat(64)}`
  const original=`说明\n![截图](${reference})`
  assert.deepEqual(screenshotIds(original),[id]);assert.equal(screenshotText(original),'说明')
  assert.equal(screenshotValue('修改说明',screenshotIds(original)),`修改说明\n![截图](${reference})`)
})
test('移动及八方向缩放始终留在视口内，小屏不会被最小尺寸撑出',()=>{
  const viewport={width:700,height:871},start={x:100,y:100,width:400,height:500}
  for(const edge of ['move','n','s','w','e','nw','ne','sw','se'])for(const delta of [-4000,4000]){
    const r=moveWindow(start,edge,delta,delta,viewport)
    assert.ok(r.x>=8&&r.y>=8&&r.x+r.width<=692&&r.y+r.height<=863)
  }
  assert.equal(clampWindow(start,{width:250,height:140}).width,234)
})
test('截图读取授权过期后刷新原记录，并在切换账号后清空',async()=>{
  let user='a';globalThis.localStorage={getItem:key=>key==='token'?user:'uid'}
  const response={headers:{'x-screenshot-grant':'grant-a','x-screenshot-grant-expires':'1'},data:screenshotValue('说明',[id]),config:{method:'get',url:'/record/1'}}
  rememberScreenshotGrant(response)
  let calls=0
  const refresh=async()=>{calls++;rememberScreenshotGrant({...response,headers:{'x-screenshot-grant':'grant-b','x-screenshot-grant-expires':String(Date.now()/1000+600)}})}
  const values=await Promise.all([screenshotGrantHeaders([id],refresh),screenshotGrantHeaders([id],refresh)])
  assert.equal(calls,1);assert.deepEqual(values,['grant-b','grant-b'])
  user='b';assert.equal(await screenshotGrantHeaders([id],refresh),'')
  delete globalThis.localStorage
})
test('保存等待当前表单截图上传，其他表单不会被阻塞',async()=>{
  const element={},container={contains:value=>value===element};let finish,done=false
  registerScreenshotUpload(element,new Promise(resolve=>{finish=resolve}))
  const waiting=waitForScreenshotUploads(container).then(result=>{done=true;return result})
  assert.equal(await waitForScreenshotUploads({contains:()=>false}),true);assert.equal(done,false)
  finish(false);assert.equal(await waiting,false)
})
