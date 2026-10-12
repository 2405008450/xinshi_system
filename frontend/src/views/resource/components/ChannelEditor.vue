<template>
  <DraggableFormDialog v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="channel-dialog" destroy-on-close>
    <template #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editId ? (isAccount ? '编辑账号' : '编辑渠道') : (isAccount ? '新增账号' : '新增渠道')" placeholder="搜索字段，如维护人" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
    </template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="渠道已被修改，草稿已保留。请重新读取最新内容后再保存。" type="warning" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="channel-form-grid">
          <el-form-item label="渠道／平台名称" prop="name"><el-input v-model="form.name" maxlength="100" show-word-limit /></el-form-item>
          <el-form-item label="平台性质" prop="category"><el-select v-model="form.category" placeholder="请选择平台性质"><el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item v-if="isAccount" label="所属平台" prop="parent_id" class="channel-wide"><ReadonlyField :model-value="parentName" source="auto" placeholder="选择平台后自动带出" /><small class="channel-muted">账号归属调整请在目标平台的账号管理中进行。</small></el-form-item>
          <el-form-item v-else-if="options.hierarchy_available" label="账号管理" prop="account_ids" class="channel-wide">
            <el-select v-model="form.account_ids" multiple filterable clearable placeholder="选择已有账号，可输入账号名称搜索">
              <el-option v-for="account in selectableAccounts" :key="account.id" :value="account.id" :label="account.parent_id && account.parent_id !== editId ? `${account.name}（当前归属：${account.parent_name}）` : account.name" />
            </el-select>
            <small class="channel-muted">关联保留原账号及历史记录；取消勾选只解除归属。创建账号请使用列表中的“新增账号”。</small>
          </el-form-item>
          <el-form-item label="维护人" prop="maintainer_ids"><template v-if="selectedAccounts.length"><ReadonlyField :model-value="summary('maintainers')" source="auto" /><small class="channel-muted">由子账号维护人自动汇总</small></template><el-select v-else v-model="form.maintainer_ids" multiple filterable clearable placeholder="选择维护人（可多选）"><el-option v-for="person in peopleFor('maintainers')" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="person.is_active === false" /></el-select></el-form-item>
          <el-form-item label="使用人" prop="user_ids"><template v-if="selectedAccounts.length"><ReadonlyField :model-value="summary('users')" source="auto" /><small class="channel-muted">由子账号使用人自动汇总</small></template><el-select v-else v-model="form.user_ids" multiple filterable clearable placeholder="选择使用人（可多选）"><el-option v-for="person in peopleFor('users')" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="person.is_active === false" /></el-select></el-form-item>
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
import './channelDialog.css'
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { aggregateChannelMembers, channelMembersText } from '@/utils/resourceChannels'

