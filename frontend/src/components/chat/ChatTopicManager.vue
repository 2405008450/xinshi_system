<template>
  <DraggableFormDialog :z-index="100002" v-model="visible" title="讨论主题管理" width="min(760px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="closeManager">
    <p class="topic-manager-hint">点击主题名称即可改名；Enter 保存，Esc 取消。</p>
    <div class="topic-manager-tree">
      <div v-for="root in roots" :key="root.id" class="topic-manager-root">
        <div class="topic-manager-row">
          <el-button v-if="root.kind === 'topic'" link :aria-label="`${expanded.includes(root.id) ? '收起' : '展开'}${root.name}`" @click="toggle(root.id)">{{ expanded.includes(root.id) ? '▾' : '▸' }}</el-button>
          <ChatInlineNameEditor v-if="editing?.id === root.id" :key="editKey" :initial-name="editing.name" label="主题名称" :saving="saving" :error="error" @save="saveName" @cancel="cancel" />
          <el-button v-else link class="topic-manager-name" :disabled="root.kind === 'annotation'" @click="rename(root)">{{ root.name }}{{ root.active ? '' : '（已停用）' }}</el-button>
          <el-button v-if="root.kind === 'topic' && root.active" link type="primary" :disabled="!!editing" @click="add(root.id)">新增二级</el-button>
          <el-button link :disabled="!!editing" :aria-label="`${root.name}设置`" @click="openSettings(root)">设置</el-button>
        </div>
        <div v-if="expanded.includes(root.id)" class="topic-manager-children">
          <div v-for="child in children(root.id)" :key="child.id" class="topic-manager-row">
            <ChatInlineNameEditor v-if="editing?.id === child.id" :key="editKey" :initial-name="editing.name" label="主题名称" :saving="saving" :error="error" @save="saveName" @cancel="cancel" />
            <el-button v-else link class="topic-manager-name" @click="rename(child)">{{ child.name }}{{ child.active ? '' : '（已停用）' }}</el-button>
            <el-button link :disabled="!!editing" :aria-label="`${child.name}设置`" @click="openSettings(child)">设置</el-button>
          </div>
          <ChatInlineNameEditor v-if="editing && !editing.id && editing.parent_id === root.id" :key="editKey" label="主题名称" :saving="saving" :error="error" @save="saveName" @cancel="cancel" />
        </div>
      </div>
      <ChatInlineNameEditor v-if="editing && !editing.id && !editing.parent_id" :key="editKey" label="主题名称" :saving="saving" :error="error" @save="saveName" @cancel="cancel" />
    </div>
    <el-button :disabled="!!editing" @click="add()">新增一级菜单</el-button>
    <template #footer><el-button :disabled="saving" @click="closeManager(() => visible = false)">关闭</el-button></template>
    <DraggableFormDialog v-model="settingsVisible" :z-index="100004" :title="`${settings.name || '主题'}设置`" width="min(560px, calc(100vw - 32px))" top="8vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false">
      <el-alert v-if="settingsError" :title="settingsError" type="error" :closable="false" />
      <AppForm ref="settingsForm" :model="settings" label-position="top">
        <el-form-item label="说明" prop="description"><el-input v-model="settings.description" type="textarea" maxlength="500" :rows="3" /></el-form-item>
        <el-form-item label="排序" prop="sort_order"><el-input-number v-model="settings.sort_order" :min="0" :max="100000" :precision="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="settings.active" :disabled="settings.kind === 'annotation'" /><span class="topic-manager-hint">停用后保留历史消息分类。</span></el-form-item>
      </AppForm>
      <template #footer><el-button :disabled="settingsSaving" @click="settingsVisible = false">取消</el-button><el-button type="primary" :loading="settingsSaving" @click="saveSettings">保存设置</el-button></template>
    </DraggableFormDialog>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { useChatTopics } from '@/composables/useChatTopics'
