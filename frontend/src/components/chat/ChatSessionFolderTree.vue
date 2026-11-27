<template>
  <section ref="panel" class="chat-folder-tree" aria-label="会话分组" :style="{ height: `${panelHeight}px` }">
    <div class="chat-folder-tree__heading"><strong>会话分组</strong><span class="chat-folder-tree__heading-actions"><el-button v-if="categories.canManage" link :disabled="!!editing" @click.stop="start(null, null, true)"><el-icon><ChatDotRound /></el-icon>新建一级会话</el-button><el-button v-if="categories.canManage" link :disabled="!!editing" @click.stop="start()"><el-icon><Plus /></el-icon>新建分组</el-button></span></div>
    <p v-if="categories.canManage && !categories.hierarchyReady" class="chat-folder-tree__hint">分类管理暂未就绪，请联系系统管理员</p>
    <div class="chat-folder-tree__scroll">
      <div class="chat-folder-tree__all-tools"><button type="button" class="chat-folder-tree__all" :aria-pressed="!selected" @click.stop="$emit('select', '')">全部分组</button><el-button link size="small" :disabled="!expanded.size || !!editing || saving" @click.stop="collapseAll">折叠全部会话</el-button></div>
      <div v-for="root in roots" :key="root.id" class="chat-folder-tree__root" :style="{'--chat-folder-accent':folderAccent(root),'--chat-folder-soft':chatGroupPalette(root).soft}">
        <div class="chat-folder-tree__row" :data-folder-row="root.id" @click.stop="clickRow($event,root)" :class="{ 'is-active': selected === root.id, 'drop-before': dropTarget === root.id && dropSide === 'before', 'drop-after': dropTarget === root.id && dropSide === 'after' }" :draggable="false" @dragstart.stop="beginDrag($event, root.id)" @dragover.prevent="dragOver($event, root.id)" @drop.stop.prevent="drop(root.id)" @dragend="endDrag" @contextmenu="openProjects($event, root)" @keydown.shift.f10="openProjects($event, root)">
          <button v-if="!root.isConversation" type="button" class="chat-folder-tree__toggle" :title="expanded.has(root.id) ? '收起文件夹' : '展开文件夹'" :aria-label="`${expanded.has(root.id) ? '收起' : '展开'}${root.name}`" :aria-expanded="expanded.has(root.id)" @click.stop="toggle(root.id)"><el-icon><FolderOpened v-if="expanded.has(root.id)" /><Folder v-else /></el-icon></button>
          <span v-else class="chat-folder-tree__toggle" aria-hidden="true"><el-icon v-if="root.isConversation"><ChatDotRound /></el-icon><template v-else>#</template></span>
          <span class="chat-folder-tree__grip" :draggable="!editing" @pointerdown="beginPointerDrag($event,root.id)" role="button" tabindex="0" :aria-label="`拖动调整${root.name}顺序`" title="拖动调整顺序，Alt+↑/↓ 微调" @keydown.alt.up.prevent="moveBy(root.id,-1)" @keydown.alt.down.prevent="moveBy(root.id,1)">⠿</span>
          <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === root.id" :data-folder-id="root.id" :aria-expanded="!root.isConversation ? expanded.has(root.id) : undefined" :aria-haspopup="root.id === annotationFolderId ? 'dialog' : undefined" :title="root.id === annotationFolderId ? '右键搜索标注项目，加入会话' : undefined" @click.stop="openChild(root)"><span>{{ root.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(root.id)} 个对话`">{{ count(root.id) }}</small><b v-if="mentionCount(root.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(root.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',root.id)" @keydown.enter.stop.prevent="emit('unread',root.id)" @keydown.space.stop.prevent="emit('unread',root.id)">{{ mentionCount(root.id) > 99 ? '99+' : mentionCount(root.id) }}</b></button>
          <el-button v-if="categories.canManage && !root.isConversation && root.ruleKey!=='personal-following'" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下新建${root.id === resourceFolderId ? '讨论' : '会话'}`" :title="root.id === resourceFolderId ? '新建讨论' : '创建会话'" @click.stop="start(root.id, null, true)"><el-icon><Plus /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.isConversation && root.ruleKey!=='personal-following'" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下创建二级菜单`" title="创建二级菜单" @click.stop="start(root.id, null, false, true)"><el-icon><FolderAdd /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin" link :disabled="!!editing" :aria-label="`重命名${root.name}`" @click.stop="start(root.parentKey, root)"><el-icon><Edit /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin && !root.deletionProtected" link :disabled="!!editing || saving" :aria-label="`${root.isConversation ? '删除会话' : '移除'}${root.name}`" @click.stop="remove(root)"><el-icon><Close /></el-icon></el-button>
        </div>
        <div v-if="expanded.has(root.id) || editing?.parentKey === root.id" class="chat-folder-tree__children">
          <template v-for="child in visibleChildren(root.id)" :key="child.id">
          <el-button v-if="child.isTechnicalEntry" link class="chat-technical-entry" @click.stop="technicalPicker.open()">技术需求</el-button>
          <div v-else class="chat-folder-tree__row" :data-folder-row="child.id" @click.stop="clickRow($event,child)" :style="child.parentKey !== root.id ? {marginLeft:'18px'} : undefined" :class="{ 'is-active': selected === child.id, 'drop-before': dropTarget === child.id && dropSide === 'before', 'drop-after': dropTarget === child.id && dropSide === 'after' }" :draggable="false" @contextmenu="openCategoryMenu($event, child)" @keydown.shift.f10="openCategoryMenu($event, child)" @dragstart.stop="beginDrag($event, child.id)" @dragover.prevent="dragOver($event, child.id)" @drop.stop.prevent="drop(child.id)" @dragend="endDrag">
            <button v-if="!child.isConversation && children(child.id).length" type="button" class="chat-folder-tree__toggle" :aria-label="`${expanded.has(child.id) ? '收起' : '展开'}${child.name}`" :aria-expanded="expanded.has(child.id)" @click.stop="toggle(child.id)"><el-icon><FolderOpened v-if="expanded.has(child.id)" /><Folder v-else /></el-icon></button>
            <span class="chat-folder-tree__grip" :draggable="!editing && !child.builtin" @pointerdown="beginPointerDrag($event,child.id)" role="button" tabindex="0" :aria-label="`拖动调整${child.name}顺序`" title="拖动调整顺序，Alt+↑/↓ 微调" @keydown.alt.up.prevent="moveBy(child.id,-1)" @keydown.alt.down.prevent="moveBy(child.id,1)">⠿</span>
            <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === child.id" :aria-expanded="!child.isConversation ? expanded.has(child.id) : undefined" @click.stop="openChild(child)"><el-icon v-if="child.statusIcon" aria-hidden="true"><component :is="statusIcons[child.statusIcon]" /></el-icon><el-icon v-else-if="child.ruleKey === 'project-status'" aria-hidden="true"><Folder /></el-icon><el-icon v-else-if="child.conversationIcon" aria-hidden="true"><component :is="statusIcons[child.conversationIcon]" /></el-icon><el-icon v-else-if="child.isConversation"><ChatDotRound /></el-icon><span>{{ child.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(child.id)} 个对话`">{{ count(child.id) }}</small><b v-if="mentionCount(child.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(child.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',child.id)" @keydown.enter.stop.prevent="emit('unread',child.id)" @keydown.space.stop.prevent="emit('unread',child.id)">{{ mentionCount(child.id) > 99 ? '99+' : mentionCount(child.id) }}</b></button>
            <el-button v-if="categories.canManage && !child.builtin && !child.isConversation && child.parentKey === root.id" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${child.name}下新建会话`" title="新建会话" @click.stop="start(child.id, null, true)"><el-icon><Plus /></el-icon></el-button>
            <el-button v-if="categories.canManage && !child.builtin" link :disabled="!!editing" :aria-label="`重命名${child.name}`" @click.stop="start(child.parentKey, child)"><el-icon><Edit /></el-icon></el-button><el-button v-if="categories.canManage && !child.builtin && !child.deletionProtected" link :disabled="!!editing || saving" :aria-label="`${child.isConversation ? '删除会话' : '删除分类'}${child.name}`" title="删除" @click.stop="remove(child)"><el-icon><Close /></el-icon></el-button>
          </div>
          <ChatInlineNameEditor v-if="editing?.parentKey === child.id" :key="editKey" :initial-name="editing.name" label="会话名称" :saving="saving" :error="error" @save="save" @cancel="cancel" />
          </template>
          <ChatInlineNameEditor v-if="editing?.parentKey === root.id" :key="editKey" :initial-name="editing.name" :label="editing?.directory || editing?.id && !editing?.isConversation ? '二级菜单名称' : '会话名称'" :saving="saving" :error="error" @save="save" @cancel="cancel" />
          <small v-if="!children(root.id).length && editing?.parentKey !== root.id" class="chat-folder-tree__hint">暂无会话或分类</small>
        </div>
        <ChatInlineNameEditor v-if="editing?.id === root.id && !editing.parentKey" :key="editKey" :initial-name="editing.name" :label="editing.isConversation || editing.conversation ? '一级会话名称' : '一级目录名称'" :saving="saving" :error="error" @save="save" @cancel="cancel" />
      </div>
      <ChatInlineNameEditor v-if="editing && !editing.id && !editing.parentKey" :key="editKey" :label="editing.isConversation || editing.conversation ? '一级会话名称' : '一级目录名称'" :saving="saving" :error="error" @save="save" @cancel="cancel" />
    </div>
    <div class="chat-folder-tree__resize" role="separator" aria-label="调整分组区域高度" aria-orientation="horizontal" tabindex="0" :aria-valuenow="panelHeight" :aria-valuemin="100" :aria-valuemax="maxHeight()" @pointerdown="beginResize" @keydown.up.prevent="resizeBy(-20)" @keydown.down.prevent="resizeBy(20)" />
    <el-popover v-model:visible="annotationMenuVisible" :virtual-ref="annotationMenuAnchor" :z-index="annotationMenuZ" virtual-triggering :trigger="[]" placement="right-start" :width="160">
      <div v-if="categoryMenuTarget" class="chat-folder-tree__context-menu"><el-button v-if="!categoryMenuTarget.isConversation" text @click.stop="categoryCommand('create')">新建会话</el-button><el-button text @click.stop="categoryCommand('rename')">重命名</el-button><el-button v-if="!categoryMenuTarget.deletionProtected" text type="danger" @click.stop="categoryCommand('delete')">删除</el-button></div>
      <div v-else class="chat-folder-tree__context-menu"><el-button text @click.stop="annotationMenuVisible = false; emit('browse-annotation')">项目搜索</el-button><el-button v-if="hasPermission('projects:write')" text @click.stop="annotationMenuVisible = false; createRequest++">新增项目</el-button><el-button text @click.stop="annotationMenuVisible=false;technicalPicker.open()">技术需求</el-button></div>
    </el-popover>
    <TechnicalRequirementsPicker ref="technicalPicker" />
    <el-config-provider v-if="createRequest" :z-index="annotationMenuZ+10"><AnnotationProjectCreator embedded create-only :create-request="createRequest" /></el-config-provider>
  </section>
</template>
<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { FolderOpened, ChatDotRound, Close, Edit, FolderAdd, Plus, Loading, Clock, CircleClose, CircleCheck, Document, Folder, Grid, UserFilled, Promotion, School, MoreFilled } from '@element-plus/icons-vue'
import { useChatSessionCategories } from '@/composables/useChatSessionCategories'
import { annotationFolderEntries, annotationFolderId, resourceFolderId, sessionFolderCount, sessionFolderMentionUnread, sessionFolderNodes, placeCompanyConversations } from '@/utils/chatSessionFolders'
import { hasPermission } from '@/utils/permission'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import {chatGroupPalette} from '@/utils/chatGroupColors'
import TechnicalRequirementsPicker from './TechnicalRequirementsPicker.vue'
const technicalPicker=ref()
function folderAccent(row){
  return chatGroupPalette(row).accent
}
const statusIcons = { Loading, Clock, CircleClose, CircleCheck, Document, Grid, UserFilled, Promotion, School, MoreFilled, ChatDotRound }
const props = defineProps({ active: { type: Boolean, default: true }, selected: { type: String, default: '' }, sessions: { type: Array, default: () => [] } })
const emit = defineEmits(['select', 'changed', 'browse-annotation', 'open-conversation', 'unread'])
function openProjects(event, row) {
  if (row.isConversation) return openCategoryMenu(event, row)
  if (row.id !== annotationFolderId || !hasPermission('projects:read')) return
  showContextMenu(event)
}
function openCategoryMenu(event, row) {
  if (!categories.canManage || row.builtin || editing.value || saving.value) return
  showContextMenu(event, row)
}
function showContextMenu(event, row=null) {
  event.preventDefault(); event.stopPropagation()
  categoryMenuTarget.value = row
  let topZ = 2100
  for (let element = event.currentTarget; element; element = element.parentElement) {
    topZ = Math.max(topZ, Number.parseInt(window.getComputedStyle(element).zIndex, 10) || 0)
  }
  annotationMenuZ.value = topZ + 1
  annotationMenuAnchor.value = event.currentTarget; annotationMenuVisible.value = true
}
const annotationMenuVisible = ref(false), annotationMenuAnchor = ref(null)
const categoryMenuTarget = ref(null)
function categoryCommand(command) {
  const row = categoryMenuTarget.value
  annotationMenuVisible.value = false
  if (!row || !categories.canManage) return
  if (command === 'create') start(row.id, null, true)
  else if (command === 'rename') start(row.parentKey, row)
  else if (command === 'delete') void remove(row)
}
const annotationMenuZ = ref(2101)
const createRequest = ref(0)
const AnnotationProjectCreator = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const { categories, create, update, refresh } = useChatSessionCategories()
const nodes = computed(() => sessionFolderNodes(categories.items, { technicalAccess: categories.technicalAccess }))
const preferenceKey = `xinshi.chatFolderLayout.${localStorage.getItem('user_id') || 'anonymous'}`
let saved = {}
try { saved = JSON.parse(localStorage.getItem(preferenceKey) || '{}') || {} } catch { /* 使用默认布局。 */ }
const order = ref(Array.isArray(saved.order) ? saved.order.filter(id => typeof id === 'string') : [])
const panel = ref(), panelHeight = ref(Math.max(100, Math.min(Number(saved.height) || 270, window.innerHeight * .55))), dragged = ref('')
const manualOrder = ref(saved.orderVersion === 2 && saved.manualOrder === true)
const dropTarget = ref(''), dropSide = ref('before')
const roots = computed(() => { const rows = nodes.value.filter(row => !row.parentKey).sort((a,b)=>rank(a.id)-rank(b.id)); return manualOrder.value ? rows : placeCompanyConversations(rows) })
const rank = id => order.value.includes(id) ? order.value.indexOf(id) : order.value.length
function persist() { try { localStorage.setItem(preferenceKey, JSON.stringify({ order: order.value, height: panelHeight.value, manualOrder: manualOrder.value, orderVersion: 2, expanded: [...expanded.value] })) } catch { /* 本次调整仍然生效。 */ } }
function beginDrag(event, id) {
  const row=nodes.value.find(item=>item.id===id)
  if (editing.value || row?.builtin && row.parentKey) { event.preventDefault(); return }
  dragged.value=id;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-xinshi-folder',id)
}
function endDrag(){dragged.value='';dropTarget.value=''}
function dragOver(event,id){
  if(!dragged.value)return
  const source=nodes.value.find(row=>row.id===dragged.value),target=nodes.value.find(row=>row.id===id)
  if(!target||target.id===source?.id||(source?.parentKey||'')!==(target.parentKey||''))return
  dropTarget.value=id;dropSide.value=event.clientY<event.currentTarget.getBoundingClientRect().top+event.currentTarget.offsetHeight/2?'before':'after'
  event.dataTransfer.dropEffect='move'
  const scroll=panel.value?.querySelector('.chat-folder-tree__scroll'),rect=scroll?.getBoundingClientRect()
  if(rect){if(event.clientY<rect.top+36)scroll.scrollTop-=18;else if(event.clientY>rect.bottom-36)scroll.scrollTop+=18}
}
function saveOrder(ids,parent){order.value=[...order.value.filter(key=>!ids.includes(key)),...ids];if(!parent)manualOrder.value=true;persist()}
function drop(id) {
  if(!dragged.value||dragged.value===id)return endDrag()
  const parent=nodes.value.find(row=>row.id===id)?.parentKey||''
  if((nodes.value.find(row=>row.id===dragged.value)?.parentKey||'')!==parent)return endDrag()
  const ids=(parent?children(parent):roots.value).map(row=>row.id).filter(key=>key!==dragged.value)
  const to=ids.indexOf(id);if(to<0)return endDrag()
  ids.splice(to+(dropSide.value==='after'?1:0),0,dragged.value);saveOrder(ids,parent);endDrag()
}
function moveBy(id,delta){
  const row=nodes.value.find(item=>item.id===id);if(!row||editing.value||row.builtin&&row.parentKey)return
  const ids=(row.parentKey?children(row.parentKey):roots.value).map(item=>item.id),from=ids.indexOf(id),to=from+delta
  if(from<0||to<0||to>=ids.length)return
  ids.splice(from,1);ids.splice(to,0,id);saveOrder(ids,row.parentKey)
}
let stopPointerDrag=()=>{}
function beginPointerDrag(event,id){
  const row=nodes.value.find(item=>item.id===id)
  if(event.button!==0||editing.value||!row||row.builtin&&row.parentKey)return
  event.preventDefault();event.stopPropagation();stopPointerDrag()
  const handle=event.currentTarget,startX=event.clientX,startY=event.clientY,pointer=event.pointerId
  let moved=false,x=startX,y=startY
  handle.setPointerCapture(pointer)
  const update=()=>{
    if(!moved)return
    const scroll=panel.value?.querySelector('.chat-folder-tree__scroll'),rect=scroll?.getBoundingClientRect()
    if(rect){if(y<rect.top+36)scroll.scrollTop-=14;else if(y>rect.bottom-36)scroll.scrollTop+=14}
    const element=document.elementFromPoint(x,y)?.closest('.chat-folder-tree__row[data-folder-row]')
    const target=nodes.value.find(item=>item.id===element?.dataset.folderRow)
    if(!target||target.id===id||(row.parentKey||'')!==(target.parentKey||'')){dropTarget.value='';return}
    dropTarget.value=target.id;const bounds=element.getBoundingClientRect();dropSide.value=y<bounds.top+bounds.height/2?'before':'after'
  }
  const move=e=>{x=e.clientX;y=e.clientY;if(!moved&&Math.hypot(x-startX,y-startY)>=4){moved=true;dragged.value=id}update()}
  const up=()=>{if(moved&&dropTarget.value)drop(dropTarget.value);stopPointerDrag()}
  const cancel=()=>stopPointerDrag()
  const timer=window.setInterval(update,40)
  stopPointerDrag=()=>{window.clearInterval(timer);handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',up);handle.removeEventListener('pointercancel',cancel);if(handle.hasPointerCapture(pointer))handle.releasePointerCapture(pointer);endDrag()}
  handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',up);handle.addEventListener('pointercancel',cancel)
}
onBeforeUnmount(()=>stopPointerDrag())
function maxHeight() { return Math.max(100, Math.floor((panel.value?.parentElement?.clientHeight || window.innerHeight) - 220)) }
function resizeBy(delta) { panelHeight.value = Math.max(100, Math.min(maxHeight(), panelHeight.value + delta)); persist() }
let stopResize = () => {}
function beginResize(event) {
  if (event.button !== 0) return
  event.preventDefault(); stopResize()
  const y = event.clientY, height = panelHeight.value, handle = event.currentTarget
  handle.setPointerCapture(event.pointerId)
  const move = e => { panelHeight.value = Math.max(100, Math.min(maxHeight(), height + e.clientY - y)) }
  stopResize = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', stopResize); handle.removeEventListener('pointercancel', stopResize); if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId); persist() }
  handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', stopResize); handle.addEventListener('pointercancel', stopResize)
}
onBeforeUnmount(() => stopResize())
const children = id => nodes.value.filter(row => row.parentKey === id).sort((a, b) => Number(!!b.fixedTop) - Number(!!a.fixedTop) || rank(a.id) - rank(b.id))
const visibleChildren = id => annotationFolderEntries(children(id), id).flatMap(row => [row, ...(expanded.value.has(row.id) ? children(row.id) : [])])
const count = id => sessionFolderCount(props.sessions, id, nodes.value)
const expanded = ref(new Set(Array.isArray(saved.expanded) ? saved.expanded.filter(id=>typeof id==='string') : []))
watch(expanded,()=>persist(),{flush:'sync'})
watch(()=>props.active,active=>{if(!active)persist()})
onBeforeUnmount(()=>persist())
function collapseAll(){expanded.value=new Set()}
const editing = ref(null), saving = ref(false), error = ref(''), editKey = ref(0)
function toggle(id) { const value = new Set(expanded.value); value.has(id) ? value.delete(id) : value.add(id); expanded.value = value }
async function reveal(id=props.selected){
  const row=nodes.value.find(row=>row.id===id);if(!row)return
  // 自动定位只滚动到分组，不展开二级目录；展开由用户点击箭头控制。
  await nextTick()
  const scroll=panel.value?.querySelector('.chat-folder-tree__scroll'),target=Array.from(panel.value?.querySelectorAll('.chat-folder-tree__row') || []).find(element => element.querySelector('.chat-folder-tree__name')?.getAttribute('data-folder-id') === (row.parentKey || row.id))
  if(scroll&&target){const a=target.getBoundingClientRect(),b=scroll.getBoundingClientRect();if(a.top<b.top||a.bottom>b.bottom)scroll.scrollTo({top:scroll.scrollTop+a.top-b.top,behavior:'smooth'})}
}
watch(()=>[props.selected,nodes.value.length],()=>reveal(),{immediate:true,flush:'post'})
defineExpose({reveal})
const mentionCount = id => sessionFolderMentionUnread(props.sessions, id, nodes.value)
function start(parentKey = null, row = null, conversation = false, directory = false) {
  if (editing.value || !categories.canManage || !canStartChatNameEditing()) return
  if (parentKey && !categories.hierarchyReady) return
  editing.value = row ? { ...row } : { id: null, name: '', parentKey, conversation, directory }
  if (parentKey) expanded.value = new Set([...expanded.value, parentKey, nodes.value.find(item => item.id === parentKey)?.parentKey].filter(Boolean))
  error.value = ''; editKey.value++
}
function cancel() { if (!saving.value) { editing.value = null; error.value = '' } }
function clickRow(event,row) {
  // 操作按钮、未读提醒和拖动手柄有独立交互，不能再触发行展开。
  if(event.target.closest?.('button,input,textarea,a,[role="button"],.chat-folder-tree__grip'))return
  openChild(row)
}
function openChild(row) {
  if(!row.isConversation)toggle(row.id)
  emit('select', row.id)
  if (row.isConversation) emit('open-conversation', { key: `discussion:${row.id}`, projectId: row.id, projectType: 'discussion', title: row.name, subtitle: '群聊', deletionProtected:!!row.deletionProtected })
}
async function remove(row) {
  if (!categories.canManage || row.builtin || row.deletionProtected || editing.value || saving.value) return
  const label = row.isConversation ? '会话' : row.parentKey ? '分类' : '分组'
  try { await ElMessageBox.confirm(row.isConversation ? `删除“${row.name}”会话？删除后停止访问，历史消息保留。` : `删除“${row.name}”${label}？其中的会话和历史消息会保留。`, `删除${label}`, { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
  saving.value = true
  try { await update(row, { active: false }); if (props.selected === row.id || children(row.id).some(child => child.id === props.selected)) emit('select', ''); emit('changed'); ElMessage.success(`${label}已删除，历史消息保留`); if (row.isConversation) window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: { projectType: 'discussion', projectId: row.id } })) }
  catch (e) { ElMessage.error(e.message || '移除失败'); await refresh().catch(() => {}) }
  finally { saving.value = false }
}
async function save(name) {
  if (saving.value || !editing.value) return
  saving.value = true; error.value = ''
  try {
    const target = editing.value
    const row = target.id ? await update(target, { name }) : await create(name, target.parentKey, !!target.conversation, !!target.directory)
    editing.value = null; emit('changed'); emit('select', row.id)
    if (!target.id && row.isConversation) openChild(row)
  } catch (e) {
    error.value = e.message; await refresh().catch(() => {})
    const current = categories.items.find(row => row.id === editing.value?.id)
    if (current && editing.value) editing.value.revision = current.revision
  } finally { saving.value = false }
}
</script>
<style scoped>
.chat-folder-tree__root>.chat-folder-tree__row{border:1px solid #dce6ef;border-left:3px solid var(--chat-folder-accent,#60758b);background:#fff;margin-bottom:4px;padding-left:3px}
.chat-folder-tree__children .chat-folder-tree__row{border-left:3px solid transparent;padding-left:3px}
.chat-folder-tree__children .chat-folder-tree__row.is-active{border-left-color:var(--chat-folder-accent,#60758b);box-shadow:inset 0 0 0 1px #c6d7e5}
.chat-folder-tree__context-menu{display:flex;flex-direction:column;align-items:stretch;gap:6px}
.chat-folder-tree__context-menu .el-button{margin:0;justify-content:flex-start}
.chat-folder-tree{display:flex;flex-direction:column;position:relative;box-sizing:border-box;flex:0 1 auto;min-height:100px;max-height:60%;padding:8px 10px 10px;border-bottom:1px solid #e6eaf0;color:#475569;font-size:12px}
.chat-folder-tree__heading{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px}.chat-folder-tree__heading strong{font-weight:500}.chat-folder-tree__heading .el-button{font-size:11px}.chat-folder-tree__heading-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.chat-folder-tree__heading-actions .el-button{margin:0}
.chat-folder-tree__scroll{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}.chat-folder-tree__row{cursor:pointer;display:flex;align-items:center;gap:3px;min-height:30px;border-radius:5px}.chat-folder-tree__row.is-active{background:var(--color-primary-soft);color:var(--color-primary-hover)}
.chat-folder-tree__resize{position:absolute;bottom:0;left:0;right:0;height:9px;cursor:row-resize;touch-action:none}.chat-folder-tree__resize:after{content:'';display:block;width:36px;height:3px;border-radius:3px;background:#cbd5e1;margin:3px auto}.chat-folder-tree__resize:hover:after,.chat-folder-tree__resize:focus:after{background:var(--el-color-primary)}.chat-folder-tree__grip{display:inline-flex;align-items:center;justify-content:center;flex:none;min-width:24px;min-height:28px;padding:0 3px;cursor:grab;touch-action:none;opacity:.65;color:#64748b;user-select:none}.chat-folder-tree__grip:active{cursor:grabbing}.chat-folder-tree__grip[draggable="false"]{display:none}.chat-folder-tree__row{position:relative}.chat-folder-tree__row.drop-before:before,.chat-folder-tree__row.drop-after:after{content:"";position:absolute;left:0;right:0;height:3px;background:var(--el-color-primary);z-index:2;pointer-events:none}.chat-folder-tree__row.drop-before:before{top:0}.chat-folder-tree__row.drop-after:after{bottom:0}.chat-folder-tree__row:hover .chat-folder-tree__grip{opacity:1}
.chat-folder-tree button{font:inherit;color:inherit;cursor:pointer}.chat-folder-tree__all,.chat-folder-tree__toggle,.chat-folder-tree__name{border:0;background:transparent}.chat-folder-tree__all{padding:6px 8px}.chat-folder-tree__all[aria-pressed="true"]{color:var(--color-primary-hover);font-weight:600}.chat-folder-tree__toggle{color:#64748b;display:flex;align-items:center;justify-content:center;flex:none;width:20px;padding:5px 0}.chat-folder-tree__name{display:flex;align-items:center;gap:6px;flex:1;min-width:0;padding:6px 2px;text-align:left}.chat-folder-tree__name span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chat-folder-tree__row>.el-button{flex:none;margin:0;padding:4px}.chat-folder-tree__children{padding-left:28px}.chat-folder-tree__hint{display:block;margin:4px 0;color:#94a3b8;font-size:11px}.chat-folder-tree__mention{color:#dc2626}.chat-folder-tree button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}
.chat-folder-tree__name>span{flex:1}.chat-folder-tree__count{flex:none;min-width:20px;box-sizing:border-box;padding:1px 6px;border-radius:7px;background:#e9eef5;color:#64748b;text-align:center;font-size:10px;font-variant-numeric:tabular-nums}.chat-folder-tree__row.is-active .chat-folder-tree__count{background:#dbe6f7;color:#4267a5}.chat-folder-tree__children{margin-left:10px;padding-left:19px;border-left:1px solid #dde4ed}.chat-folder-tree__row:not(.is-active):hover{background:#edf1f7}
.chat-folder-tree__mention{flex:none;min-width:18px;padding:1px 5px;border-radius:10px;background:#dc2626;color:white;text-align:center;font-size:11px;line-height:16px}
.chat-folder-tree__all-tools{display:flex;align-items:center;justify-content:space-between;gap:8px}.chat-folder-tree__all-tools>.el-button{font-size:11px}
</style>
