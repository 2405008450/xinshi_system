import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { ref, computed } from 'vue'
import { DEFAULT_SCREENSHOT_SHORTCUT, readScreenshotShortcut, shortcutFromEvent, shortcutLabel } from '../src/utils/screenshotShortcut.js'
const source=readFileSync(new URL('../src/components/ScreenshotControl.vue',import.meta.url),'utf8').split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm,'')
function setup(cancel=false){
 let stopped=0,draws=[],closed=[],unmount
 const canvas=()=>({width:0,height:0,getContext:()=>({drawImage:(...args)=>draws.push(args)}),toBlob:callback=>callback(new Blob(['image'],{type:'image/png'}))})
 const storage=new Map([['user_id','alice']])
 const context={ref,computed,DEFAULT_SCREENSHOT_SHORTCUT,readScreenshotShortcut,shortcutFromEvent,shortcutLabel,
  localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
  navigator:{mediaDevices:{getDisplayMedia:async()=>{if(cancel)throw Object.assign(Error('cancel'),{name:'NotAllowedError'});return {getTracks:()=>[{stop:()=>stopped++}]}}}},
  document:{createElement:tag=>tag==='video'?{videoWidth:1000,videoHeight:500,play:async()=>{}}:canvas()},
  URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:value=>closed.push(value)},
  ElMessage:{warning(){},error(){},success(){},info(){}},
  onMounted(){},onBeforeUnmount:fn=>{unmount=fn},window:{removeEventListener(){}},setTimeout,Blob,
 }
 const component=runInNewContext(`${source}; ({capture,exportBlob,preview,surface,beginSelection,moveSelection,finishSelection,selection,release,imageUrl,annotator})`,context)
 return {component,draws,closed,stopped:()=>stopped,unmount:()=>unmount()}
}
test('截图成功后立即停止屏幕共享，预览关闭时释放图片；取消授权不生成截图',async()=>{
 const run=setup(),c=run.component
 await c.capture()
 assert.equal(run.stopped(),1)
 assert.equal(c.preview.value,true)
 assert.equal(c.imageUrl.value,'blob:test')
 assert.equal((await c.exportBlob()).type,'image/png')
 c.release()
 assert.deepEqual(run.closed,['blob:test'])
 const canceled=setup(true)
 await canceled.component.capture()
 assert.equal(canceled.component.preview.value,false)
 assert.equal(canceled.draws.length,0)
})
test('反向框选映射到原始分辨率，导出整列坐标正确且不产生网络上传',async()=>{
 const run=setup(),c=run.component
 await c.capture()
 c.surface.value={getBoundingClientRect:()=>({left:10,top:20,width:500,height:250}),setPointerCapture(){}}
 c.beginSelection({button:0,clientX:410,clientY:220,pointerId:1})
 c.moveSelection({clientX:110,clientY:70})
 c.finishSelection()
 await c.exportBlob()
 const args=run.draws[1]
 assert.deepEqual(args.slice(1),[200,100,600,300,0,0,600,300])
 run.unmount()
})


test('下载与复制导出已标注画布，框选后仍从标注结果裁剪',async()=>{
 const run=setup(),c=run.component
 await c.capture()
 const edited=Object.freeze({toBlob:callback=>callback(new Blob(['annotated'],{type:'image/png'}))})
 c.annotator.value={renderCanvas:()=>edited}
 assert.equal(await (await c.exportBlob()).text(),'annotated')
 c.selection.value={x:0.1,y:0.2,width:0.5,height:0.4}
 await c.exportBlob()
 assert.equal(run.draws.at(-1)[0],edited)
})
