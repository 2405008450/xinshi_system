import test from 'node:test'
import assert from 'node:assert/strict'
import { bindColumnResize, resizedColumnWidth, COLUMN_RESIZE_HIT_WIDTH, installTableColumnResize } from '../src/utils/tableColumnResize.js'
import { bindColumnDrag } from '../src/utils/columnDragGesture.js'
class Element {
 constructor(doc){this.ownerDocument=doc;this.children=[];this.style={};this.attrs={};this.listeners=new Map();this.classes=new Set();this.classList={add:(...v)=>v.forEach(x=>this.classes.add(x)),remove:(...v)=>v.forEach(x=>this.classes.delete(x)),contains:x=>this.classes.has(x),[Symbol.iterator]:()=>this.classes.values()};this.rect={left:100,top:10,right:260,bottom:50,width:160,height:40}}
 set className(value){value.split(' ').forEach(x=>this.classes.add(x))}
 setAttribute(key,value){this.attrs[key]=value}
 appendChild(el){el.parentNode=this;this.children.push(el)}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this);this.parentNode=null}
 closest(selector){return selector==='.app-column-resize-handle'&&this.classes.has('app-column-resize-handle')?this:null}
 contains(el){return el===this||this.children.some(child=>child.contains(el))}
 getBoundingClientRect(){return this.rect}
 setPointerCapture(){}
 addEventListener(type,fn,options){const list=this.listeners.get(type)||[];list.push({fn,capture:options===true});this.listeners.set(type,list)}
 removeEventListener(type,fn){this.listeners.set(type,(this.listeners.get(type)||[]).filter(x=>x.fn!==fn))}
 fire(type,values={}){const event={button:0,pointerId:1,clientX:258,clientY:20,target:this,...values,preventDefault(){this.defaultPrevented=true},stopImmediatePropagation(){this.stopped=true}};for(const {fn} of [...(this.listeners.get(type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture))){fn(event);if(event.stopped)break}return event}
}
function setup(t){
 const prior=globalThis.MutationObserver;globalThis.MutationObserver=class{observe(){}disconnect(){}}
 t.after(()=>{globalThis.MutationObserver=prior})
 const doc=new Element();doc.ownerDocument=doc;doc.createElement=()=>new Element(doc);doc.body=new Element(doc);doc.documentElement=new Element(doc);doc.defaultView=new Element(doc);doc.defaultView.setTimeout=setTimeout
 const root=new Element(doc),header=new Element(doc);root.appendChild(header);root.rect={left:100,top:10,right:500,bottom:300,width:400,height:290}
 let width=200;const changes=[];const entry={element:header,width:200,minimum:40,label:'项目名称'}
 const cleanup=bindColumnResize(root,()=>[{...entry,width}],(_entry,next,old)=>{changes.push({next,old});width=next})
 const handle=header.children[0]
 return {doc,root,header,handle,changes,cleanup,get width(){return width}}
}
test('列宽计算适配80%/125%缩放并限制最小宽度',()=>{
 assert.equal(COLUMN_RESIZE_HIT_WIDTH,14)
 assert.equal(resizedColumnWidth(200,40,.8),250)
 assert.equal(resizedColumnWidth(200,50,1.25),240)
 assert.equal(resizedColumnWidth(200,-500,.8),40)
})
test('扩大后的边界手柄优先于字段排序，松开后只提交列宽',async t=>{
 const f=setup(t);let sorted=0
 const stopOrder=bindColumnDrag(f.root,()=> 'name',()=>{sorted++})
 const down=f.root.fire('pointerdown',{target:f.handle})
 assert.equal(down.defaultPrevented,true);assert.equal(down.stopped,true)
 f.doc.fire('pointermove',{clientX:290});assert.equal(f.width,200)
 f.doc.fire('pointerup',{clientX:290});assert.deepEqual(f.changes,[{next:240,old:200}]);assert.equal(sorted,0)
 assert.equal(f.doc.body.children.length,0)
 stopOrder();f.cleanup()
})
test('拖动取消和窗口失焦均清理状态，不改列宽，卸载移除手柄',t=>{
 const f=setup(t)
 f.root.fire('pointerdown',{target:f.handle});f.doc.fire('pointermove',{clientX:300});f.doc.fire('pointercancel')
 assert.equal(f.changes.length,0);assert.equal(f.doc.body.children.length,0)
 f.root.fire('pointerdown',{target:f.handle});f.doc.defaultView.fire('blur')
 assert.equal(f.changes.length,0)
 f.cleanup();assert.equal(f.header.children.length,0)
})
test('每条边框可用方向键调整，Shift加速；左右键不触发排序',async t=>{
 const f=setup(t)
 const event=f.root.fire('keydown',{target:f.handle,key:'ArrowRight',shiftKey:true})
 assert.equal(event.stopped,true);assert.deepEqual(f.changes,[{next:240,old:200}])
 await Promise.resolve()
 assert.equal(f.handle.attrs['aria-valuenow'],'240')
 f.root.fire('keydown',{target:f.handle,key:'ArrowLeft',shiftKey:false})
 assert.equal(f.width,232)
 f.cleanup()
})

test('表体整条竖线两侧可拖动，宽度计算仍遵循页面缩放',t=>{
 const f=setup(t),cell=new Element(f.doc)
 cell.closest=selector=>selector==='td'?cell:null
 f.root.appendChild(cell)
 f.root.fire('pointermove',{target:cell,clientX:265})
 assert.equal(f.root.classList.contains('app-column-resize-hover'),true)
 f.root.fire('pointerdown',{target:cell,clientX:265})
 f.doc.fire('pointerup',{clientX:297})
 assert.deepEqual(f.changes,[{next:240,old:200}])
 f.cleanup()
})
test('公共安装覆盖最右列和原本不可调整列；排序重建后保留当前列宽',async t=>{
 const f=setup(t);f.cleanup()
 let mixin,layouts=0,emits=[]
 installTableColumnResize({mixin:value=>{mixin=value}})
 const old={id:'el-table_1_column_1',property:'customer',label:'客户',width:200,realWidth:200,resizable:false,type:'default'}
 f.header.classList.add(old.id);f.header.closest=selector=>selector==='.el-table'?f.root:null
 f.header.offsetWidth=200
 f.root.querySelectorAll=()=>[f.header];f.root.querySelector=()=>f.header
 const internal={store:{states:{_columns:{value:[old]}},scheduleLayout:()=>{layouts++}},emit:(...args)=>emits.push(args)}
 const context={$options:{name:'ElTable'},$:internal,$el:f.root}
 mixin.mounted.call(context)
 assert.equal(f.header.children.length,1)
 f.root.fire('keydown',{target:f.header.children[0],key:'ArrowRight',shiftKey:false})
 assert.equal(old.width,208);assert.equal(old.realWidth,208)
 assert.equal(emits[0][0],'header-dragend')
 const rebuilt={...old,id:'el-table_1_column_2',width:120,realWidth:120}
 internal.store.states._columns.value=[rebuilt]
 f.header.classList.remove(old.id);f.header.classList.add(rebuilt.id)
 await Promise.resolve()
 assert.equal(rebuilt.width,208)
 assert.ok(layouts>=2)
 mixin.beforeUnmount.call(context)
 assert.equal(f.header.children.length,0)
})
