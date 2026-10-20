<template>
  <section ref="panel" class="chat-folder-tree" aria-label="会话分组" :style="{ height: `${panelHeight}px` }">
    <div class="chat-folder-tree__heading"><strong>会话分组</strong><el-button v-if="categories.canManage" link :disabled="!!editing" @click="start()"><el-icon><Plus /></el-icon>新建分组</el-button></div>
    <p v-if="categories.canManage && !categories.hierarchyReady" class="chat-folder-tree__hint">分类管理暂未就绪，请联系系统管理员</p>
    <div class="chat-folder-tree__scroll">
      <button type="button" class="chat-folder-tree__all" :aria-pressed="!selected" @click="$emit('select', '')">全部分组</button>
      <div v-for="root in roots" :key="root.id">
        <div class="chat-folder-tree__row" :class="{ 'is-active': selected === root.id }" :draggable="!editing" @dragstart.stop="beginDrag($event, root.id)" @dragover.prevent @drop.stop.prevent="drop(root.id)" @dragend="dragged = ''" @contextmenu="openProjects($event, root)" @keydown.shift.f10="openProjects($event, root)">
          <button v-if="root.id !== resourceFolderId" type="button" class="chat-folder-tree__toggle" :aria-label="`${expanded.has(root.id) ? '收起' : '展开'}${root.name}`" :aria-expanded="expanded.has(root.id)" @click="toggle(root.id)"><el-icon><ArrowDown v-if="expanded.has(root.id)" /><ArrowRight v-else /></el-icon></button>
          <span v-else class="chat-folder-tree__toggle" aria-hidden="true">#</span>
          <span class="chat-folder-tree__grip" title="拖动调整分组顺序" aria-hidden="true">⠿</span>
          <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === root.id" :aria-haspopup="root.id === annotationFolderId ? 'dialog' : undefined" :title="root.id === annotationFolderId ? '右键打开标注项目管理，加入会话' : undefined" @click="$emit('select', root.id)"><span>{{ root.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(root.id)} 个对话`">{{ count(root.id) }}</small></button>
          <el-button v-if="categories.canManage" link :disabled="!!editing || !categories.hierarchyReady" :aria-label="`在${root.name}下新建${root.id === resourceFolderId ? '讨论' : '分类'}`" :title="root.id === resourceFolderId ? '新建讨论' : '新建分类'" @click="start(root.id)"><el-icon><Plus /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin" link :disabled="!!editing" :aria-label="`重命名${root.name}`" @click="start(root.parentKey, root)"><el-icon><Edit /></el-icon></el-button>
          <el-button v-if="categories.canManage && !root.builtin" link :disabled="!!editing || saving" :aria-label="`移除${root.name}`" @click="remove(root)"><el-icon><Close /></el-icon></el-button>
        </div>
        <div v-if="root.id !== resourceFolderId && expanded.has(root.id) || editing?.parentKey === root.id" class="chat-folder-tree__children">
          <div v-for="child in children(root.id)" :key="child.id" class="chat-folder-tree__row" :class="{ 'is-active': selected === child.id }" :draggable="!editing" @dragstart.stop="beginDrag($event, child.id)" @dragover.prevent @drop.stop.prevent="drop(child.id)" @dragend="dragged = ''">
            <span class="chat-folder-tree__grip" title="拖动调整分类顺序" aria-hidden="true">⠿</span>
            <button type="button" class="chat-folder-tree__name" :aria-pressed="selected === child.id" @click="$emit('select', child.id)"><span>{{ child.name }}</span><small class="chat-folder-tree__count" :aria-label="`${count(child.id)} 个对话`">{{ count(child.id) }}</small><b v-if="hasMention(child.id)" class="chat-folder-tree__mention">@</b></button>
            <el-button v-if="categories.canManage && !child.builtin" link :disabled="!!editing" :aria-label="`重命名${child.name}`" @click="start(child.parentKey, child)"><el-icon><Edit /></el-icon></el-button>
          </div>
          <ChatInlineNameEditor v-if="editing?.parentKey === root.id" :key="editKey" :initial-name="editing.name" :label="root.id === resourceFolderId ? '讨论名称' : '分类名称'" :saving="saving" :error="error" @save="save" @cancel="cancel" />
          <small v-if="!children(root.id).length && editing?.parentKey !== root.id" class="chat-folder-tree__hint">暂无二级目录</small>
        </div>
        <ChatInlineNameEditor v-if="editing?.id === root.id && !editing.parentKey" :key="editKey" :initial-name="editing.name" label="一级目录名称" :saving="saving" :error="error" @save="save" @cancel="cancel" />
      </div>
      <ChatInlineNameEditor v-if="editing && !editing.id && !editing.parentKey" :key="editKey" label="一级目录名称" :saving="saving" :error="error" @save="save" @cancel="cancel" />
    </div>
    <div class="chat-folder-tree__resize" role="separator" aria-label="调整分组区域高度" aria-orientation="horizontal" tabindex="0" :aria-valuenow="panelHeight" :aria-valuemin="100" :aria-valuemax="maxHeight()" @pointerdown="beginResize" @keydown.up.prevent="resizeBy(-20)" @keydown.down.prevent="resizeBy(20)" />
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { ArrowDown, ArrowRight, Close, Edit, Plus } from '@element-plus/icons-vue'
import { useChatSessionCategories } from '@/composables/useChatSessionCategories'
import { annotationFolderId, resourceFolderId, sessionFolderCount, sessionFolderNodes, sessionMatchesFolder } from '@/utils/chatSessionFolders'
import { hasPermission } from '@/utils/permission'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
const props = defineProps({ selected: { type: String, default: '' }, sessions: { type: Array, default: () => [] } })
const emit = defineEmits(['select', 'changed', 'browse-annotation'])
function openProjects(event, row) {
  if (row.id !== annotationFolderId || !hasPermission('projects:read')) return
  event.preventDefault(); emit('browse-annotation')
}
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
const count = id => sessionFolderCount(props.sessions, id, nodes.value)
const expanded = ref(new Set())
const editing = ref(null), saving = ref(false), error = ref(''), editKey = ref(0)
function toggle(id) { const value = new Set(expanded.value); value.has(id) ? value.delete(id) : value.add(id); expanded.value = value }
watch(() => props.selected, id => { const row = nodes.value.find(row => row.id === id); if (row) expanded.value = new Set([...expanded.value, row.parentKey || row.id]) }, { immediate: true })
const hasMention = id => props.sessions.some(row => Number(row.mentionUnread) > 0 && sessionMatchesFolder(row, id, nodes.value))
function start(parentKey = null, row = null) {
  if (editing.value || !categories.canManage || !canStartChatNameEditing()) return
  if (parentKey && !categories.hierarchyReady) return
  editing.value = row ? { ...row } : { id: null, name: '', parentKey }
  if (parentKey) expanded.value = new Set([...expanded.value, parentKey])
  error.value = ''; editKey.value++
}
function cancel() { if (!saving.value) { editing.value = null; error.value = '' } }
async function remove(row) {
  try { await ElMessageBox.confirm(`移除“${row.name}”分组？其中的对话和消息会保留。`, '移除分组', { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' }) } catch { return }
  saving.value = true
  try { await update(row, { active: false }); if (props.selected === row.id || children(row.id).some(child => child.id === props.selected)) emit('select', ''); emit('changed') }
  catch (e) { ElMessage.error(e.message || '移除失败'); await refresh().catch(() => {}) }
  finally { saving.value = false }
}
async function save(name) {
  if (saving.value || !editing.value) return
  saving.value = true; error.value = ''
  try {
    const target = editing.value
    const row = target.id ? await update(target, { name }) : await create(name, target.parentKey)
    editing.value = null; emit('changed'); emit('select', target.parentKey === resourceFolderId ? resourceFolderId : row.id)
  } catch (e) {
    error.value = e.message; await refresh().catch(() => {})
    const current = categories.items.find(row => row.id === editing.value?.id)
    if (current && editing.value) editing.value.revision = current.revision
  } finally { saving.value = false }
}
</script>
<style scoped>
.chat-folder-tree{display:flex;flex-direction:column;position:relative;box-sizing:border-box;flex:0 1 auto;min-height:100px;max-height:60%;padding:8px 10px 10px;border-bottom:1px solid #e6eaf0;color:#475569;font-size:12px}
.chat-folder-tree__heading{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px}.chat-folder-tree__heading strong{font-weight:500}.chat-folder-tree__heading .el-button{font-size:11px}
.chat-folder-tree__scroll{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}.chat-folder-tree__row{display:flex;align-items:center;gap:3px;min-height:30px;border-radius:5px}.chat-folder-tree__row.is-active{background:var(--color-primary-soft);color:var(--color-primary-hover)}
.chat-folder-tree__resize{position:absolute;bottom:0;left:0;right:0;height:9px;cursor:row-resize;touch-action:none}.chat-folder-tree__resize:after{content:'';display:block;width:36px;height:3px;border-radius:3px;background:#cbd5e1;margin:3px auto}.chat-folder-tree__resize:hover:after,.chat-folder-tree__resize:focus:after{background:var(--el-color-primary)}.chat-folder-tree__grip{cursor:grab;opacity:0;color:#94a3b8}.chat-folder-tree__row:hover .chat-folder-tree__grip{opacity:1}
.chat-folder-tree button{font:inherit;color:inherit;cursor:pointer}.chat-folder-tree__all,.chat-folder-tree__toggle,.chat-folder-tree__name{border:0;background:transparent}.chat-folder-tree__all{padding:6px 8px}.chat-folder-tree__all[aria-pressed="true"]{color:var(--color-primary-hover);font-weight:600}.chat-folder-tree__toggle{display:flex;align-items:center;justify-content:center;flex:none;width:20px;padding:5px 0}.chat-folder-tree__name{display:flex;align-items:center;gap:6px;flex:1;min-width:0;padding:6px 2px;text-align:left}.chat-folder-tree__name span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chat-folder-tree__row>.el-button{flex:none;margin:0;padding:4px}.chat-folder-tree__children{padding-left:28px}.chat-folder-tree__hint{display:block;margin:4px 0;color:#94a3b8;font-size:11px}.chat-folder-tree__mention{color:#dc2626}.chat-folder-tree button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}
.chat-folder-tree__name>span{flex:1}.chat-folder-tree__count{flex:none;min-width:20px;box-sizing:border-box;padding:1px 6px;border-radius:7px;background:#e9eef5;color:#64748b;text-align:center;font-size:10px;font-variant-numeric:tabular-nums}.chat-folder-tree__row.is-active .chat-folder-tree__count{background:#dbe6f7;color:#4267a5}.chat-folder-tree__children{margin-left:10px;padding-left:19px;border-left:1px solid #dde4ed}.chat-folder-tree__row:not(.is-active):hover{background:#edf1f7}
</style>
