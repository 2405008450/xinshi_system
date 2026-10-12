<template>
  <Teleport to="body">
    <div v-if="visible" ref="menuRef" class="chat-message-context-menu" role="menu" aria-label="消息操作菜单" :style="{left:`${position.left}px`,top:`${position.top}px`}" @mousedown.prevent @contextmenu.prevent @keydown="onKeydown">
      <button v-for="item in items" :key="item.id" type="button" role="menuitem" :aria-label="item.label" class="chat-message-context-menu__item" :class="{'is-danger':item.danger,'has-separator':item.separator,'is-active':submenu === item.id}" :title="item.id === 'favorite' ? '收藏（仅自己可见）' : undefined" :aria-haspopup="item.submenu ? 'menu' : undefined" :aria-expanded="item.submenu ? submenu === item.id : undefined" @mouseenter="hover(item,$event)" @click="activate(item,$event)">
        <el-icon><component :is="icons[item.icon]" /></el-icon><span>{{ item.label }}</span><span v-if="item.submenu" aria-hidden="true" class="chat-message-context-menu__arrow">›</span>
      </button>
    </div>
    <div v-if="visible && submenu === 'collect'" ref="submenuRef" class="chat-message-context-menu chat-message-context-menu--submenu" role="menu" aria-label="收录类别" :style="{left:`${subPosition.left}px`,top:`${subPosition.top}px`}" @mousedown.prevent @contextmenu.prevent @keydown="onKeydown">
      <button v-for="category in issueCategories" :key="category.value" type="button" role="menuitem" class="chat-message-context-menu__item" @click="collectIssue(category.value)">{{ category.label }}</button>
    </div>
  </Teleport>
  <ChatMessageTopic v-if="message" ref="topicRef" :message="message" programmatic :show-tag="false" />
</template>
<script setup>
import { computed, getCurrentInstance, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, ChatLineRound, Star, CircleCheck, PriceTag, DocumentAdd, CirclePlus, Select, Delete } from '@element-plus/icons-vue'
import { useResourceIssues } from '@/composables/useResourceIssues'
import { issueCategories } from '@/utils/resourceIssues'
import { buildMessageMenu, clampMessageMenu, nativeMessageContextSelector } from '@/utils/chatMessageMenu'
import ChatMessageTopic from './ChatMessageTopic.vue'
const props = defineProps({ currentUserId: {type:String,default:''}, handlers:{type:Object,default:()=>({})}, canProgress:Boolean, selecting:Boolean, messages:{type:Array,default:()=>[]}, active:{type:Boolean,default:true} })
const { access, collect } = useResourceIssues()
const instanceId = getCurrentInstance().uid
const icons = {copy:CopyDocument,reply:ChatLineRound,favorite:Star,acknowledge:CircleCheck,classify:PriceTag,collect:DocumentAdd,progress:CirclePlus,select:Select,recall:Delete}
const visible=ref(false), message=ref(null), excerpt=ref(''), menuRef=ref(), submenuRef=ref(), topicRef=ref(), submenu=ref('')
const position=reactive({left:0,top:0}), subPosition=reactive({left:0,top:0})
let origin, point={x:0,y:0}, openVersion=0
const items=computed(()=>buildMessageMenu(message.value,{handlers:props.handlers,currentUserId:props.currentUserId,canCollect:access.can_collect,canProgress:props.canProgress,selecting:props.selecting,excerpt:excerpt.value}))
const activeMessageId=computed(()=>visible.value ? String(message.value?.id || '') : '')
function close(restore=false) {
  visible.value=false; submenu.value=''; openVersion++
  if (restore && origin?.isConnected) { const target=origin; nextTick(()=>target.focus?.({preventScroll:true})) }
}
function reposition() {
  if (!menuRef.value) return
  const rect=menuRef.value.getBoundingClientRect()
  Object.assign(position,clampMessageMenu(point,rect,{width:window.innerWidth,height:window.innerHeight}))
}
async function open(event,row) {
  if (!row || row.recalledAt) return
  const context=event.type==='contextmenu' || event.type==='keydown'
  if (context && event.target?.closest?.(nativeMessageContextSelector)) return
  const selection=window.getSelection?.(), root=event.currentTarget
  let selected=''
  if (selection && !selection.isCollapsed && selection.rangeCount) {
    const range=selection.getRangeAt(0)
    if (root.contains(range.startContainer) && root.contains(range.endContainer)) selected=selection.toString().trim()
  }
  message.value=row; excerpt.value=selected
  if (!items.value.length) return
  event.preventDefault(); event.stopPropagation()
  topicRef.value?.close()
  document.dispatchEvent(new CustomEvent('chat-message-menu-opened',{detail:instanceId}))
  const rect=root.getBoundingClientRect()
  origin=root.closest('[data-message-id]')?.querySelector('[data-message-menu-anchor]') || root
  point=context && (event.clientX || event.clientY) ? {x:event.clientX,y:event.clientY} : {x:rect.right,y:rect.bottom}
  submenu.value=''; visible.value=true
  const version=++openVersion
  await nextTick()
  if (version!==openVersion || !visible.value) return
  reposition(); menuRef.value?.querySelector('[role="menuitem"]')?.focus({preventScroll:true})
}
function openKeyboard(event,row) {
  if (event.key==='ContextMenu' || (event.shiftKey && event.key==='F10')) open(event,row)
}
async function showSubmenu(event,focus=false) {
  submenu.value='collect'
  const rect=event.currentTarget.getBoundingClientRect()
  await nextTick()
  if (!visible.value || !submenuRef.value) return
  const size=submenuRef.value.getBoundingClientRect(), menu=menuRef.value.getBoundingClientRect()
  const x=menu.right+4+size.width <= window.innerWidth-8 ? menu.right+4 : menu.left-size.width-4
  Object.assign(subPosition,clampMessageMenu({x,y:rect.top},size,{width:window.innerWidth,height:window.innerHeight}))
  if (focus) submenuRef.value.querySelector('[role="menuitem"]')?.focus({preventScroll:true})
}
function hover(item,event) { if (item.submenu) showSubmenu(event); else submenu.value='' }
async function activate(item,event) {
  if (item.submenu) { await showSubmenu(event,true); return }
  const row=message.value, text=excerpt.value
  if (item.id==='classify') {
    const rect=event.currentTarget.getBoundingClientRect()
    const anchor={left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height,x:rect.x,y:rect.y}
    close()
    await nextTick(); topicRef.value?.openAt(anchor)
    return
  }
  close(!['reply','progress','select','recall'].includes(item.id))
  try { await props.handlers[item.id]?.(row,text) } catch(e) { ElMessage.error(e.detail || e.message || '操作失败，请重试') }
}
function collectIssue(category) { const id=message.value.id; close(); collect(id,category) }
function onKeydown(event) {
  if (event.key==='Tab') { close(); return }
  const root=event.currentTarget, buttons=[...root.querySelectorAll('[role="menuitem"]')], index=buttons.indexOf(document.activeElement)
  if (event.key==='Escape') { event.preventDefault(); event.stopPropagation(); close(true); return }
  if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
    event.preventDefault(); const next=event.key==='Home' ? 0 : event.key==='End' ? buttons.length-1 : (index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length
    buttons[next]?.focus(); return
  }
  if (event.key==='ArrowRight' && root===menuRef.value && items.value[index]?.submenu) { event.preventDefault(); showSubmenu({currentTarget:buttons[index]},true) }
  if (event.key==='ArrowLeft' && root===submenuRef.value) { event.preventDefault(); submenu.value=''; nextTick(()=>menuRef.value?.querySelector('[aria-haspopup="menu"]')?.focus()) }
}
function outside(event) { if (visible.value && !menuRef.value?.contains(event.target) && !submenuRef.value?.contains(event.target)) close() }
function scroll(event) {
  if (event.target?.closest?.('.group-timeline,.chat-list')) topicRef.value?.close()
  if (visible.value && !menuRef.value?.contains(event.target) && !submenuRef.value?.contains(event.target)) close() }
