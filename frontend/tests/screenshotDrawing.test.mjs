import test from 'node:test'
import assert from 'node:assert/strict'
import { drawScreenshotMark } from '../src/utils/screenshotDrawing.js'
function fixture(){const calls=[];const context={canvas:{},...Object.fromEntries(['save','restore','beginPath','strokeRect','ellipse','stroke','moveTo','lineTo','fillText','drawImage'].map(name=>[name,(...args)=>calls.push([name,...args])]))};return {context,calls}}
test('反向拖动方框、圆框使用正确位置与宽高',()=>{
 const {context,calls}=fixture(),mark={start:{x:80,y:60},end:{x:20,y:10},color:'#ff0000',size:4}
 drawScreenshotMark(context,{...mark,type:'rectangle'})
 assert.deepEqual(calls.find(x=>x[0]==='strokeRect'),['strokeRect',20,10,60,50])
 drawScreenshotMark(context,{...mark,type:'ellipse'})
 assert.deepEqual(calls.find(x=>x[0]==='ellipse').slice(1,5),[50,35,30,25])
})
test('箭头包含箭头端点，文字与表情使用用户内容',()=>{
 const {context,calls}=fixture(),start={x:10,y:20},end={x:80,y:60}
 drawScreenshotMark(context,{type:'arrow',start,end})
 assert.equal(calls.filter(x=>x[0]==='lineTo').length,3)
 drawScreenshotMark(context,{type:'text',start,text:'第一行\n第二行',size:4})
 drawScreenshotMark(context,{type:'emoji',start,text:'👍',size:4})
 assert.deepEqual(calls.filter(x=>x[0]==='fillText').map(x=>x[1]),['第一行','第二行','👍'])
})
test('马赛克覆盖选择区域，并关闭平滑放大以保留块状遮挡',()=>{
 const {context,calls}=fixture(),small={width:0,height:0,getContext:()=>({drawImage(){}})}
 drawScreenshotMark(context,{type:'mosaic',start:{x:0,y:0},end:{x:160,y:80},size:4},()=>small)
 assert.equal(small.width,10);assert.equal(small.height,5)
 assert.equal(context.imageSmoothingEnabled,false)
 assert.deepEqual(calls.find(x=>x[0]==='drawImage').slice(-4),[0,0,160,80])
})
