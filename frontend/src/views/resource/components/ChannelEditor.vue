<template>
  <DraggableFormDialog v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="channel-dialog" destroy-on-close>
    <template #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editId ? '编辑渠道' : '新增渠道'" placeholder="搜索字段，如维护人" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
    </template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="渠道已被修改，草稿已保留。请重新读取最新内容后再保存。" type="warning" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="channel-form-grid">
          <el-form-item label="渠道／平台名称" prop="name"><el-input v-model="form.name" maxlength="100" show-word-limit /></el-form-item>
          <el-form-item label="平台性质" prop="category"><el-select v-model="form.category" placeholder="请选择平台性质"><el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="维护人" prop="maintainer_ids"><el-select v-model="form.maintainer_ids" multiple filterable clearable placeholder="选择维护人（可多选）"><el-option v-for="person in peopleFor('maintainers')" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="person.is_active === false" /></el-select></el-form-item>
          <el-form-item label="使用人" prop="user_ids"><el-select v-model="form.user_ids" multiple filterable clearable placeholder="选择使用人（可多选）"><el-option v-for="person in peopleFor('users')" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="person.is_active === false" /></el-select></el-form-item>
          <el-form-item label="平台用途" prop="purpose" class="channel-wide"><el-input v-model="form.purpose" type="textarea" :rows="4" maxlength="2000" show-word-limit /></el-form-item>
          <el-form-item label="平台情况说明" prop="description" class="channel-wide"><el-input v-model="form.description" type="textarea" :rows="8" maxlength="5000" show-word-limit /></el-form-item>
        </div>
      </AppForm>
    </div>
    <template #footer>
      <el-button v-if="conflict || failed" :loading="loading" @click="readLatest">重新读取最新内容</el-button>
      <el-button v-if="!conflict && draft" @click="restoreDraft">恢复保留的草稿</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || conflict || failed" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'

const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const visible = ref(false), loading = ref(false), saving = ref(false), editId = ref(null), formRef = ref(null), bodyRef = ref(null), conflict = ref(false), failed = ref(false), draft = ref(null)
const retained = reactive({ maintainers: [], users: [] })
const empty = () => ({ name: '', category: '', purpose: '', description: '', maintainer_ids: [], user_ids: [], revision: 0 })
const form = reactive(empty())
const rules = { name: [{ required: true, whitespace: true, message: '请填写渠道／平台名称', trigger: 'blur' }], category: [{ required: true, message: '请选择平台性质', trigger: 'change' }] }
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const personLabel = person => `${person.name}${person.is_active === false ? '（已停用）' : ''}`
const peopleFor = role => [...new Map([...(props.options.users || []), ...retained[role]].map(person => [person.id, person])).values()]
const payload = () => ({ ...form, maintainer_ids: [...form.maintainer_ids], user_ids: [...form.user_ids] })
let request, sequence = 0
async function readLatest() {
  request?.abort(); request = new AbortController(); const seq = ++sequence
  loading.value = true; failed.value = false
  try {
    const row = await api.channel(editId.value, request.signal)
    if (seq !== sequence) return
    Object.assign(form, { name: row.name, category: row.category, purpose: row.purpose, description: row.description, revision: row.revision, maintainer_ids: row.maintainers.map(person => person.id), user_ids: row.users.map(person => person.id) })
    Object.assign(retained, { maintainers: row.maintainers, users: row.users }); conflict.value = false
  } catch (error) { if (seq === sequence && error.code !== 'ERR_CANCELED') { failed.value = true; ElMessage.error(error.message) } }
  finally { if (seq === sequence) loading.value = false }
}
async function open(row, category = '') {
  request?.abort(); sequence++; editId.value = row?.id || null
  Object.assign(form, empty(), { category }); Object.assign(retained, { maintainers: [], users: [] })
  draft.value = null; conflict.value = false; failed.value = false; clearFieldSearch(); visible.value = true
  if (editId.value) await readLatest()
  await nextTick(); formRef.value?.clearValidate()
}
function restoreDraft() {
  const revision = form.revision
  // 只恢复业务输入；最新版本号及停用人员名单仍以重新读取的服务器资料为准。
  Object.assign(form, draft.value, { revision }); draft.value = null
}
async function save() {
  if (saving.value || loading.value || conflict.value || failed.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    const saved = await api.saveChannel(payload(), editId.value)
    visible.value = false; emit('saved', saved); ElMessage.success('渠道资料已保存')
  } catch (error) {
    if (editId.value && error.response?.status === 409 && !String(error.message).includes('同名')) { conflict.value = true; draft.value = payload() }
    await formRef.value?.applyServerErrors(error); ElMessage.error(error.message)
  } finally { saving.value = false }
}
onBeforeUnmount(() => { request?.abort(); sequence++ })
defineExpose({ open })
</script>

<style scoped>
.channel-form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 20px; }
.channel-form-grid .el-select { width:100%; }
.channel-wide { grid-column:1/-1; }
@media (max-width:640px) { .channel-form-grid { grid-template-columns:minmax(0,1fr); } }
</style>
