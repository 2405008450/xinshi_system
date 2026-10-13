<template>
  <DraggableFormDialog ref="dialogRef" v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="team-form-dialog" destroy-on-close :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editId ? '编辑团队' : '新增团队'" placeholder="搜索字段，如资源情况" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="团队已被其他人修改，草稿已保留。请重新读取最新内容后核对保存。" type="warning" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <section class="form-section"><h3>基本资料</h3><div class="team-form-grid">
          <el-form-item label="团队简称" prop="short_name"><el-input v-model="form.short_name" maxlength="100" show-word-limit /></el-form-item>
          <el-form-item label="团队全称" prop="full_name"><el-input v-model="form.full_name" maxlength="255" show-word-limit /></el-form-item>
          <el-form-item label="团队类型" prop="team_type"><el-select v-model="form.team_type" placeholder="请选择团队类型"><el-option v-for="item in options.team_types" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="资源类型" prop="resource_types"><el-select v-model="form.resource_types" multiple placeholder="请选择资源类型"><el-option v-for="item in options.resource_types" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item v-if="form.resource_types.includes('other')" label="其他资源说明" prop="other_resource_description" class="team-wide"><el-input v-model="form.other_resource_description" maxlength="500" show-word-limit /></el-form-item>
        </div></section>
        <section class="form-section"><h3>团队对接人</h3>
          <el-form-item label="团队对接人" prop="contacts"><div class="team-text-field"><p>{{ teamContactSummary(form.contacts) }}</p><el-button @click="contactsEditorRef.open(form.contacts)">编辑团队对接人</el-button></div></el-form-item>
        </section>
        <section class="form-section"><h3>资料附件</h3>
          <el-form-item label="资料附件"><el-button v-if="editId" :disabled="loading || saving" @click="emit('attachments', { id: editId, short_name: form.short_name })">管理资料附件</el-button><span v-else>保存团队后，可在列表的“资料附件”中上传资料。</span></el-form-item>
        </section>
        <section class="form-section"><h3>资源说明</h3>
          <el-form-item label="团队简介" prop="introduction"><div class="team-text-field"><p>{{ form.introduction || '暂未填写' }}</p><el-button @click="textEditorRef.open('introduction', '编辑简介', form.introduction)">编辑简介</el-button></div></el-form-item>
          <el-form-item label="资源情况" prop="resource_situation"><div class="team-text-field"><p>{{ form.resource_situation || '暂未填写' }}</p><el-button @click="textEditorRef.open('resource_situation', '编辑资源情况', form.resource_situation)">编辑资源情况</el-button></div></el-form-item>
          <el-form-item label="备注" prop="remarks"><el-input v-model="form.remarks" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
        </section>
        <section class="form-section"><h3>信实对接</h3><div class="team-form-grid">
          <el-form-item label="信实对接人" prop="contact_user_id"><el-select v-model="form.contact_user_id" clearable filterable placeholder="选择信实对接人"><el-option v-for="person in people" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="!person.is_active" /></el-select></el-form-item>
          <el-form-item label="对接日期" prop="contact_date"><el-date-picker v-model="form.contact_date" type="date" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" placeholder="选择对接日期" /></el-form-item>
          <el-form-item label="信实跟进人" prop="follow_up_user_id"><el-select v-model="form.follow_up_user_id" clearable filterable placeholder="选择信实跟进人"><el-option v-for="person in people" :key="person.id" :label="personLabel(person)" :value="person.id" :disabled="!person.is_active" /></el-select></el-form-item>
        </div></section>
      </AppForm>
    </div>
    <template #footer>
      <el-button v-if="conflict || failed" :disabled="loading" @click="readLatest">重新读取最新内容</el-button>
      <el-button v-if="!conflict && draft" @click="restoreDraft">恢复保留的草稿</el-button>
      <el-button :disabled="saving" @click="dialogRef.handleClose()">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || conflict || failed" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>
  <TeamTextEditor ref="textEditorRef" @confirmed="(key, value) => form[key] = value" />
  <TeamContactsEditor ref="contactsEditorRef" :can-view-contacts="options.can_view_contacts" @confirmed="value => form.contacts = value" />
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { teamApi } from '@/api/teams'
import { getRawErrorDetail } from '@/utils/errorMessages'
import { emptyTeam, personLabel, teamPayload, teamContactSummary } from '@/utils/teamResources'
import TeamTextEditor from './TeamTextEditor.vue'
import TeamContactsEditor from './TeamContactsEditor.vue'

