<template>
  <section v-if="compact" class="chat-folder-chips" aria-label="会话分组">
    <div class="chat-folder-chips__row">
      <button type="button" class="chat-folder-chips__chip" :class="{ 'is-active': !selected }" :aria-pressed="!selected" @click="$emit('select', '')">全部</button>
      <button v-for="root in roots" :key="root.id" type="button" class="chat-folder-chips__chip" :class="{ 'is-active': activeRootId === root.id }" :aria-pressed="activeRootId === root.id" @click="openChild(root)">
        <span>{{ root.name }}</span><small>{{ count(root.id) }}</small><b v-if="mentionCount(root.id)" :aria-label="`${mentionCount(root.id)} 条未读提及`">{{ mentionCount(root.id) > 99 ? '99+' : mentionCount(root.id) }}</b>
      </button>
    </div>
    <div v-if="subFolders.length" class="chat-folder-chips__row chat-folder-chips__row--sub">
      <button v-for="(child, childIndex) in subFolders" :key="child.id" type="button" class="chat-folder-chips__chip" :class="{ 'is-active': selected === child.id, 'is-stripe': childIndex % 2 === 1 }" :data-folder-id="child.id" :title="child.name" :aria-pressed="selected === child.id" @click="openChild(child)">
        <span>{{ child.name }}</span><small>{{ count(child.id) }}</small><b v-if="mentionCount(child.id)" :aria-label="`${mentionCount(child.id)} 条未读提及`">{{ mentionCount(child.id) > 99 ? '99+' : mentionCount(child.id) }}</b>
      </button>
    </div>
  </section>
  <section v-else ref="panel" class="chat-folder-tree" aria-label="会话分组" :style="{ height: `${panelHeight}px` }">
    <div class="chat-folder-tree__heading">
      <strong>会话分组</strong>
      <span v-if="categories.canManage" class="chat-folder-tree__heading-actions">
        <button type="button" class="chat-folder-tree__head-btn" :disabled="!!editing" title="新建一级会话" aria-label="新建一级会话" @click="start(null, null, true)"><el-icon><ChatDotRound /></el-icon></button>
        <button type="button" class="chat-folder-tree__head-btn" :disabled="!!editing" title="新建分组" aria-label="新建分组" @click="start()"><el-icon><FolderAdd /></el-icon></button>
      </span>
    </div>
    <p v-if="categories.canManage && !categories.hierarchyReady" class="chat-folder-tree__hint">分类管理暂未就绪，请联系系统管理员</p>
    <div class="chat-folder-tree__scroll">
      <button type="button" class="chat-folder-tree__all" :aria-pressed="!selected" @click="$emit('select', '')">全部分组</button>
      <div v-for="root in roots" :key="root.id" class="chat-folder-tree__branch" :style="{'--folder-tint': folderTint(root)}">
        <div class="chat-folder-tree__row" :class="{ 'is-active': selected === root.id }" @dragstart.stop="beginDrag($event, root.id)" @dragover.prevent @drop.stop.prevent="drop(root.id)" @dragend="dragged = ''" @contextmenu="openProjects($event, root)" @keydown.shift.f10="openProjects($event, root)">
          <button v-if="!root.isConversation && root.id !== resourceFolderId" type="button" class="chat-folder-tree__toggle" :aria-label="`${expanded.has(root.id) ? '收起' : '展开'}${root.name}`" :aria-expanded="expanded.has(root.id)" @click="toggle(root.id)"><el-icon><ArrowDown v-if="expanded.has(root.id)" /><ArrowRight v-else /></el-icon></button>
          <span v-else class="chat-folder-tree__toggle" aria-hidden="true"><el-icon v-if="root.isConversation"><ChatDotRound /></el-icon><template v-else>#</template></span>
          <span class="chat-folder-tree__grip" :draggable="!editing && !root.fixedTop" @dragstart.stop="beginDrag($event, root.id)" title="拖动调整分组顺序" aria-hidden="true">⠿</span>
          <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === root.id" :data-folder-id="root.id" :aria-haspopup="root.id === annotationFolderId ? 'dialog' : undefined" :title="root.id === annotationFolderId ? '右键搜索标注项目，加入会话' : undefined" @click="openChild(root)"><span class="chat-folder-tree__label">{{ root.name }}</span><span class="chat-folder-tree__badges"><b v-if="mentionCount(root.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(root.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',root.id)" @keydown.enter.stop.prevent="emit('unread',root.id)" @keydown.space.stop.prevent="emit('unread',root.id)">{{ mentionCount(root.id) > 99 ? '99+' : mentionCount(root.id) }}</b><small v-if="!root.isConversation" class="chat-folder-tree__count" :aria-label="`${count(root.id)} 个对话`">{{ count(root.id) }}</small></span></button>
          <span v-if="categories.canManage && (!root.isConversation || !root.builtin)" class="chat-folder-tree__row-actions" @click.stop>
            <button v-if="!root.isConversation" type="button" class="chat-folder-tree__act-btn" :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下新建${root.id === resourceFolderId ? '讨论' : '会话'}`" :title="root.id === resourceFolderId ? '新建讨论' : '创建会话'" @click="start(root.id, null, true)"><el-icon><Plus /></el-icon></button>
            <button v-if="!root.isConversation && root.id !== resourceFolderId" type="button" class="chat-folder-tree__act-btn" :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下创建二级菜单`" title="创建二级菜单" @click="start(root.id, null, false, true)"><el-icon><FolderAdd /></el-icon></button>
            <button v-if="!root.builtin" type="button" class="chat-folder-tree__act-btn" :disabled="!!editing" :aria-label="`重命名${root.name}`" title="重命名" @click="start(root.parentKey, root)"><el-icon><Edit /></el-icon></button>
            <button v-if="!root.builtin && !root.deletionProtected" type="button" class="chat-folder-tree__act-btn is-danger" :disabled="!!editing || saving" :aria-label="`${root.isConversation ? '删除会话' : '移除'}${root.name}`" title="删除" @click="remove(root)"><el-icon><Close /></el-icon></button>
          </span>
        </div>
        <div v-if="root.id !== resourceFolderId && expanded.has(root.id) || editing?.parentKey === root.id" class="chat-folder-tree__children">
          <el-button v-if="root.id===annotationFolderId" link class="chat-technical-entry" @click="technicalPicker.open()">技术需求</el-button>
          <template v-for="(child, childIndex) in visibleChildren(root.id)" :key="child.id">
          <div class="chat-folder-tree__row" :class="{ 'is-active': selected === child.id, 'is-subgroup': child.id === annotationStatusGroupId, 'is-nested': child.parentKey !== root.id, 'is-stripe': childIndex % 2 === 1 }" @contextmenu="openCategoryMenu($event, child)" @keydown.shift.f10="openCategoryMenu($event, child)" @dragstart.stop="beginDrag($event, child.id)" @dragover.prevent @drop.stop.prevent="drop(child.id)" @dragend="dragged = ''">
            <button v-if="children(child.id).length" type="button" class="chat-folder-tree__toggle" :aria-expanded="expanded.has(child.id)" :aria-label="`${expanded.has(child.id) ? '收起' : '展开'}${child.name}`" @click="toggle(child.id)"><el-icon><ArrowDown v-if="expanded.has(child.id)" /><ArrowRight v-else /></el-icon></button><span v-if="!child.fixedTop && !child.builtin" class="chat-folder-tree__grip" :draggable="!editing && !child.fixedTop" @dragstart.stop="beginDrag($event, child.id)" title="拖动调整分类顺序" aria-hidden="true">⠿</span>
            <button type="button" class="chat-folder-tree__name" :data-folder-id="child.id" :title="child.name" :aria-pressed="selected === child.id" @click="openChild(child)"><el-icon v-if="child.isConversation"><ChatDotRound /></el-icon><span class="chat-folder-tree__label">{{ child.name }}</span><span class="chat-folder-tree__badges"><b v-if="mentionCount(child.id)" class="chat-folder-tree__mention" :aria-label="`${mentionCount(child.id)} 条未读提及`" role="button" tabindex="0" @click.stop.prevent="emit('unread',child.id)" @keydown.enter.stop.prevent="emit('unread',child.id)" @keydown.space.stop.prevent="emit('unread',child.id)">{{ mentionCount(child.id) > 99 ? '99+' : mentionCount(child.id) }}</b><small v-if="!child.isConversation" class="chat-folder-tree__count" :aria-label="`${count(child.id)} 个对话`">{{ count(child.id) }}</small></span></button>
            <span v-if="categories.canManage && !child.builtin" class="chat-folder-tree__row-actions" @click.stop>
              <button v-if="!child.isConversation && child.parentKey === root.id" type="button" class="chat-folder-tree__act-btn" :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${child.name}下新建会话`" title="新建会话" @click="start(child.id, null, true)"><el-icon><Plus /></el-icon></button>
              <button type="button" class="chat-folder-tree__act-btn" :disabled="!!editing" :aria-label="`重命名${child.name}`" title="重命名" @click="start(child.parentKey, child)"><el-icon><Edit /></el-icon></button>
              <button v-if="!child.deletionProtected && child.parentKey !== resourceFolderId" type="button" class="chat-folder-tree__act-btn is-danger" :disabled="!!editing || saving" :aria-label="`${child.isConversation ? '删除会话' : '删除分类'}${child.name}`" title="删除" @click="remove(child)"><el-icon><Close /></el-icon></button>
            </span>
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
      <div v-if="categoryMenuTarget" class="chat-folder-tree__context-menu"><el-button v-if="!categoryMenuTarget.isConversation" text @click="categoryCommand('create')">新建会话</el-button><el-button text @click="categoryCommand('rename')">重命名</el-button><el-button v-if="!categoryMenuTarget.deletionProtected" text type="danger" @click="categoryCommand('delete')">删除</el-button></div>
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
import { annotationFolderId, annotationStatusGroupId, resourceFolderId, sessionFolderCount, sessionFolderMentionUnread, sessionFolderNodes } from '@/utils/chatSessionFolders'
import { hasPermission } from '@/utils/permission'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import TechnicalRequirementsPicker from './TechnicalRequirementsPicker.vue'
const technicalPicker=ref()
const props = defineProps({ active: { type: Boolean, default: true }, selected: { type: String, default: '' }, sessions: { type: Array, default: () => [] }, compact: { type: Boolean, default: false } })
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
const nodes = computed(() => sessionFolderNodes(categories.items, { technicalAccess: categories.technicalAccess }))
const preferenceKey = `xinshi.chatFolderLayout.${localStorage.getItem('user_id') || 'anonymous'}`
let saved = {}
try { saved = JSON.parse(localStorage.getItem(preferenceKey) || '{}') || {} } catch { /* 使用默认布局。 */ }
const order = ref(Array.isArray(saved.order) ? saved.order.filter(id => typeof id === 'string') : [])
const panel = ref(), panelHeight = ref(Math.max(92, Math.min(Number(saved.height) || 200, window.innerHeight * .55))), dragged = ref('')
const roots = computed(() => nodes.value.filter(row => !row.parentKey).sort((a, b) => rank(a.id) - rank(b.id)))
const rank = id => order.value.includes(id) ? order.value.indexOf(id) : order.value.length
function persist() { try { localStorage.setItem(preferenceKey, JSON.stringify({ order: order.value, height: panelHeight.value, expanded: [...expanded.value] })) } catch { /* 本次调整仍然生效。 */ } }
function folderTint(row) { const colors = ['#64748b','#0d9488','#334155','#7c3aed','#d97706','#0284c7']; const index = ['resource','annotation','translation','interpretation','recruitment','technical'].indexOf(row.ruleKey); return colors[index < 0 ? [...row.id].reduce((n,c)=>n+c.charCodeAt(0),0)%colors.length : index] }
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
const children = id => nodes.value.filter(row => row.parentKey === id).sort((a, b) => Number(!!b.fixedTop) - Number(!!a.fixedTop) || rank(a.id) - rank(b.id))
const visibleChildren = id => children(id).flatMap(row => [row, ...(expanded.value.has(row.id) ? children(row.id) : [])])
const activeRootId = computed(() => {
  let row = nodes.value.find(item => item.id === props.selected)
  while (row?.parentKey) {
    const parent = nodes.value.find(item => item.id === row.parentKey)
    if (!parent) break
    row = parent
  }
  return row?.id || ''
})
const subFolders = computed(() => (activeRootId.value && activeRootId.value !== resourceFolderId ? visibleChildren(activeRootId.value) : []))
const count = id => sessionFolderCount(props.sessions, id, nodes.value)
const expanded = ref(new Set(Array.isArray(saved.expanded) ? saved.expanded : []))
const editing = ref(null), saving = ref(false), error = ref(''), editKey = ref(0)
function toggle(id) { const value = new Set(expanded.value); value.has(id) ? value.delete(id) : value.add(id); expanded.value = value; persist() }
async function reveal(id=props.selected){
  if (editing.value) return
  const row=nodes.value.find(row=>row.id===id);if(!row)return
  // 自动定位只滚动到分组，不展开二级目录；展开由用户点击箭头控制。
  await nextTick()
  const scroll=panel.value?.querySelector('.chat-folder-tree__scroll'),target=Array.from(panel.value?.querySelectorAll('.chat-folder-tree__row') || []).find(element => element.querySelector('.chat-folder-tree__name')?.getAttribute('data-folder-id') === row.id)
  if(scroll&&target){const a=target.getBoundingClientRect(),b=scroll.getBoundingClientRect();if(a.top<b.top||a.bottom>b.bottom)scroll.scrollTo({top:scroll.scrollTop+a.top-b.top,behavior:'auto'})}
}
// 分别观察标量，避免轮询替换分组数据时因数组引用变化反复拉回滚动位置。
// 普通点击和轮询不自动定位，避免打断手动滚动。
defineExpose({reveal})
const mentionCount = id => sessionFolderMentionUnread(props.sessions, id, nodes.value)
function start(parentKey = null, row = null, conversation = false, directory = false) {
  if (editing.value || !categories.canManage || !canStartChatNameEditing()) return
  if (parentKey && !categories.hierarchyReady) return
  editing.value = row ? { ...row } : { id: null, name: '', parentKey, conversation, directory }
  if (parentKey) expanded.value = new Set([...expanded.value, parentKey, nodes.value.find(item => item.id === parentKey)?.parentKey].filter(Boolean))
  error.value = ''; editKey.value++
  // 新建入口可能在长列表末尾，仅在打开时将整个编辑区（含操作按钮）带入视口。
  nextTick(() => {
    const scroll = panel.value?.querySelector('.chat-folder-tree__scroll')
    const editor = scroll?.querySelector('.chat-inline-name-editor')
    if (!scroll || !editor) return
    const bounds = scroll.getBoundingClientRect(), target = editor.getBoundingClientRect()
    if (target.bottom > bounds.bottom) scroll.scrollTop += target.bottom - bounds.bottom
    if (target.top < bounds.top) scroll.scrollTop += target.top - bounds.top
  })
}
function cancel() { if (!saving.value) { editing.value = null; error.value = '' } }
function openChild(row) {
  if (!row.isConversation) {
    if (row.id === annotationStatusGroupId && expanded.value.has(row.id) && props.selected === row.id) {
      toggle(row.id)
      return
    }
    expanded.value = new Set([...expanded.value, row.id])
    persist()
    emit('select', row.id)
  }
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
.chat-folder-chips{flex:none;padding:6px 0 4px;border-bottom:1px solid #e6eaf0;background:#fff}
.chat-folder-chips__row{display:flex;gap:8px;padding:2px 10px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.chat-folder-chips__row::-webkit-scrollbar{display:none}
.chat-folder-chips__row--sub{padding-top:6px}
.chat-folder-chips__chip{display:inline-flex;flex:none;align-items:center;gap:4px;height:30px;padding:0 12px;border:1px solid #dce3ed;border-radius:15px;background:#f7f8fa;color:#475569;font:inherit;font-size:13px;white-space:nowrap;cursor:pointer}
.chat-folder-chips__row--sub .chat-folder-chips__chip{height:26px;padding:0 10px;font-size:12px;background:#fff}
.chat-folder-chips__chip.is-active{border-color:var(--color-primary);background:var(--color-primary-soft);color:var(--color-primary-hover);font-weight:600}
.chat-folder-chips__chip small{min-width:16px;padding:0 5px;border-radius:8px;background:#e9eef5;color:#64748b;font-size:10px;line-height:16px;text-align:center}
.chat-folder-chips__chip b{min-width:16px;padding:0 5px;border-radius:8px;background:#dc2626;color:#fff;font-size:10px;line-height:16px;text-align:center}
.chat-folder-chips__chip:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:1px}
</style>
<style scoped>
.chat-folder-tree__context-menu{display:flex;flex-direction:column;align-items:stretch;gap:6px}
.chat-folder-tree__context-menu .el-button{margin:0;justify-content:flex-start}
.chat-folder-tree{display:flex;flex-direction:column;position:relative;box-sizing:border-box;flex:0 1 auto;min-height:100px;max-height:60%;padding:8px 10px 10px;border-bottom:1px solid #e6eaf0;color:#475569;font-size:12px}
.chat-folder-tree__heading{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px}.chat-folder-tree__heading strong{font-weight:500}.chat-folder-tree__heading .el-button{font-size:11px}.chat-folder-tree__heading-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.chat-folder-tree__heading-actions .el-button{margin:0}
.chat-folder-tree__scroll{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}.chat-folder-tree__row{display:flex;align-items:center;gap:3px;min-height:30px;border-radius:5px}.chat-folder-tree__row.is-active{background:var(--color-primary-soft);color:var(--color-primary-hover)}
.chat-folder-tree__resize{position:absolute;bottom:0;left:0;right:0;height:9px;cursor:row-resize;touch-action:none}.chat-folder-tree__resize:after{content:'';display:block;width:36px;height:3px;border-radius:3px;background:#cbd5e1;margin:3px auto}.chat-folder-tree__resize:hover:after,.chat-folder-tree__resize:focus:after{background:var(--el-color-primary)}.chat-folder-tree__grip{cursor:grab;opacity:0;color:#94a3b8}.chat-folder-tree__row:hover .chat-folder-tree__grip{opacity:1}
.chat-folder-tree button{font:inherit;color:inherit;cursor:pointer}.chat-folder-tree__all,.chat-folder-tree__toggle,.chat-folder-tree__name{border:0;background:transparent}.chat-folder-tree__all{padding:6px 8px}.chat-folder-tree__all[aria-pressed="true"]{color:var(--color-primary-hover);font-weight:600}.chat-folder-tree__toggle{display:flex;align-items:center;justify-content:center;flex:none;width:20px;padding:5px 0}.chat-folder-tree__name{display:flex;align-items:center;gap:6px;flex:1;min-width:0;padding:6px 2px;text-align:left}.chat-folder-tree__name span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chat-folder-tree__row>.el-button{flex:none;margin:0;padding:4px}.chat-folder-tree__children{padding-left:28px}.chat-folder-tree__hint{display:block;margin:4px 0;color:#94a3b8;font-size:11px}.chat-folder-tree__mention{color:#dc2626}.chat-folder-tree button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}
.chat-folder-tree__name>span{flex:1}.chat-folder-tree__count{flex:none;min-width:20px;box-sizing:border-box;padding:1px 6px;border-radius:7px;background:#e9eef5;color:#64748b;text-align:center;font-size:10px;font-variant-numeric:tabular-nums}.chat-folder-tree__row.is-active .chat-folder-tree__count{background:#dbe6f7;color:#4267a5}.chat-folder-tree__children{margin-left:10px;padding-left:19px;border-left:1px solid #dde4ed}
.chat-folder-tree__mention{flex:none;min-width:18px;padding:1px 5px;border-radius:10px;background:#dc2626;color:white;text-align:center;font-size:11px;line-height:16px}
</style>

<style scoped>
.chat-folder-tree{flex-shrink:0;max-height:60%;overflow:hidden}.chat-folder-tree__scroll{scrollbar-gutter:stable;overflow-anchor:none}.chat-folder-tree__branch{margin-bottom:5px}.chat-folder-tree__branch>.chat-folder-tree__row{background:var(--folder-tint);font-weight:600}.chat-folder-tree__row{min-height:34px;border-left:3px solid transparent}.chat-folder-tree__row.is-active{border-left-color:var(--el-color-primary);font-weight:600}.chat-folder-tree__children{padding-left:16px;margin-left:10px}.chat-folder-tree__toggle{width:24px}.chat-folder-tree__grip{flex:none}
</style>

<style scoped>
/* 深蓝灰商务中性分组树：左侧 3px 语义色条区分模块，所有一级/子级计数泡泡统一右对齐，行尾操作悬停浮层显示不占宽度。 */
.chat-folder-tree{padding:8px 10px 10px;min-height:92px;border-color:var(--chat-sidebar-border,#e2e8f0)}
.chat-folder-tree__heading{min-height:24px;margin-bottom:6px;color:#64748b}
.chat-folder-tree__heading strong{font-size:11.5px;font-weight:600;letter-spacing:.04em}
.chat-folder-tree__heading-actions{display:flex;align-items:center;gap:2px}
.chat-folder-tree__head-btn{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:1px solid transparent;border-radius:6px;background:transparent;color:#64748b;cursor:pointer;transition:background-color .14s ease,border-color .14s ease,color .14s ease}
.chat-folder-tree__head-btn:hover:not(:disabled){background:#e7eef6;border-color:#d5e0ee;color:#1e293b}
.chat-folder-tree__head-btn:disabled{opacity:.45;cursor:not-allowed}
.chat-folder-tree__head-btn .el-icon{font-size:14px}
.chat-folder-tree__all{display:block;width:100%;margin-bottom:4px;padding:5px 8px;border-radius:6px;text-align:left;color:#64748b;transition:background-color .14s ease,color .14s ease}
.chat-folder-tree__all:hover{background:#eef2f7;color:#1e293b}
.chat-folder-tree__all[aria-pressed="true"]{background:#e7eef6;color:#1e293b;font-weight:600}
.chat-folder-tree__branch{margin-bottom:3px}
.chat-folder-tree__row{position:relative;overflow:hidden;min-height:31px;border-radius:6px;border-left:3px solid transparent;background:transparent;box-shadow:none;transition:background-color .14s ease,border-color .14s ease;color:#475569}
.chat-folder-tree__branch>.chat-folder-tree__row{background:#fff;border:1px solid #e9eef5;border-left:3px solid var(--folder-tint,#64748b);font-weight:500}
.chat-folder-tree__children{margin:3px 0 2px 12px;padding-left:10px;border-left:1px solid #dce4ee}
.chat-folder-tree__children .chat-folder-tree__row{min-height:28px;margin-bottom:2px;background:transparent;border:1px solid transparent;border-left:2px solid transparent;font-weight:400}
.chat-folder-tree__children .chat-folder-tree__row.is-subgroup{font-weight:500;color:#334155}
.chat-folder-tree__children .chat-folder-tree__row.is-nested{margin-left:14px;padding-left:4px}
.chat-folder-tree__children .chat-folder-tree__row.is-stripe{background:transparent}
.chat-folder-tree__row:not(.is-active):hover,.chat-folder-tree__row:not(.is-active):has(:focus-visible){background:#eef3f8;border-color:#d8e2ee}
.chat-folder-tree__branch>.chat-folder-tree__row:not(.is-active):hover,.chat-folder-tree__branch>.chat-folder-tree__row:not(.is-active):has(:focus-visible){border-left-color:var(--folder-tint,#64748b)}
.chat-folder-tree__branch .chat-folder-tree__row.is-active{background:#e7eef6;border-color:#c6d4e5;border-left-color:var(--folder-tint,#334155);color:#1e293b;font-weight:600}
.chat-folder-tree__grip{width:10px;font-size:11px;margin-left:-2px;text-align:center}
.chat-folder-tree__name{padding:5px 8px 5px 2px;gap:6px}
.chat-folder-tree__name>.chat-folder-tree__label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-folder-tree__name>.chat-folder-tree__badges{display:inline-flex;align-items:center;justify-content:flex-end;gap:4px;flex:none;margin-left:auto;overflow:visible}
.chat-folder-tree__count,.chat-folder-tree__row.is-active .chat-folder-tree__count{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:18px;padding:0 6px;border-radius:9px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;font-size:10.5px;line-height:1;font-variant-numeric:tabular-nums}
.chat-folder-tree__row.is-active .chat-folder-tree__count{background:#fff;color:#1e293b;border-color:#cbd5e1}
.chat-folder-tree__mention{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:#dc2626;color:#fff;font-size:10.5px;line-height:1}
.chat-folder-tree__row-actions{position:absolute;top:0;bottom:0;right:0;display:inline-flex;align-items:center;gap:2px;padding:0 5px 0 18px;background:linear-gradient(90deg,transparent 0%,#eef3f8 16px,#eef3f8 100%);opacity:0;pointer-events:none;transition:opacity .12s ease}
.chat-folder-tree__row-actions:empty{display:none}
.chat-folder-tree__row.is-active .chat-folder-tree__row-actions{background:linear-gradient(90deg,transparent 0%,#e7eef6 16px,#e7eef6 100%)}
.chat-folder-tree__row:hover .chat-folder-tree__row-actions,.chat-folder-tree__row:has(:focus-visible) .chat-folder-tree__row-actions{opacity:1;pointer-events:auto}
.chat-folder-tree__act-btn{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;margin:0;padding:0;border:0;border-radius:4px;background:transparent;color:#64748b;font-size:13px;line-height:1;cursor:pointer;transition:background-color .12s ease,color .12s ease}
.chat-folder-tree__act-btn:hover:not(:disabled){background:#dbe5f1;color:#1e293b}
.chat-folder-tree__act-btn.is-danger:hover:not(:disabled){background:#fee2e2;color:#dc2626}
.chat-folder-tree__act-btn:disabled{opacity:.4;cursor:not-allowed}
.chat-folder-tree__scroll{scrollbar-width:thin;scrollbar-color:#cbd5e1 transparent}
@media (hover: none){.chat-folder-tree__row-actions{position:static;padding:0 4px 0 0;background:none!important;opacity:1;pointer-events:auto}}
</style>
