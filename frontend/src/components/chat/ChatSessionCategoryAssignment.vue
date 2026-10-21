<template>
  <DraggableFormDialog v-model="visible" :z-index="100002" title="设置会话分类" width="min(480px, calc(100vw - 32px))" top="8vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="close">
    <p class="assignment-hint">团队共享归类；仅展示各人有权访问的会话。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm ref="formRef" :model="form" @submit.prevent="save">
      <el-form-item label="团队分类" prop="ids">
        <el-checkbox-group v-model="form.ids" :disabled="saving" class="assignment-options">
          <el-checkbox v-for="row in folderOptions" :key="row.id" :value="row.id">{{ row.label }}</el-checkbox>
        </el-checkbox-group>
        <span v-if="!folderOptions.length">暂无可用目录，请联系超级管理员或 Jimmy 新增。</span>
      </el-form-item>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!loaded" @click="save">确定</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { chatRequest } from '@/api/projectChat'
import { useChatSessionCategories } from '@/composables/useChatSessionCategories'
import { assignableSessionFolders } from '@/utils/chatSessionFolders'
import '@/views/resource/components/issueDialogs.css'
const emit = defineEmits(['changed'])
const { categories, refresh } = useChatSessionCategories()
const folderOptions = computed(() => assignableSessionFolders(categories.items).filter(row => !row.builtin || categories.hierarchyReady))
const visible = ref(false), saving = ref(false), loaded = ref(false), error = ref(''), formRef = ref(), form = reactive({ ids: [] })
let session, original = new Set()
async function open(row) {
  if (saving.value) return
  session = row; original = new Set(row.categoryIds || []); form.ids = [...original]; error.value = ''; visible.value = true; saving.value = true; loaded.value = false
  try { const data = await chatRequest(`sessions/${row.projectType}/${row.projectId}/categories`); original = new Set(data.categoryIds); form.ids = [...original]; loaded.value = true }
  catch (e) { error.value = e.message }
  finally { saving.value = false }
}
function close(done) { if (!saving.value) done() }
async function save() {
  if (saving.value || !loaded.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  const desired = new Set(form.ids)
  const operations = folderOptions.value.filter(row => original.has(row.id) !== desired.has(row.id))
  const failures = []
  for (const row of operations) {
    const adding = desired.has(row.id)
    try {
      await chatRequest(`sessions/${session.projectType}/${session.projectId}/categories/${row.id}`, { method: adding ? 'put' : 'delete' })
      if (adding) original.add(row.id); else original.delete(row.id)
    } catch (e) { failures.push(`${row.name}：${e.message}`) }
  }
  emit('changed', { key: session.key, categoryIds: [...original] })
  if (failures.length) { error.value = failures.join('；'); await refresh().catch(() => {}) }
  else visible.value = false
  saving.value = false
}
defineExpose({ open })
</script>
<style scoped>
.assignment-options{display:flex;flex-direction:column;width:100%;gap:6px}.assignment-options :deep(.el-checkbox){margin:0;height:auto;min-height:30px;white-space:normal}.assignment-options :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}.assignment-hint{font-size:12px;color:#64748b}
</style>
