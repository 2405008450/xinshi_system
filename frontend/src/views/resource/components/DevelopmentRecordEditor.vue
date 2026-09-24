<template>
  <DraggableFormDialog v-model="visible" width="min(1000px, calc(100vw - 32px))" top="5vh" class="development-dialog" destroy-on-close :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="quickMode ? `${form.full_name} · 快捷跟进` : form.revision ? '编辑资源开拓' : '新增资源开拓'" placeholder="搜索字段，如资源姓名" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" @keydown="saveShortcut">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <template v-if="!quickMode">
        <h3>本批次录入信息</h3>
        <p class="muted">当天再次新增时沿用上次保存的日期、开拓人员、平台和账号。业绩与日报归属开拓人员，实际录入人由系统自动记录。</p>
        <div class="development-form-grid">
          <el-form-item label="开拓平台" prop="platform_id"><el-select v-model="form.platform_id" filterable><el-option-group v-for="group in categoryOptions" :key="group.value" :label="group.label"><el-option v-for="p in platforms.filter(p => p.category === group.value)" :key="p.id" :label="p.name" :value="p.id" /></el-option-group></el-select></el-form-item>
          <el-form-item label="日期" prop="work_date"><el-date-picker v-model="form.work_date" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
          <el-form-item label="开拓人员" prop="owner_id"><el-select v-model="form.owner_id" filterable :disabled="!options.can_delegate" @change="followOperator = ''"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
          <el-form-item label="对接账号"><el-select v-model="form.account_id" clearable filterable @clear="form.account_id = null"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
        </div>
        <h3>资源资料</h3>
        <div class="development-form-grid">
          <el-form-item label="招呼编号"><ReadonlyField :model-value="greetingNo" source="auto" placeholder="保存后自动生成" /></el-form-item>
          <el-form-item label="资源姓名" prop="full_name"><el-input v-model="form.full_name" maxlength="255" @blur="checkName" /></el-form-item>
          <el-form-item label="资源语种/方言" class="wide"><el-select v-model="form.language_ids" multiple filterable><el-option v-for="l in options.languages" :key="l.id" :label="`${l.label}${l.language_type === 'dialect' ? '（方言）' : ''}`" :value="l.id" /></el-select></el-form-item>
          <el-form-item label="资源手机" prop="phone"><el-input v-model="form.phone" maxlength="100" /></el-form-item>
          <el-form-item label="资源微信号" prop="wechat"><el-input v-model="form.wechat" maxlength="100" /></el-form-item>
        </div>
        </template>
        <el-alert v-if="nameCandidates.length && !needsEnrollment" type="warning" :closable="false" :title="`人才总库有 ${nameCandidates.length} 条疑似匹配，添加成功时请确认关联。`" />
        <h3>跟进进展</h3>
        <p v-if="historicalOnly" class="muted">历史导入记录：仅在资源开拓保存跟进标记，不创建、关联或跳转人才总库。</p><p v-else class="muted">微信、企微“已添加”会进入人才入库流程；进群、沟通、入项独立记录，入项标记不会自动生成项目安排。</p>
        <el-button v-if="quickMode" text type="primary" @click="quickMode = false">查看全部历史及资料</el-button>
        <div v-for="(action, index) in form.actions" v-show="!quickMode || !savedActionIds.includes(action.id)" :key="action.id" class="development-action" data-dialog-field-search-group>
          <div data-dialog-field-search-group-title>操作 {{ index + 1 }}<span v-if="action.request_number"> · 第 {{ action.request_number }} 次请求</span></div>
          <div class="development-form-grid">
            <el-form-item label="跟进类型" :prop="`actions.${index}.channel`" :rules="required('请选择跟进类型')"><el-select v-model="action.channel" @change="action.status = progressStatuses(action.channel).at(-1)"><el-option v-for="(label, value) in progressChannels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
            <el-form-item label="跟进状态" :prop="`actions.${index}.status`" :rules="required('请选择跟进状态')"><el-select v-model="action.status" filterable allow-create default-first-option><el-option v-for="s in progressStatuses(action.channel)" :key="s" :label="s" :value="s" /></el-select></el-form-item>
            <el-form-item label="操作日期" :prop="`actions.${index}.action_date`" :rules="required('请选择操作日期')"><el-date-picker v-model="action.action_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="操作人员" :prop="`actions.${index}.operator_id`" :rules="required('请选择操作人员')"><el-select v-model="action.operator_id" filterable><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
            <el-form-item label="操作账号"><el-select v-model="action.account_id" clearable filterable @clear="action.account_id = null"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
          </div>
          <el-button v-if="!savedActionIds.includes(action.id)" text type="danger" @click="form.actions.splice(index, 1)">移除此条未保存操作</el-button>
          <small v-else class="muted">录入：{{ action.created_by_name }}；最近修改：{{ action.updated_by_name }}</small>
        </div>
        <el-button v-if="!quickMode" @click="addAction()">新增一次跟进</el-button>
        <template v-if="needsEnrollment">
          <h3>进入人才总库</h3>
          <el-form-item label="专业分类" prop="capabilities"><el-checkbox-group v-model="form.capabilities"><el-checkbox v-for="c in capabilityOptions" :key="c.value" :value="c.value">{{ c.label }}</el-checkbox></el-checkbox-group></el-form-item>
          <el-button :loading="checking" @click="checkName">检查重复人才</el-button>
          <el-form-item v-if="nameCandidates.length" label="关联已有档案" prop="link_person_id"><el-select v-model="form.link_person_id" clearable @clear="form.link_person_id = null"><el-option v-for="p in nameCandidates" :key="p.id" :value="p.id" :label="`${p.full_name} / ${p.resource_code || '暂无编号'}（${p.match_fields.map(f => ({name:'同名',phone:'同手机号',wechat:'同微信号'})[f]).join('、')}）`" /></el-select></el-form-item>
          <el-form-item v-if="nameCandidates.length && !form.link_person_id" label="不是同一人的说明" prop="duplicate_note"><el-input v-model="form.duplicate_note" type="textarea" :rows="3" placeholder="仅同名时可填写说明另建；手机号或微信号冲突需先处理" /></el-form-item>
        </template>
        <el-alert v-if="personId" type="success" :closable="false" :title="`已关联人才：${resourceCode || '已入库'}，修改开拓记录不会覆盖人才档案。`" />
        <el-form-item label="后续跟进"><el-input v-model="form.follow_up" type="textarea" :rows="quickMode ? 2 : 5" maxlength="20000" placeholder="可补充沟通内容、群名、入项项目等" /></el-form-item>
        <el-form-item v-if="!quickMode" label="备注"><el-input v-model="form.remarks" type="textarea" :rows="5" maxlength="20000" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><span class="muted">Ctrl / ⌘ + Enter：{{ form.revision ? '保存' : '保存并继续新增' }}</span><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button v-if="!form.revision" type="primary" :loading="saving" @click="save(true)">保存并继续新增</el-button><el-button :type="form.revision ? 'primary' : 'default'" :loading="saving" @click="save(false)">保存</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions, progressChannels, progressStatuses, continueDevelopmentValues, restoreDevelopmentBatch, newDevelopmentId, dateText, previousWorkday } from '@/utils/resourceDevelopment'