const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved', 'attachments'])
const visible = ref(false), editId = ref(null), loading = ref(false), saving = ref(false), conflict = ref(false), failed = ref(false), draft = ref(null)
const dialogRef = ref(null), formRef = ref(null), bodyRef = ref(null), textEditorRef = ref(null), retained = ref([])
const form = reactive(emptyTeam())
const contactsEditorRef = ref(null)
const people = computed(() => [...new Map([...props.options.people, ...retained.value].map(person => [person.id, person])).values()])
const rules = {
  short_name: [{ required: true, whitespace: true, message: '请填写团队简称', trigger: 'blur' }],
  team_type: [{ required: true, message: '请选择团队类型', trigger: 'change' }],
  resource_types: [{ type: 'array', required: true, min: 1, message: '请选择至少一种资源类型', trigger: 'change' }],
  other_resource_description: [{ required: true, whitespace: true, message: '请填写其他资源说明', trigger: 'blur' }],
}
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
let request, sequence = 0, original = ''
const signature = () => JSON.stringify(teamPayload(form, props.options.can_view_contacts))
async function beforeClose(done) {
  if (saving.value) return
  if (signature() !== original) {
    try { await ElMessageBox.confirm('团队资料尚未保存，确定放弃修改吗？', '放弃修改', { type: 'warning' }) } catch { return }
  }
  request?.abort(); sequence++; done()
}
async function readLatest() {
  request?.abort(); request = new AbortController(); const seq = ++sequence
  loading.value = true; failed.value = false
  try {
    const row = await teamApi.detail(editId.value, request.signal)
    if (seq !== sequence) return
    Object.assign(form, emptyTeam(), teamPayload(row)); retained.value = [row.contact_user, row.follow_up_user].filter(Boolean)
    original = signature(); conflict.value = false
    await nextTick(); formRef.value?.clearValidate()
  } catch (error) { if (seq === sequence && error.code !== 'ERR_CANCELED') { failed.value = true; ElMessage.error(error.message) } }
  finally { if (seq === sequence) loading.value = false }
}
async function open(row) {
  request?.abort(); sequence++; editId.value = row?.id || null
  Object.assign(form, emptyTeam()); retained.value = []; draft.value = null; conflict.value = false; failed.value = false; loading.value = false
  clearFieldSearch(); original = signature(); visible.value = true
  if (editId.value) await readLatest()
  await nextTick(); formRef.value?.clearValidate()
}
function restoreDraft() { const revision = form.revision; Object.assign(form, draft.value, { revision }); draft.value = null }
async function save() {
  if (saving.value || loading.value || conflict.value || failed.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true
  const payload = teamPayload(form, props.options.can_view_contacts)
  try {
    let saved
    try { saved = await teamApi.save(payload, editId.value) }
    catch (error) {
      const detail = getRawErrorDetail(error)
      if (detail?.code !== 'team_duplicate_warning') throw error
      const names = detail.candidates.map(row => `${row.short_name}${row.full_name ? `（${row.full_name}）` : ''}`).join('、')
      try { await ElMessageBox.confirm(`发现同名团队：${names}。请核对是否重复登记，仍然保存当前团队吗？`, '团队重名提醒', { type: 'warning', confirmButtonText: '仍然保存', cancelButtonText: '返回核对' }) } catch { return }
      saved = await teamApi.save({ ...payload, allow_duplicate: true }, editId.value)
    }
    visible.value = false; emit('saved', saved); ElMessage.success('团队资料已保存')
  } catch (error) {
    if (getRawErrorDetail(error)?.code === 'team_revision_conflict') { conflict.value = true; draft.value = teamPayload(form) }
    await formRef.value?.applyServerErrors(error); ElMessage.error(error.message)
  } finally { saving.value = false }
}
onBeforeUnmount(() => { request?.abort(); sequence++ })
defineExpose({ open })
</script>

<style>
.team-form-dialog { display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
.team-form-dialog>.el-dialog__header,.team-form-dialog>.el-dialog__footer { flex-shrink:0; }
.team-form-dialog>.el-dialog__body { flex:1; min-height:0; overflow-y:auto; }
.team-form-dialog>.el-dialog__footer { background:#f8fafc; border-top:1px solid var(--el-border-color-light); }
.team-form-dialog .el-alert { margin-bottom:16px; }
.team-form-dialog .form-section h3 { font-size:15px; margin:8px 0 16px; }
.team-form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 20px; }
.team-wide { grid-column:1/-1; }
.team-form-grid .el-select,.team-form-grid .el-date-editor { width:100%; }
.team-text-field { width:100%; }
.team-text-field p { margin:0 0 8px; white-space:pre-wrap; overflow-wrap:anywhere; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
@media(max-width:640px) { .team-form-grid { grid-template-columns:minmax(0,1fr); } }
</style>