import { topicApi } from '@/api/chatTopics'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import '@/views/resource/components/issueDialogs.css'
const { topics, refresh } = useChatTopics()
const visible = ref(false), saving = ref(false), error = ref(''), editing = ref(null), editKey = ref(0), expanded = ref([])
const settingsVisible = ref(false), settingsSaving = ref(false), settingsError = ref(''), settings = reactive({}), settingsForm = ref()
const roots = computed(() => topics.items.filter(row => !row.parent_id))
const children = id => topics.items.filter(row => row.parent_id === id)
function accept(row) { const index = topics.items.findIndex(item => item.id === row.id); if (index < 0) topics.items.push(row); else topics.items[index] = row; topics.items.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, 'zh-CN')) }
function toggle(id) { expanded.value = expanded.value.includes(id) ? expanded.value.filter(value => value !== id) : [...expanded.value, id] }
function cancel() { if (!saving.value) { editing.value = null; error.value = '' } }
function add(parentId = null) {
  if (editing.value || !canStartChatNameEditing()) return
  if (parentId && !expanded.value.includes(parentId)) expanded.value.push(parentId)
  editing.value = { id: null, parent_id: parentId, name: '' }; error.value = ''; editKey.value++
}
function rename(row) { if (!editing.value && row.kind !== 'annotation' && canStartChatNameEditing()) { editing.value = { ...row }; error.value = ''; editKey.value++ } }
function closeManager(done) { if (!saving.value && !settingsSaving.value) { cancel(); done() } }
async function open() { if (!canStartChatNameEditing()) return; await refresh(true); cancel(); expanded.value = roots.value.map(row => row.id); visible.value = true }
async function saveName(name) {
  if (saving.value || !editing.value) return
  const row = editing.value
  if (topics.items.some(item => item.id !== row.id && item.parent_id === row.parent_id && item.name.toLocaleLowerCase() === name.toLocaleLowerCase())) { error.value = '同一层级已有同名讨论主题'; return }
  saving.value = true; error.value = ''
  try {
    const result = row.id ? await topicApi.update(row.id, { name, description: row.description, sort_order: row.sort_order, active: row.active, revision: row.revision })
      : await topicApi.create({ name, parent_id: row.parent_id, sort_order: Math.min(100000, Math.max(0, ...topics.items.filter(item => item.parent_id === row.parent_id).map(item => item.sort_order)) + 10) })
    accept(result)
    editing.value = null
    await refresh(true).catch(() => {})
  } catch (e) { error.value = e.message; await refresh(true).catch(() => {}); const current = topics.items.find(item => item.id === row.id); if (current && editing.value) Object.assign(editing.value, { ...current, name }) }
  finally { saving.value = false }
}
function openSettings(row) { Object.assign(settings, row); settingsError.value = ''; settingsVisible.value = true }
async function saveSettings() {
  if (settingsSaving.value || !await settingsForm.value.validate().catch(() => false)) return
  settingsSaving.value = true; settingsError.value = ''
  try { accept(await topicApi.update(settings.id, { name: settings.name, description: settings.description, sort_order: settings.sort_order, active: settings.active, revision: settings.revision })); settingsVisible.value = false; await refresh(true).catch(() => {}) }
  catch (e) { settingsError.value = e.message; await refresh(true).catch(() => {}); const row = topics.items.find(item => item.id === settings.id); if (row && (e.status === 409 || e.response?.status === 409)) Object.assign(settings, row) }
  finally { settingsSaving.value = false }
}
defineExpose({ open })
</script>
<style scoped>
.topic-manager-hint{font-size:12px;color:#64748b}.topic-manager-tree{margin:16px 0}.topic-manager-row{display:flex;align-items:center;gap:10px;min-height:42px;flex-wrap:wrap}.topic-manager-row>.el-button{margin-left:0}.topic-manager-name{flex:1;justify-content:flex-start;min-width:80px;white-space:normal;text-align:left}.topic-manager-children{padding-left:28px}.topic-manager-root{border-bottom:1px solid #edf1f5;padding:4px 0}.topic-manager-row>.chat-inline-name-editor{flex-basis:100%}
</style>
