<template>
  <section ref="panel" class="chat-folder-tree" aria-label="会话分组" :style="{ height: `${panelHeight}px` }">
    <div class="chat-folder-tree__heading"><strong>会话分组</strong><span class="chat-folder-tree__heading-actions"><el-button v-if="categories.canManage" link :disabled="!!editing" @click="start(null, null, true)"><el-icon><ChatDotRound /></el-icon>新建一级会话</el-button><el-button v-if="categories.canManage" link :disabled="!!editing" @click="start()"><el-icon><Plus /></el-icon>新建分组</el-button></span></div>
    <p v-if="categories.canManage && !categories.hierarchyReady" class="chat-folder-tree__hint">分类管理暂未就绪，请联系系统管理员</p>
    <div class="chat-folder-tree__scroll">
      <button type="button" class="chat-folder-tree__all" :aria-pressed="!selected" @click="$emit('select', '')">全部分组</button>
      <div v-for="root in roots" :key="root.id">
        <div class="chat-folder-tree__row" :class="{ 'is-active': selected === root.id }" :draggable="!editing" @dragstart.stop="beginDrag($event, root.id)" @dragover.prevent @drop.stop.prevent="drop(root.id)" @dragend="dragged = ''" @contextmenu="openProjects($event, root)" @keydown.shift.f10="openProjects($event, root)">
          <button v-if="!root.isConversation && root.id !== resourceFolderId" type="button" class="chat-folder-tree__toggle" :aria-label="`${expanded.has(root.id) ? '收起' : '展开'}${root.name}`" :aria-expanded="expanded.has(root.id)" @click="toggle(root.id)"><el-icon><ArrowDown v-if="expanded.has(root.id)" /><ArrowRight v-else /></el-icon></button>
          <span v-else class="chat-folder-tree__toggle" aria-hidden="true"><el-icon v-if="root.isConversation"><ChatDotRound /></el-icon><template v-else>#</template></span>
          <span class="chat-folder-tree__grip" title="拖动调整分组顺序" aria-hidden="true">⠿</span>
          <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === root.id" :data-folder-id="root.id" :aria-haspopup="root.id === annotationFolderId ? 'dialog' : undefined" :title="root.id === annotationFolderId ? '右键搜索标注项目，加入会话' : undefined" @click="openChild(root)"><span>{{ root.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(root.id)} 个对话`">{{ count(root.id) }}</small><b v-if="mentionCount(root.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(root.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',root.id)" @keydown.enter.stop.prevent="emit('unread',root.id)" @keydown.space.stop.prevent="emit('unread',root.id)">{{ mentionCount(root.id) > 99 ? '99+' : mentionCount(root.id) }}</b></button>
          <el-button v-if="categories.canManage && !root.isConversation" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下新建${root.id === resourceFolderId ? '讨论' : '会话'}`" :title="root.id === resourceFolderId ? '新建讨论' : '创建会话'" @click="start(root.id, null, true)"><el-icon><Plus /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.isConversation && root.id !== resourceFolderId" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下创建二级菜单`" title="创建二级菜单" @click="start(root.id, null, false, true)"><el-icon><FolderAdd /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin" link :disabled="!!editing" :aria-label="`重命名${root.name}`" @click="start(root.parentKey, root)"><el-icon><Edit /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin" link :disabled="!!editing || saving" :aria-label="`${root.isConversation ? '删除会话' : '移除'}${root.name}`" @click="remove(root)"><el-icon><Close /></el-icon></el-button>
        </div>
        <div v-if="root.id !== resourceFolderId && expanded.has(root.id) || editing?.parentKey === root.id" class="chat-folder-tree__children">
          <el-button v-if="root.id===annotationFolderId" link class="chat-technical-entry" @click="technicalPicker.open()">技术需求</el-button>
          <template v-for="child in visibleChildren(root.id)" :key="child.id">
          <div class="chat-folder-tree__row" :style="child.parentKey !== root.id ? {marginLeft:'18px'} : undefined" :class="{ 'is-active': selected === child.id }" :draggable="!editing" @contextmenu="openCategoryMenu($event, child)" @keydown.shift.f10="openCategoryMenu($event, child)" @dragstart.stop="beginDrag($event, child.id)" @dragover.prevent @drop.stop.prevent="drop(child.id)" @dragend="dragged = ''">
            <span class="chat-folder-tree__grip" title="拖动调整分类顺序" aria-hidden="true">⠿</span>
            <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === child.id" @click="openChild(child)"><el-icon v-if="child.isConversation"><ChatDotRound /></el-icon><span>{{ child.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(child.id)} 个对话`">{{ count(child.id) }}</small><b v-if="mentionCount(child.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(child.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',child.id)" @keydown.enter.stop.prevent="emit('unread',child.id)" @keydown.space.stop.prevent="emit('unread',child.id)">{{ mentionCount(child.id) > 99 ? '99+' : mentionCount(child.id) }}</b></button>
            <el-button v-if="categories.canManage && !child.builtin && !child.isConversation && child.parentKey === root.id" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${child.name}下新建会话`" title="新建会话" @click="start(child.id, null, true)"><el-icon><Plus /></el-icon></el-button>
            <el-button v-if="categories.canManage && !child.builtin" link :disabled="!!editing" :aria-label="`重命名${child.name}`" @click="start(child.parentKey, child)"><el-icon><Edit /></el-icon></el-button><el-button v-if="categories.canManage && !child.builtin && child.parentKey !== resourceFolderId" link :disabled="!!editing || saving" :aria-label="`${child.isConversation ? '删除会话' : '删除分类'}${child.name}`" title="删除" @click="remove(child)"><el-icon><Close /></el-icon></el-button>
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
      <div v-if="categoryMenuTarget" class="chat-folder-tree__context-menu"><el-button v-if="!categoryMenuTarget.isConversation" text @click="categoryCommand('create')">新建会话</el-button><el-button text @click="categoryCommand('rename')">重命名</el-button><el-button text type="danger" @click="categoryCommand('delete')">删除</el-button></div>
      <div v-else class="chat-folder-tree__context-menu"><el-button text @click="annotationMenuVisible = false; emit('browse-annotation')">项目搜索</el-button><el-button v-if="hasPermission('projects:write')" text @click="annotationMenuVisible = false; createRequest++">新增项目</el-button><el-button text @click="annotationMenuVisible=false;technicalPicker.open()">技术需求</el-button></div>
    </el-popover>
    <TechnicalRequirementsPicker ref="technicalPicker" />
    <el-config-provider v-if="createRequest" :z-index="annotationMenuZ+10"><AnnotationProjectCreator embedded create-only :create-request="createRequest" /></el-config-provider>
  </section>
</template>
<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { ArrowDown, ArrowRight, ChatDotRound, Close, Edit, FolderAdd, Plus } from '@element-plus/icons-vue'
import { useChatSessionCategories } from '@/composables/useChatSessionCategories'
import { annotationFolderId, resourceFolderId, sessionFolderCount, sessionFolderMentionUnread, sessionFolderNodes } from '@/utils/chatSessionFolders'
import { hasPermission } from '@/utils/permission'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import TechnicalRequirementsPicker from './TechnicalRequirementsPicker.vue'
const technicalPicker=ref()
const props = defineProps({ active: { type: Boolean, default: true }, selected: { type: String, default: '' }, sessions: { type: Array, default: () => [] } })
const emit = defineEmits(['select', 'changed', 'browse-annotation', 'open-conversation', 'unread'])
function openProjects(event, row) {
  if (row.isConversation) return openCategoryMenu(event, row)
  if (row.id !== annotationFolderId || !hasPermission('projects:read')) return
  showContextMenu(event)
}
function openCategoryMenu(event, row) {
  if (!categories.canManage || row.builtin || row.parentKey === resourceFolderId || editing.value || saving.value) return
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
const nodes = computed(() => sessionFolderNodes(categories.items))
const preferenceKey = `xinshi.chatFolderLayout.${localStorage.getItem('user_id') || 'anonymous'}`
let saved = {}
try { saved = JSON.parse(localStorage.getItem(preferenceKey) || '{}') || {} } catch { /* 使用默认布局。 */ }
const order = ref(Array.isArray(saved.order) ? saved.order.filter(id => typeof id === 'string') : [])
const panel = ref(), panelHeight = ref(Math.max(100, Math.min(Number(saved.height) || 270, window.innerHeight * .55))), dragged = ref('')
const roots = computed(() => nodes.value.filter(row => !row.parentKey).sort((a, b) => rank(a.id) - rank(b.id)))
const rank = id => order.value.includes(id) ? order.value.indexOf(id) : order.value.length
function persist() { try { localStorage.setItem(preferenceKey, JSON.stringify({ order: order.value, height: panelHeight.value })) } catch { /* 本次调整仍然生效。 */ } }
function beginDrag(event, id) { dragged.value = id; event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', id) }
function drop(id) {
  if (!dragged.value || dragged.value === id) return
  const parent = nodes.value.find(row => row.id === id)?.parentKey || ''
  if ((nodes.value.find(row => row.id === dragged.value)?.parentKey || '') !== parent) return
  const ids = (parent ? children(parent) : roots.value).map(row => row.id), from = ids.indexOf(dragged.value), to = ids.indexOf(id)
  if (from < 0 || to < 0) return
  ids.splice(from, 1); ids.splice(to, 0, dragged.value); order.value = [...order.value.filter(key => !ids.includes(key)), ...ids]; dragged.value = ''; persist()
}
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
const children = id => nodes.value.filter(row => row.parentKey === id).sort((a, b) => rank(a.id) - rank(b.id))
const visibleChildren = id => children(id).flatMap(row => [row, ...children(row.id)])
const count = id => sessionFolderCount(props.sessions, id, nodes.value)
const expanded = ref(new Set())
watch(() => props.active, active => { if (active) expanded.value = new Set() })
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
function openChild(row) {
  emit('select', row.id)
  if (row.isConversation) emit('open-conversation', { key: `discussion:${row.id}`, projectId: row.id, projectType: 'discussion', title: row.name, subtitle: '群聊' })
}
async function remove(row) {
  if (!categories.canManage || row.builtin || editing.value || saving.value) return
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
    editing.value = null; emit('changed'); emit('select', target.parentKey === resourceFolderId ? resourceFolderId : row.id)
    if (!target.id && row.isConversation && target.parentKey !== resourceFolderId) openChild(row)
  } catch (e) {
    error.value = e.message; await refresh().catch(() => {})
    const current = categories.items.find(row => row.id === editing.value?.id)
    if (current && editing.value) editing.value.revision = current.revision
  } finally { saving.value = false }
}
</script>
<style scoped>
.chat-folder-tree__context-menu{display:flex;flex-direction:column;align-items:stretch;gap:6px}
.chat-folder-tree__context-menu .el-button{margin:0;justify-content:flex-start}
.chat-folder-tree{display:flex;flex-direction:column;position:relative;box-sizing:border-box;flex:0 1 auto;min-height:100px;max-height:60%;padding:8px 10px 10px;border-bottom:1px solid #e6eaf0;color:#475569;font-size:12px}
.chat-folder-tree__heading{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px}.chat-folder-tree__heading strong{font-weight:500}.chat-folder-tree__heading .el-button{font-size:11px}.chat-folder-tree__heading-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.chat-folder-tree__heading-actions .el-button{margin:0}
.chat-folder-tree__scroll{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}.chat-folder-tree__row{display:flex;align-items:center;gap:3px;min-height:30px;border-radius:5px}.chat-folder-tree__row.is-active{background:var(--color-primary-soft);color:var(--color-primary-hover)}
.chat-folder-tree__resize{position:absolute;bottom:0;left:0;right:0;height:9px;cursor:row-resize;touch-action:none}.chat-folder-tree__resize:after{content:'';display:block;width:36px;height:3px;border-radius:3px;background:#cbd5e1;margin:3px auto}.chat-folder-tree__resize:hover:after,.chat-folder-tree__resize:focus:after{background:var(--el-color-primary)}.chat-folder-tree__grip{cursor:grab;opacity:0;color:#94a3b8}.chat-folder-tree__row:hover .chat-folder-tree__grip{opacity:1}
.chat-folder-tree button{font:inherit;color:inherit;cursor:pointer}.chat-folder-tree__all,.chat-folder-tree__toggle,.chat-folder-tree__name{border:0;background:transparent}.chat-folder-tree__all{padding:6px 8px}.chat-folder-tree__all[aria-pressed="true"]{color:var(--color-primary-hover);font-weight:600}.chat-folder-tree__toggle{display:flex;align-items:center;justify-content:center;flex:none;width:20px;padding:5px 0}.chat-folder-tree__name{display:flex;align-items:center;gap:6px;flex:1;min-width:0;padding:6px 2px;text-align:left}.chat-folder-tree__name span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chat-folder-tree__row>.el-button{flex:none;margin:0;padding:4px}.chat-folder-tree__children{padding-left:28px}.chat-folder-tree__hint{display:block;margin:4px 0;color:#94a3b8;font-size:11px}.chat-folder-tree__mention{color:#dc2626}.chat-folder-tree button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}
.chat-folder-tree__name>span{flex:1}.chat-folder-tree__count{flex:none;min-width:20px;box-sizing:border-box;padding:1px 6px;border-radius:7px;background:#e9eef5;color:#64748b;text-align:center;font-size:10px;font-variant-numeric:tabular-nums}.chat-folder-tree__row.is-active .chat-folder-tree__count{background:#dbe6f7;color:#4267a5}.chat-folder-tree__children{margin-left:10px;padding-left:19px;border-left:1px solid #dde4ed}.chat-folder-tree__row:not(.is-active):hover{background:#edf1f7}
.chat-folder-tree__mention{flex:none;min-width:18px;padding:1px 5px;border-radius:10px;background:#dc2626;color:white;text-align:center;font-size:11px;line-height:16px}
</style>