const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const visible = ref(false), loading = ref(false), saving = ref(false), editId = ref(null), formRef = ref(null), bodyRef = ref(null), conflict = ref(false), failed = ref(false), draft = ref(null)
const retained = reactive({ maintainers: [], users: [] })
const empty = () => ({ name: '', category: '', purpose: '', description: '', maintainer_ids: [], user_ids: [], revision: 0, is_group: true, account_ids: [], parent_id: null, parent_revision: null })
const form = reactive(empty())
const accountCandidates = ref([]), parentName = ref(''), originalAccounts = ref([])
const isAccount = computed(() => Boolean(form.parent_id))
const selectableAccounts = computed(() => accountCandidates.value.filter(account => account.id !== editId.value))
const selectedAccounts = computed(() => selectableAccounts.value.filter(account => form.account_ids.includes(account.id)))
const summary = role => channelMembersText(aggregateChannelMembers(selectedAccounts.value, role))
const rules = { name: [{ required: true, whitespace: true, message: '请填写渠道／平台名称', trigger: 'blur' }], category: [{ required: true, message: '请选择平台性质', trigger: 'change' }] }
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const personLabel = person => `${person.name}${person.is_active === false ? '（已停用）' : ''}`
const peopleFor = role => [...new Map([...(props.options.users || []), ...retained[role]].map(person => [person.id, person])).values()]
const payload = () => {
  const value = { ...form, maintainer_ids: [...form.maintainer_ids], user_ids: [...form.user_ids] }
  if (isAccount.value) {
    delete value.account_ids
  } else {
    delete value.parent_id; delete value.parent_revision
    if (!props.options.hierarchy_available) delete value.account_ids
    value.account_revisions = Object.fromEntries([...originalAccounts.value, ...accountCandidates.value].map(account => [account.id, account.revision]))
  }
  return value
}
let request, sequence = 0
async function readLatest() {
  request?.abort(); request = new AbortController(); const seq = ++sequence
  loading.value = true; failed.value = false
  try {
    if (!editId.value) {
      const [accounts, parent] = await Promise.all([
        props.options.hierarchy_available ? api.channelAccountOptions(request.signal) : Promise.resolve([]),
        form.parent_id ? api.channel(form.parent_id, request.signal) : Promise.resolve(null),
      ])
      if (seq !== sequence) return
      accountCandidates.value = accounts
      if (parent) { form.parent_revision = parent.revision; parentName.value = parent.name }
      conflict.value = false
      return
    }
    const [row, accounts] = await Promise.all([api.channel(editId.value, request.signal), props.options.hierarchy_available ? api.channelAccountOptions(request.signal) : Promise.resolve([])])
    if (seq !== sequence) return
    Object.assign(form, { name: row.name, category: row.category, purpose: row.purpose, description: row.description, revision: row.revision, is_group: row.kind === 'channel_group', account_ids: (row.accounts || []).map(account => account.id), parent_id: row.parent_id || null, parent_revision: row.parent_revision || null, maintainer_ids: (row.direct_maintainers || row.maintainers).map(person => person.id), user_ids: (row.direct_users || row.users).map(person => person.id) })
    originalAccounts.value = row.accounts || []; accountCandidates.value = accounts; parentName.value = row.parent_name || ''
    Object.assign(retained, { maintainers: row.direct_maintainers || row.maintainers, users: row.direct_users || row.users }); conflict.value = false
  } catch (error) { if (seq === sequence && error.code !== 'ERR_CANCELED') { failed.value = true; ElMessage.error(error.message) } }
  finally { if (seq === sequence) loading.value = false }
}
async function open(row, category = '', parent = null) {
  request?.abort(); sequence++; editId.value = row?.id || null
  Object.assign(form, empty(), { category }); Object.assign(retained, { maintainers: [], users: [] })
  originalAccounts.value = []; accountCandidates.value = []; parentName.value = parent?.name || ''; loading.value = false
  if (parent) Object.assign(form, { category: parent.category, parent_id: parent.id, parent_revision: parent.revision, is_group: false })
  draft.value = null; conflict.value = false; failed.value = false; clearFieldSearch(); visible.value = true
  if (editId.value) await readLatest()
  else if (!parent && props.options.hierarchy_available) {
    loading.value = true; const seq = sequence; request = new AbortController()
    try { const accounts = await api.channelAccountOptions(request.signal); if (seq === sequence) accountCandidates.value = accounts }
    catch (error) { if (seq === sequence && error.code !== 'ERR_CANCELED') { failed.value = true; ElMessage.error(error.message) } }
    finally { if (seq === sequence) loading.value = false }
  }
  await nextTick(); formRef.value?.clearValidate()
}
function restoreDraft() {
  const revision = form.revision, parentRevision = form.parent_revision
  // 只恢复业务输入；最新版本号及停用人员名单仍以重新读取的服务器资料为准。
  const { account_revisions: _revisions, ...businessDraft } = draft.value
  Object.assign(form, businessDraft, { revision, parent_revision: parentRevision }); draft.value = null
}
async function save() {
  if (saving.value || loading.value || conflict.value || failed.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    const moved = selectedAccounts.value.filter(account => account.parent_id && account.parent_id !== editId.value)
    if (moved.length) await ElMessageBox.confirm(`以下账号将转移到当前平台：${moved.map(account => `${account.name}（原平台：${account.parent_name}）`).join('、')}。原账号及历史记录保持不变。`, '确认调整账号归属', { confirmButtonText: '确认转移', cancelButtonText: '取消', type: 'warning' })
    const saved = await api.saveChannel(payload(), editId.value)
    visible.value = false; emit('saved', saved); ElMessage.success('渠道资料已保存')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    if (error.response?.status === 409 && !String(error.message).includes('同名')) { conflict.value = true; draft.value = payload() }
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
.channel-form-grid small { display:block; margin-top:5px; line-height:1.5; }
@media (max-width:640px) { .channel-form-grid { grid-template-columns:minmax(0,1fr); } }
</style>