const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), checking = ref(false), formRef = ref(null), bodyRef = ref(null)
const quickMode = ref(false)
const followOperator = ref(''), followDate = ref(''), followOwner = ref('')
const batchKey = () => `resource-development:entry-batch:${props.options.user_id}`
function readBatch() {
  try { return restoreDevelopmentBatch(JSON.parse(sessionStorage.getItem(batchKey()) || 'null'), props.options) } catch { return {} }
}
function saveShortcut(event) {
  if (event.isComposing || event.repeat || !(event.ctrlKey || event.metaKey) || event.key !== 'Enter') return
  event.preventDefault(); save(!form.revision)
}
const historicalOnly = ref(false)
const greetingNo = ref(''), personId = ref(null), resourceCode = ref(''), savedActionIds = ref([]), nameCandidates = ref([])
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const empty = () => ({ id: newDevelopmentId(), revision: 0, platform_id: '', work_date: props.options.default_date || previousWorkday(), owner_id: props.options.user_id, full_name: '', account_id: null, phone: '', wechat: '', language_ids: [], follow_up: '', remarks: '', actions: [], capabilities: [], link_person_id: null, duplicate_note: '' })
const form = reactive(empty())
const platforms = computed(() => props.options.options.filter(o => o.kind === 'platform'))
const accounts = computed(() => props.options.options.filter(o => o.kind === 'account'))
const needsEnrollment = computed(() => !historicalOnly.value && !personId.value && ['wechat', 'enterprise'].some(channel => form.actions.filter(a => a.channel === channel).at(-1)?.status === '已添加'))
const capabilityOptions = [{ value: 'written_translation', label: '笔译' }, { value: 'interpretation', label: '口译' }, { value: 'annotation', label: '标注' }, { value: 'recruitment', label: '全职' }]
const required = message => [{ required: true, message, trigger: 'change' }]
const rules = computed(() => ({ platform_id: required('请选择开拓平台'), work_date: required('请选择日期'), owner_id: required('请选择开拓人员'), full_name: required('请填写资源姓名'), capabilities: needsEnrollment.value && !form.link_person_id ? [{ type: 'array', required: true, min: 1, message: '请选择至少一个专业分类', trigger: 'change' }] : [] }))
function payload() {
  return { ...form, account_id: form.account_id || null, actions: form.actions.map(a => ({ id: a.id, channel: a.channel, status: a.status, action_date: a.action_date, operator_id: a.operator_id, account_id: a.account_id || null })) }
}
let checkSequence = 0
async function checkName() {
  if (historicalOnly.value || !form.full_name.trim() || !form.platform_id) return
  const seq = ++checkSequence; checking.value = true
  try { const result = await api.duplicates(payload()); if (seq === checkSequence) nameCandidates.value = result.items }
  catch (e) { if (seq === checkSequence) ElMessage.error(e.message) }
  finally { if (seq === checkSequence) checking.value = false }
}
function addAction(channel = 'wechat', quick = false) { form.actions.push({ id: newDevelopmentId(), channel, status: quick ? progressStatuses(channel).at(-1) : '已发请求', action_date: followDate.value || dateText(new Date()), operator_id: followOwner.value === form.owner_id && props.options.users.some(u => u.id === followOperator.value) ? followOperator.value : form.owner_id, account_id: form.account_id }) }
async function open(row, channel) {
  const data = row ? await api.detail(row.id) : null
  Object.assign(form, empty()); nameCandidates.value = []; clearFieldSearch(); checkSequence++
  if (!data) Object.assign(form, readBatch())
  if (data) for (const key of Object.keys(form)) if (key in data) form[key] = data[key]
  historicalOnly.value = Boolean(data?.historical_only)
  greetingNo.value = data?.greeting_no || ''; personId.value = data?.person_id || null; resourceCode.value = data?.resource_code || ''
  savedActionIds.value = form.actions.map(a => a.id); quickMode.value = Boolean(channel)
  if (channel) addAction(channel, true)
  visible.value = true
}
async function save(continueAdding = false) {
  if (saving.value) return
  saving.value = true
  try {
    if (!await formRef.value.validate().catch(() => false)) return
    if (needsEnrollment.value) {
      const checked = await api.duplicates(payload()); nameCandidates.value = checked.items
      if (checked.items.length && !form.link_person_id) {
        const strong = checked.items.some(p => p.match_fields.some(f => ['phone', 'wechat'].includes(f)))
        if (strong || !form.duplicate_note.trim()) {
          ElMessage.warning(strong ? '手机号或微信号重复，请关联已有档案或先处理冲突' : '存在同名人才，请选择关联，或填写不是同一人的说明')
          await locateDialogFieldByLabel('关联已有档案'); return
        }
      }
    }
    await api.save(payload())
    if (!form.revision) {
      try { sessionStorage.setItem(batchKey(), JSON.stringify({ user_id: props.options.user_id, day: dateText(new Date()), batch: continueDevelopmentValues(form) })) } catch { /* 浏览器禁用存储时不影响保存。 */ }
    }
    const latest = form.actions.filter(a => !savedActionIds.value.includes(a.id)).at(-1)
    if (latest) { followOperator.value = latest.operator_id; followDate.value = latest.action_date; followOwner.value = form.owner_id }
    emit('saved'); ElMessage.success('资源开拓已保存')
    if (continueAdding) {
      const retained = continueDevelopmentValues(form)
      await open(); Object.assign(form, retained)
      await nextTick()
      formRef.value?.clearValidate()
      await locateDialogFieldByLabel('资源姓名')
      formRef.value?.clearValidate()
    } else visible.value = false
  } catch (e) {
    if (e.rawDetail?.duplicates) { nameCandidates.value = e.rawDetail.duplicates; await locateDialogFieldByLabel('关联已有档案') }
    ElMessage.error(e.message)
  } finally { saving.value = false }
}
defineExpose({ open })
</script>

