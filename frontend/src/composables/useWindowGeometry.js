import { onBeforeUnmount, reactive, watch } from 'vue'
import { notifyWindowAnchors } from '../utils/windowAnchorPosition.js'

export function clampWindow(rect, viewport={width:window.innerWidth,height:window.innerHeight}){
  const width=Math.min(Math.max(280,rect.width),Math.max(1,viewport.width-16)),height=Math.min(Math.max(140,rect.height),Math.max(1,viewport.height-16))
  return {width,height,x:Math.max(8,Math.min(rect.x,viewport.width-width-8)),y:Math.max(8,Math.min(rect.y,viewport.height-height-8))}
}
export function moveWindow(initial,edge,dx,dy,viewport){
  const r={...initial}
  if(edge==='move'){r.x+=dx;r.y+=dy}else{
    if(edge.includes('e'))r.width+=dx;if(edge.includes('s'))r.height+=dy
    if(edge.includes('w')){r.x+=dx;r.width-=dx}if(edge.includes('n')){r.y+=dy;r.height-=dy}
    if(r.width<280){if(edge.includes('w'))r.x=initial.x+initial.width-280;r.width=280}
    if(r.height<140){if(edge.includes('n'))r.y=initial.y+initial.height-140;r.height=140}
  }
  return clampWindow(r,viewport)
}
export function useWindowGeometry(element){
  const state=reactive({rect:null,maximized:false,dragging:false}),saved={rect:null}
  let stop=()=>{}
  let anchorFrame = null
  // post 保证窗口样式已更新；每帧最多刷新一次，拖动、缩放、最大化及复位共用。
  const stopAnchors = watch(() => state.rect, () => {
    if (anchorFrame !== null) return
    anchorFrame = window.requestAnimationFrame(() => {
      notifyWindowAnchors(element())
      // 外层浮层先完成渲染，再校正其中已展开的二级下拉。
      anchorFrame = window.requestAnimationFrame(() => {
        anchorFrame = null
        notifyWindowAnchors(element())
      })
    })
  }, { flush: 'post', deep: true })
  function measure(){const r=element()?.getBoundingClientRect();return r?{x:r.left,y:r.top,width:r.width,height:r.height}:null}
  function set(rect){state.rect=clampWindow(rect)}
  function reset(){stop();state.rect=null;state.maximized=false;saved.rect=null}
  function maximize(){if(state.maximized)return;saved.rect=state.rect||measure();state.maximized=true;state.rect={x:8,y:8,width:window.innerWidth-16,height:window.innerHeight-16}}
  function restore(){if(state.maximized){state.maximized=false;state.rect=saved.rect?clampWindow(saved.rect):null}else reset()}
  function start(event,edge='move'){
    if(event.button!==0||state.maximized)return
    const initial=measure();if(!initial)return
    event.preventDefault();event.stopPropagation();stop();set(initial)
    const x=event.clientX,y=event.clientY,oldSelect=document.body.style.userSelect
    document.body.style.userSelect='none'
    state.dragging=true
    const move=e=>set(moveWindow(initial,edge,e.clientX-x,e.clientY-y))
    stop=()=>{window.removeEventListener('mousemove',move);window.removeEventListener('mouseup',stop);window.removeEventListener('blur',stop);document.body.style.userSelect=oldSelect;state.dragging=false}
    window.addEventListener('mousemove',move);window.addEventListener('mouseup',stop,{once:true});window.addEventListener('blur',stop,{once:true})
  }
  const viewportChanged=()=>{if(state.maximized)state.rect={x:8,y:8,width:window.innerWidth-16,height:window.innerHeight-16};else if(state.rect)set(state.rect)}
  window.addEventListener('resize',viewportChanged)
  onBeforeUnmount(()=>{stop();stopAnchors();if(anchorFrame!==null)window.cancelAnimationFrame(anchorFrame);window.removeEventListener('resize',viewportChanged)})
  return {state,reset,maximize,restore,start}
}
