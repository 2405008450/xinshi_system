const MIME='application/x-xinshi-filter-field'
let activePointerDrags=0
export const isAdvancedFilterDockDragging=()=>activePointerDrags>0
export function filterDockStorageKey(path,scope,user){return `advanced-filter-dock:${user||'anonymous'}:${path}:${scope||'default'}`}
export function readDockKeys(storage,key){try{const value=JSON.parse(storage.getItem(key)||'[]');return Array.isArray(value)?[...new Set(value.filter(item=>typeof item==='string'))]:[]}catch{return []}}

// 只移动原控件节点，不复制输入框，不触发业务查询；Vue 绑定与事件保留。
export function createAdvancedFilterDock({root,anchor,scope='',onChange=()=>{}}){
  const reference=anchor||document.querySelector(`[aria-describedby="${root.closest('.el-popper')?.id}"]`)
  const query=reference?.closest('form,.el-form,.search-form,.search-bar,.filter-bar,.filters,.filter-row,.search-area')||reference?.parentElement
  if(!query)return null
  const popup=root.closest('.el-popper')
  const moduleScope=scope||[...(popup?.classList||[])].filter(name=>!['el-popper','is-light','is-dark','app-window-popover'].includes(name)).join('.')||'default'
  const key=filterDockStorageKey(location.pathname,moduleScope,localStorage.getItem('user_id')||localStorage.getItem('user_name'))
  let pinned=new Set(readDockKeys(localStorage,key)),editing=false,dragged=null,pointerDrag=null
  const records=new Map(),host=document.createElement('div'),hint=document.createElement('span')
  host.className='advanced-filter-pinned-row';host.setAttribute('aria-label','常用筛选')
  hint.className='advanced-filter-drop-hint';hint.textContent='将高级筛选项拖到这里，设为常用条件'
  host.append(hint)
  // 放在查询按钮前，同一查询栏可自动换行。
  const action=reference.closest('.el-form-item')
  if(action?.parentElement===query)query.insertBefore(host,action);else query.append(host)
  function persist(){try{localStorage.setItem(key,JSON.stringify([...pinned]))}catch{};onChange()}
  function move(node,parent,before=null){const focused=node.contains(document.activeElement)?document.activeElement:null;parent.insertBefore(node,before);if(focused?.isConnected)focused.focus({preventScroll:true})}
  function place(record){
    const isPinned=pinned.has(record.key)
    if(isPinned){if(record.container.parentElement!==host)move(record.container,host);record.container.removeAttribute('data-advanced-filter-search-hidden')}
    else if(record.home.parentNode&&record.container.parentNode!==record.home.parentNode)move(record.container,record.home.parentNode,record.home.nextSibling)
    record.container.classList.toggle('advanced-filter-pinned-field',isPinned)
    record.button.textContent=isPinned?'移回':'移出'
    record.button.title=isPinned?'移回高级筛选':'移至查询栏'
    record.button.setAttribute('aria-label',`${isPinned?'移回高级筛选':'移至查询栏'}：${record.label}`)
    host.hidden=!editing&&![...records.values()].some(item=>pinned.has(item.key))
  }
  function toggle(record){if(pinned.has(record.key))pinned.delete(record.key);else pinned.add(record.key);place(record);persist()}
  function startPointerDrag(event,record){
    if(event.button!==0)return
    event.preventDefault();event.stopPropagation()
    const startX=event.clientX,startY=event.clientY
    let moving=false,ghost
    const inside=(element,x,y)=>{const r=element.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom}
    function movePointer(next){
      if(!moving&&Math.hypot(next.clientX-startX,next.clientY-startY)>6){moving=true;host.classList.add('is-drop-target');host.hidden=false;ghost=document.createElement('div');ghost.className='advanced-filter-drag-ghost';ghost.textContent=record.label;document.body.append(ghost)}
      if(ghost){ghost.style.left=`${next.clientX+12}px`;ghost.style.top=`${next.clientY+12}px`}
    }
    function finish(next){
      if(moving){
        record.suppressClick=true;setTimeout(()=>{record.suppressClick=false},0)
        if(inside(host,next.clientX,next.clientY)||inside(query,next.clientX,next.clientY)){pinned.add(record.key);place(record);persist()}
        else if(inside(root,next.clientX,next.clientY)){pinned.delete(record.key);place(record);persist()}
      }
      cleanup()
    }
    let cleaned=false
    const cancelOnEscape=next=>{if(next.key==='Escape')cleanup()}
    function cleanup(){if(cleaned)return;cleaned=true;activePointerDrags--;document.removeEventListener('mousemove',movePointer);document.removeEventListener('mouseup',finish);document.removeEventListener('keydown',cancelOnEscape);window.removeEventListener('blur',cleanup);ghost?.remove();host.classList.remove('is-drop-target');host.hidden=!editing&&![...records.values()].some(item=>pinned.has(item.key));pointerDrag=null}
    pointerDrag?.();activePointerDrags++;pointerDrag=cleanup
    document.addEventListener('mousemove',movePointer);document.addEventListener('mouseup',finish);document.addEventListener('keydown',cancelOnEscape);window.addEventListener('blur',cleanup)
  }
  function decorate(fields){
    for(const field of fields){
      if(records.has(field.element))continue
      let id=field.label,index=2
      while([...records.values()].some(item=>item.key===id))id=`${field.label}#${index++}`
      const home=document.createComment(`filter:${id}`),button=document.createElement('button')
      field.container.before(home);button.type='button';button.className='advanced-filter-dock-toggle';button.draggable=true
      const record={...field,key:id,home,button};records.set(field.element,record)
      const label=field.element.querySelector(':scope > .el-form-item__label,:scope > .compact-filter-cell__label,:scope > label,:scope > span')||field.element
      // label 内的按钮不能触发控件聚焦或提交。
      button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(!record.suppressClick)toggle(record)})
      button.addEventListener('mousedown',event=>startPointerDrag(event,record))
      button.addEventListener('dragstart',event=>{dragged=record;event.dataTransfer.setData(MIME,id);event.dataTransfer.effectAllowed='move';host.classList.add('is-drop-target')})
      button.addEventListener('dragend',()=>{dragged=null;host.classList.remove('is-drop-target')})
      label.append(button);place(record)
    }
    for(const [element,record] of records)if(!record.home.isConnected||!element.isConnected){record.container.remove();record.home.remove();record.button.remove();records.delete(element)}
  }
  function drop(event,toPinned){if(!dragged||!event.dataTransfer.types.includes(MIME))return;event.preventDefault();event.stopPropagation();if(toPinned)pinned.add(dragged.key);else pinned.delete(dragged.key);place(dragged);persist()}
  const over=event=>{if(dragged){event.preventDefault();event.dataTransfer.dropEffect='move'}}
  const dropHome=event=>drop(event,false),dropPinned=event=>drop(event,true)
  host.addEventListener('dragover',over);host.addEventListener('drop',dropPinned);root.addEventListener('dragover',over);root.addEventListener('drop',dropHome)
  return {
    decorate,
    fields:()=>[...records.values()],
    setEditing(value){editing=value;root.classList.toggle('advanced-filter-dock-configuring',value);host.classList.toggle('is-configuring',value);hint.hidden=!value;host.hidden=!value&&![...records.values()].some(item=>pinned.has(item.key))},
    isPinned:field=>pinned.has(records.get(field.element)?.key),
    reset(){pinned.clear();for(const item of records.values())place(item);persist()},
    dispose(){pointerDrag?.();root.removeEventListener('dragover',over);root.removeEventListener('drop',dropHome);for(const record of records.values()){if(record.home.parentNode)move(record.container,record.home.parentNode,record.home.nextSibling);record.home.remove();record.button.remove();record.container.classList.remove('advanced-filter-pinned-field')}host.remove();records.clear()},
  }
}
