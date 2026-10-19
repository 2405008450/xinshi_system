<template>
  <div v-if="categories.ready" class="chat-category-menu">
    <div class="chat-category-heading"><strong>团队分类</strong><el-button v-if="categories.canManage" link :disabled="!!editing" @click="start()">新增分类</el-button></div>
    <div v-for="row in categories.items.filter(item => item.active || categories.canManage)" :key="row.id" class="chat-category-row">
      <ChatInlineNameEditor v-if="editing?.id === row.id" :key="editKey" :initial-name="editing.name" label="分类名称" :saving="saving" :error="error" @save="save" @cancel="cancel" />
      <template v-else>
        <el-button link :disabled="!row.active || !!editing" :type="selected === categoryKey(row.id) ? 'primary' : ''" class="chat-category-name" @click="$emit('select', categoryKey(row.id))">{{ row.name }} ({{ count(row.id) }}){{ row.active ? '' : ' · 已停用' }}</el-button>
        <el-button v-if="categories.canManage" link :disabled="!!editing" :aria-label="`重命名${row.name}`" title="改名" @click="start(row)"><el-icon><Edit /></el-icon></el-button>
        <el-button v-if="categories.canManage" link :disabled="saving || !!editing" :aria-label="`${row.active ? '停用' : '启用'}${row.name}`" :title="row.active ? '停用分类，保留会话关联' : '启用分类'" @click="toggle(row)"><el-icon><component :is="row.active ? Remove : CirclePlus" /></el-icon></el-button>
      </template>
    </div>
    <ChatInlineNameEditor v-if="editing && !editing.id" :key="editKey" label="分类名称" :saving="saving" :error="error" @save="save" @cancel="cancel" />
    <small v-if="!categories.items.some(row => row.active) && !editing">暂无团队分类</small>
    <p v-if="actionError" role="alert" class="chat-category-error">{{ actionError }}</p>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { CirclePlus, Edit, Remove } from '@element-plus/icons-vue'
import { categoryKey, useChatSessionCategories } from '@/composables/useChatSessionCategories'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
const props = defineProps({ sessions: { type: Array, default: () => [] }, selected: { type: String, default: 'all' } })
const emit = defineEmits(['select', 'changed', 'editing'])
const { categories, create, update, refresh } = useChatSessionCategories()
const editing = ref(null), saving = ref(false), error = ref(''), actionError = ref(''), editKey = ref(0)
const count = id => props.sessions.filter(row => row.categoryIds?.includes(id)).length
function cancel() { if (!saving.value) { editing.value = null; error.value = '' } }
function start(row) { if (!editing.value && canStartChatNameEditing()) { editing.value = row ? { ...row } : { id: null, name: '' }; error.value = ''; editKey.value++; emit('editing') } }
async function save(name) {
  if (saving.value || !editing.value) return
  saving.value = true; error.value = ''; const target = editing.value
  try { if (target.id) await update(target, { name }); else await create(name); editing.value = null; emit('changed') }
  catch (e) { error.value = e.message; emit('editing'); await refresh().catch(() => {}); const current = categories.items.find(row => row.id === target.id); if (current && editing.value) editing.value.revision = current.revision }
  finally { saving.value = false }
}
async function toggle(row) {
  if (saving.value) return
  saving.value = true; actionError.value = ''
  try { await update(row, { active: !row.active }); emit('changed') }
  catch (e) { actionError.value = e.message; await refresh().catch(() => {}) }
  finally { saving.value = false }
}
</script>
<style scoped>
.chat-category-menu{border-top:1px solid #e2e8f0;margin-top:6px;padding-top:8px}.chat-category-heading{display:flex;align-items:center;justify-content:space-between;padding:4px 0 8px;font-size:12px;color:#64748b}.chat-category-row{display:flex;align-items:center;gap:4px;min-width:0}.chat-category-row>.el-button{margin:0;padding:8px 2px;flex:none}.chat-category-row>.chat-category-name{flex:1;min-width:0;justify-content:flex-start;white-space:normal;overflow-wrap:anywhere;text-align:left}.chat-category-error{color:var(--el-color-danger);font-size:12px;overflow-wrap:anywhere}.chat-category-menu small{font-size:12px;color:#64748b}.chat-category-heading .el-button{padding:0}
</style>
