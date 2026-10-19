<template>
  <DraggableFormDialog v-model="visible" width="min(760px, calc(100vw - 32px))" top="5vh" class="request-arrangement-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @closed="closed">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="项目每日安排" placeholder="搜索字段，如日期、平台账号" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button text :disabled="loading" @click="loadDate(true)">重新加载</el-button></el-alert>
      <RequestArrangementDetails v-if="request" :key="request.id" :request="request" :users="options.users" />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="订单号"><ReadonlyField :model-value="request?.order_no || '-'" source="auto" /></el-form-item>
        <el-form-item label="项目名称"><ReadonlyField :model-value="request?.project_name || request?.request_no || '-'" source="auto" /></el-form-item>
        <el-form-item label="语言／方言＋城市" prop="selected_scope_keys">
          <div class="request-scope-summary">
            <ReadonlyField :model-value="scopeSummary" source="auto" />
            <el-button :disabled="loading || saving || !!error" @click="scopeEditor.open(form)">编辑安排内容</el-button>
            <p class="request-scope-note">安排备注：{{ form.arrangement_note || '-' }}</p>
          </div>
        </el-form-item>
        <el-form-item label="安排日期" prop="work_date"><el-date-picker v-model="form.work_date" value-format="YYYY-MM-DD" :clearable="false" :disabled="saving" @change="loadDate(false)" /></el-form-item>
        <el-form-item label="平台账号" prop="platform_ids">
          <div class="request-account-options">
            <p class="muted">可选择多个平台账号。取消勾选只撤回本需求在所选日期的安排。</p>
            <el-checkbox-group v-model="form.platform_ids" :disabled="loading || saving || !!error">
              <section v-for="group in groups" :key="group.value" class="request-account-category">
                <h4>{{ group.label }}</h4>
                <div v-for="platform in group.platforms" :key="platform.id" class="request-account-platform">
                  <strong v-if="platform.accounts.some(account => account.accountName !== '单账号')">{{ platform.name }}</strong>
                  <el-checkbox v-for="account in platform.accounts" :key="account.id" :value="account.id">{{ account.accountName === '单账号' ? account.platformName : account.accountName }}</el-checkbox>
                </div>
              </section>
            </el-checkbox-group>
            <el-empty v-if="!loading && !groups.length" description="暂无可安排的平台账号，请先维护平台" :image-size="60" />
          </div>
        </el-form-item>
      </AppForm>
    </div>
    <template #footer><span class="muted">已选 {{ form.platform_ids.length }} 个账号</span><el-button :disabled="saving" @click="beforeClose(() => visible = false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || !!error || !form.work_date" @click="save">保存安排</el-button></template>
  </DraggableFormDialog>
  <RequestArrangementScopeEditor ref="scopeEditor" :options="request?.scope_options || []" @confirm="applyScope" />
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementTomorrow, groupArrangementAccounts } from '@/utils/resourceArrangements'
import RequestArrangementDetails from './RequestArrangementDetails.vue'
import RequestArrangementScopeEditor from './RequestArrangementScopeEditor.vue'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['saved', 'visibility-change'])
const visible = ref(false), saving = ref(false), loading = ref(false), error = ref(''), request = ref(null), cells = ref([])
watch(visible, value => emit('visibility-change', value))
const form = reactive({ work_date: '', revision: 0, platform_ids: [], selected_scope_keys: [], arrangement_note: '' }), bodyRef = ref(), formRef = ref(), scopeEditor = ref()
const savedScope = ref([])
const scopeSummary = computed(() => form.selected_scope_keys.map(key => (request.value?.scope_options || []).find(o => o.key === key)?.label || savedScope.value.find(o => o.key === key)?.label || '已失效选项').join('；') || '未配置语种与城市')
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const groups = computed(() => groupArrangementAccounts(props.options, cells.value.filter(c => c.targets?.some(t => t.request_id === request.value?.id)), { includeEmpty: false }))
let controller, sequence = 0, baseline = [], baselineDraft = '', hasLoadedDate = false
const draft = () => JSON.stringify({ platform_ids: [...form.platform_ids].sort(), selected_scope_keys: [...form.selected_scope_keys].sort(), arrangement_note: form.arrangement_note })
function applyScope(value) { Object.assign(form, value); formRef.value?.clearValidate('selected_scope_keys') }
const rules = {
  work_date: [{ required: true, message: '请选择安排日期', trigger: 'change' }],
  platform_ids: [{ validator: (_rule, value, callback) => callback(!value.length && !baseline.length ? new Error('请至少选择一个平台账号') : undefined), trigger: 'change' }],
  selected_scope_keys: [{ validator: (_rule, value, callback) => {
    const options = request.value?.scope_options || []
    callback(form.platform_ids.length && ((options.length && !value.length) || value.some(key => !options.some(o => o.key === key))) ? new Error('项目语言或城市已变化，请编辑安排内容重新选择') : undefined)
  }, trigger: 'change' }],
}
async function loadDate(keepDraft = false) {
  controller?.abort(); const seq = ++sequence
  const preserved = keepDraft && hasLoadedDate ? { platform_ids: [...form.platform_ids], selected_scope_keys: [...form.selected_scope_keys], arrangement_note: form.arrangement_note } : null
  if (!keepDraft) hasLoadedDate = false
  baseline = []; cells.value = []; error.value = ''
  if (!form.work_date) { loading.value = false; return }
  const current = new AbortController(); controller = current; loading.value = true
  try {
    const [day, detail] = await Promise.all([api.arrangement(form.work_date, current.signal), api.arrangementRequest(request.value.id, current.signal)])
    if (seq !== sequence) return
    request.value = detail
    cells.value = day.cells; form.revision = day.revision
    form.platform_ids = day.cells.filter(c => c.targets.some(t => t.request_id === request.value.id)).map(c => c.platform_id)
    baseline = [...form.platform_ids]
    const target = day.cells.flatMap(c => c.targets || []).find(t => t.kind === 'request_project' && t.request_id === request.value.id)
    savedScope.value = target?.scope || []
    form.selected_scope_keys = (target?.scope || detail.scope_options || []).map(o => o.key)
    form.arrangement_note = target?.arrangement_note || ''
    baselineDraft = draft()
    hasLoadedDate = true
    if (preserved) Object.assign(form, preserved)
    formRef.value?.clearValidate()
  } catch (e) { if (seq === sequence && !current.signal.aborted) error.value = e.message }
  finally { if (seq === sequence) loading.value = false }
}
async function open(row, date) {
  if (saving.value) return
  request.value = row; form.work_date = date || arrangementTomorrow(); form.revision = 0; hasLoadedDate = false
  form.platform_ids = []; form.selected_scope_keys = []; form.arrangement_note = ''; savedScope.value = []; baselineDraft = draft()
  clearFieldSearch(); visible.value = true; await loadDate()
}
async function beforeClose(done) {
  if (saving.value) return
  if (draft() !== baselineDraft) {
    try { await ElMessageBox.confirm('当前安排内容尚未保存，是否放弃修改？', '关闭安排', { type: 'warning' }) }
    catch { return }
  }
  done()
}
function closed() { sequence++; controller?.abort(); loading.value = false }
async function save() {
  if (saving.value || loading.value || error.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    const day = await api.assignRequest(request.value.id, form.work_date, { revision: form.revision, platform_ids: form.platform_ids, selected_scope_keys: form.selected_scope_keys, arrangement_note: form.arrangement_note })
    baseline = [...form.platform_ids]; baselineDraft = draft(); visible.value = false; ElMessage.success('每日安排已保存'); emit('saved', day)
  } catch (e) { error.value = `${e.message}；选择已保留，重新加载后可继续调整。` }
  finally { saving.value = false }
}
onBeforeUnmount(closed)
defineExpose({ open })
</script>
<style>
.request-arrangement-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.request-arrangement-dialog > .el-dialog__header, .request-arrangement-dialog > .el-dialog__footer { flex-shrink: 0; }
.request-arrangement-dialog > .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.request-arrangement-dialog > .el-dialog__footer { border-top: 1px solid var(--el-border-color-light); background: var(--el-fill-color-light); padding: 16px; }
.request-arrangement-dialog .muted { color: var(--el-text-color-secondary); font-size: 13px; }
.request-arrangement-dialog .el-alert { margin: 12px 0; }
.request-scope-summary { width: 100%; }
.request-scope-summary > .el-button { margin-top: 8px; }
.request-scope-note { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 0; }
.request-account-options{width:100%}.request-account-category{padding:10px 14px;border:1px solid var(--el-border-color-light);border-radius:6px;margin-bottom:12px}.request-account-category h4{margin:0 0 10px}.request-account-platform{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.request-account-platform>strong{width:120px;overflow-wrap:anywhere}.request-account-platform .el-checkbox{height:auto;min-height:32px;margin-right:12px;max-width:100%}.request-account-platform .el-checkbox__label{white-space:normal;overflow-wrap:anywhere}.request-arrangement-dialog>.el-dialog__footer{display:flex;justify-content:flex-end;align-items:center;gap:10px}.request-arrangement-dialog>.el-dialog__footer>.muted{margin-right:auto}.request-arrangement-dialog .el-date-editor{width:100%}
@media(max-width:600px){.request-account-platform>strong{width:100%}.request-arrangement-dialog>.el-dialog__footer{flex-wrap:wrap}}
</style>
