<template>
  <DraggableFormDialog :z-index="100002" v-model="visible" title="讨论主题管理" width="min(860px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body destroy-on-close :close-on-click-modal="false">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div class="topic-manager-grid">
      <div><el-button @click="start()">新增一级菜单</el-button><div v-for="root in roots" :key="root.id" class="topic-manager-root">
        <el-button link @click="start(root)">{{ root.name }}{{ root.active ? '' : '（已停用）' }}</el-button>
        <el-button v-if="root.kind === 'topic'" link type="primary" @click="start(null, root.id)">新增二级</el-button>
        <div v-for="child in topics.items.filter(row => row.parent_id === root.id)" :key="child.id" class="topic-manager-child"><el-button link @click="start(child)">{{ child.name }}{{ child.active ? '' : '（已停用）' }}</el-button></div>
      </div></div>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="菜单名称" prop="name"><ReadonlyField v-if="form.kind === 'annotation'" :model-value="form.name" source="locked" /><el-input v-else v-model="form.name" maxlength="80" /></el-form-item>
        <el-form-item label="说明" prop="description"><el-input v-model="form.description" type="textarea" maxlength="500" :rows="3" /></el-form-item>
        <el-form-item label="排序" prop="sort_order"><el-input-number v-model="form.sort_order" :min="0" :max="100000" :precision="0" /><span>数字越小越靠前；当前模块优先入口自动置顶。</span></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.active" :disabled="form.kind === 'annotation'" /><span>停用后保留历史消息分类。</span></el-form-item>
        <p>当前编辑：{{ form.id ? '已有菜单' : form.parent_id ? '新增二级菜单' : '新增一级菜单' }}</p>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible = false">关闭</el-button><el-button type="primary" :loading="saving" @click="save">保存菜单</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatTopics } from '@/composables/useChatTopics'
import { topicApi } from '@/api/chatTopics'
import '@/views/resource/components/issueDialogs.css'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
const { topics, refresh } = useChatTopics()
const visible = ref(false), saving = ref(false), error = ref(''), formRef = ref()
const form = reactive({}), roots = computed(() => topics.items.filter(row => !row.parent_id))
const rules = { name: [{ required: true, whitespace: true, message: '请填写菜单名称', trigger: 'blur' }] }
function start(row, parentId = null) { Object.assign(form, { id: null, parent_id: parentId, kind: 'topic', name: '', description: '', sort_order: 100, active: true, revision: 0 }, row || {}); formRef.value?.clearValidate(); error.value = '' }
async function open() { await refresh(true); start(); visible.value = true }
async function save() {
  if (saving.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  const data = { name: form.name, description: form.description, sort_order: form.sort_order }
  try {
    const result = form.id ? await topicApi.update(form.id, { ...data, active: form.active, revision: form.revision }) : await topicApi.create({ ...data, parent_id: form.parent_id })
    await refresh(true); start(result); ElMessage.success('主题菜单已保存')
  } catch (e) { error.value = e.message; await refresh(true).catch(() => {}) }
  finally { saving.value = false }
}
defineExpose({ open })
</script>
<style scoped>
.topic-manager-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:12px}.topic-manager-root{margin:12px 0}.topic-manager-child{padding-left:20px}.topic-manager-grid :deep(.el-form-item__content){gap:8px}.topic-manager-grid span{font-size:12px;color:var(--el-text-color-secondary)}
@media(max-width:650px){.topic-manager-grid{grid-template-columns:1fr}}
</style>