function otherOpened(event) { if (event.detail!==instanceId) { close(); topicRef.value?.close() } }
function leave() { close() }
watch(()=>props.messages,rows=>{
  if (!message.value) return
  const current=rows.find(row=>String(row.id)===String(message.value.id))
  if (!current || current.recalledAt) { close(); topicRef.value?.close() }
  else message.value=current
})
watch(()=>[message.value?.recalledAt,message.value?.canClassify],()=>{ if(message.value?.recalledAt){close();topicRef.value?.close()} else if(!message.value?.canClassify) topicRef.value?.close() })
watch(()=>props.active,value=>{if(!value){close();topicRef.value?.close()}})
onMounted(()=>{
  document.addEventListener('pointerdown',outside,true); document.addEventListener('scroll',scroll,true)
  document.addEventListener('chat-message-menu-opened',otherOpened); document.addEventListener('app-dialog-opened',leave)
  window.addEventListener('resize',leave); window.addEventListener('blur',leave)
})
onBeforeUnmount(()=>{
  document.removeEventListener('pointerdown',outside,true); document.removeEventListener('scroll',scroll,true)
  document.removeEventListener('chat-message-menu-opened',otherOpened); document.removeEventListener('app-dialog-opened',leave)
  window.removeEventListener('resize',leave); window.removeEventListener('blur',leave)
})
defineExpose({open,openKeyboard,close,activeMessageId})
</script>
<style>
.chat-message-context-menu{position:fixed;z-index:100000;width:218px;max-width:calc(100vw - 16px);max-height:calc(100vh - 16px);overflow-y:auto;padding:6px;background:var(--el-bg-color-overlay,#fff);border:1px solid var(--el-border-color-light);border-radius:7px;box-shadow:0 6px 24px rgb(15 23 42 / 18%);box-sizing:border-box}
.chat-message-context-menu--submenu{width:168px;z-index:100001}
.chat-message-context-menu__item{display:flex;align-items:center;gap:10px;width:100%;min-height:34px;padding:7px 10px;border:0;background:transparent;color:var(--el-text-color-primary);font:inherit;font-size:13px;text-align:left;cursor:pointer;border-radius:4px;white-space:nowrap}
.chat-message-context-menu__item:hover,.chat-message-context-menu__item:focus-visible,.chat-message-context-menu__item.is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);outline:none}.chat-message-context-menu__item.is-danger{color:var(--el-color-danger)}.chat-message-context-menu__item.has-separator{border-top:1px solid var(--el-border-color-lighter);border-radius:0;margin-top:4px;padding-top:10px}.chat-message-context-menu__arrow{margin-left:auto;font-size:20px;line-height:12px}
.chat-message-more{flex:none;border:0;border-radius:5px;background:transparent;color:var(--el-text-color-secondary);cursor:pointer;padding:3px 7px;font-size:19px;line-height:22px;opacity:0}.chat-message-more:hover,.chat-message-more:focus-visible{opacity:1;background:var(--el-fill-color-light);outline:2px solid var(--el-color-primary-light-7)}.group-message:hover .chat-message-more,.group-message:focus-within .chat-message-more,.chat-conversation-item:hover .chat-message-more,.chat-conversation-item:focus-within .chat-message-more,.chat-message-card:hover .chat-message-more,.chat-message-card:focus-within .chat-message-more{opacity:1}
@media(max-width:420px){.chat-message-context-menu--submenu{width:152px}}
@media(hover:none){.chat-message-more{opacity:1}}
</style>
