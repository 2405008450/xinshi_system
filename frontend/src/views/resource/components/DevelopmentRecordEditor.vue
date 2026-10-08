<template>
  <DraggableFormDialog v-model="visible" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body class="development-dialog" destroy-on-close :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="quickMode ? `${form.full_name} · ${followUpMode ? '后续跟进情况' : '快捷跟进'}` : form.revision ? '编辑资源开拓' : '新增资源开拓'" placeholder="搜索字段，如资源姓名" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" @keydown="saveShortcut">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <template v-if="!quickMode">
        <h3>本批次录入信息</h3>
        <p class="muted">当天再次新增时沿用上次保存的日期、开拓人员、平台和账号。业绩与日报归属开拓人员，实际录入人由系统自动记录。</p>
        <div class="development-form-grid">
          <el-form-item label="开拓平台" prop="platform_id"><el-select v-model="form.platform_id" filterable><el-option-group v-for="group in categoryOptions" :key="group.value" :label="group.label"><el-option v-for="p in platforms.filter(p => p.category === group.value)" :key="p.id" :label="p.name" :value="p.id" /></el-option-group></el-select></el-form-item>
          <el-form-item label="日期" prop="work_date"><el-date-picker v-model="form.work_date" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
          <el-form-item label="开拓人员" prop="owner_id"><el-select v-model="form.owner_id" filterable :disabled="!options.can_delegate"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
          <el-form-item label="交换账号"><el-select v-model="form.account_id" clearable filterable @clear="form.account_id = null"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
          <el-form-item label="加微账号" prop="friend_accounts"><CompanyWechatAccountSelect v-model="form.friend_accounts" /></el-form-item>
        </div>
        <h3>资源资料</h3>
        <div class="development-form-grid">
          <el-form-item label="招呼编号"><ReadonlyField :model-value="greetingNo" source="auto" placeholder="保存后自动生成" /></el-form-item>
          <el-form-item label="资源姓名" prop="full_name">
            <el-input v-model="form.full_name" maxlength="255" @blur="checkRecordName()" />
            <div v-if="!form.revision && !quickMode" class="record-name-check" aria-live="polite">
              <span v-if="recordChecking" class="muted">正在检查同名开拓记录…</span>
              <template v-if="recordCheckFailed"><span class="record-name-warning">查重失败，请重试</span><el-button link type="primary" @click="checkRecordName()">重试</el-button></template>
              <template v-if="recordTotal && !recordCheckFailed">
                <span class="record-name-warning">资源开拓中存在 {{ recordTotal }} 条同名记录，请人工核实</span>
                <el-popover v-model:visible="recordPopover" trigger="click" placement="bottom-end" :width="760" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }" title="同名资源开拓记录" popper-class="record-name-duplicates-popover">
                  <template #reference><el-button link type="primary">查看同名记录</el-button></template>
                  <div v-loading="recordChecking" class="record-name-duplicates-body">
                    <el-descriptions v-for="item in recordCandidates" :key="item.id" :column="2" border size="small" class="record-name-duplicate-item">
                      <el-descriptions-item label="资源姓名">{{ item.full_name || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="招呼编号">{{ item.greeting_no || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="微信号">{{ item.contact_restricted ? '受限' : item.wechat || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="手机号">{{ item.contact_restricted ? '受限' : item.phone || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="开拓人员">{{ item.owner_name || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="开拓平台">{{ item.platform_name || '-' }}</el-descriptions-item>
                      <el-descriptions-item label="业务日期" :span="2">{{ duplicateDate(item.work_date) }}</el-descriptions-item>
                    </el-descriptions>
                  </div>
                  <el-pagination v-if="recordTotal > 20" small layout="prev, pager, next" :page-size="20" :total="recordTotal" :current-page="recordPage" @current-change="checkRecordName" />
                  <div class="record-name-duplicates-footer"><span>同名仅作提醒，请人工核实是否为同一人。</span><el-button link type="primary" @click="recordPopover = false">关闭</el-button></div>
                </el-popover>
              </template>
            </div>
          </el-form-item>
          <el-form-item label="资源语种/方言" class="wide"><el-select v-model="form.language_ids" multiple filterable><el-option v-for="l in options.languages" :key="l.id" :label="`${l.label}${l.language_type === 'dialect' ? '（方言）' : ''}`" :value="l.id" /></el-select></el-form-item>
          <el-form-item label="资源手机" prop="phone" class="wide"><el-input v-model="form.phone" maxlength="100" /></el-form-item>
          <el-form-item label="资源微信号" prop="wechat"><el-input v-model="form.wechat" maxlength="100" /></el-form-item>
          <el-form-item label="资源小红书号" prop="xiaohongshu"><el-input v-model="form.xiaohongshu" maxlength="100" /></el-form-item>
        </div>
        </template>
        <h3>跟进进展</h3>
        <p v-if="historicalOnly" class="muted">历史导入记录：原表标记不自动入库；今后确认添加好友或小群、大群已进群时，会查重并进入人才总库。</p><p v-else class="muted">微信、企微“已添加”或企微小群、大群“已进群”会进入人才入库流程；已拉群、已发码、已退群不触发入库。</p>
        <el-button v-if="quickMode" text type="primary" @click="quickMode = false">查看全部历史及资料</el-button>
        <div v-for="(action, index) in form.actions" v-show="!quickMode || !savedActionIds.includes(action.id)" :key="action.id" class="development-action" data-dialog-field-search-group>
          <div data-dialog-field-search-group-title>操作 {{ index + 1 }}<span v-if="action.request_number"> · 第 {{ action.request_number }} 次请求</span></div>
          <div class="development-form-grid">
            <el-form-item label="跟进类型" :prop="`actions.${index}.channel`" :rules="required('请选择跟进类型')"><el-select v-model="action.channel" :disabled="isGroupChannel(action.channel) && savedActionIds.includes(action.id)" @change="changeActionChannel(action)"><el-option v-for="(label, value) in progressChannels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
            <el-form-item label="跟进状态" :prop="`actions.${index}.status`" :rules="required('请选择跟进状态')"><ReadonlyField v-if="isGroupChannel(action.channel) && savedActionIds.includes(action.id)" :model-value="action.status" source="auto" /><el-select v-else v-model="action.status" filterable :allow-create="!isGroupChannel(action.channel)" default-first-option><el-option v-for="s in progressStatuses(action.channel)" :key="s" :label="s" :value="s" /></el-select></el-form-item>
            <el-form-item label="操作日期" :prop="`actions.${index}.action_date`" :rules="required('请选择操作日期')"><ReadonlyField v-if="isGroupChannel(action.channel)" :model-value="action.action_date" source="auto" /><el-date-picker v-else v-model="action.action_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="操作人员" :prop="`actions.${index}.operator_id`" :rules="required('请选择操作人员')"><ReadonlyField v-if="isGroupChannel(action.channel)" :model-value="options.users.find(u => u.id === action.operator_id)?.name || action.operator_name || '-'" source="auto" /><el-select v-else v-model="action.operator_id" filterable><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
            <el-form-item label="操作账号"><el-select v-model="action.account_id" :disabled="isGroupChannel(action.channel) && savedActionIds.includes(action.id)" clearable filterable @clear="action.account_id = null"><el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
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
        <el-alert v-if="personId" type="success" :closable="false" :title="`已关联人才：${resourceCode || '已入库'}，交换账号、加微账号会汇总到人才总库，已添加和已删状态双向同步。`" />
        <section v-if="!quickMode || followUpMode" class="form-section">
          <h3>后续跟进情况</h3>
          <p class="muted">手工填写跟进内容，保存后自动记录操作人和操作时间。已保存记录只读，可新增一条补充或更正说明。</p>
          <div v-for="(entry, index) in form.follow_ups" :key="entry.id" class="development-action" data-dialog-field-search-group>
            <div data-dialog-field-search-group-title>新增跟进 {{ index + 1 }}</div>
            <el-form-item label="后续跟进情况" :prop="`follow_ups.${index}.content`" :rules="[{ required: true, whitespace: true, message: '请填写跟进内容或移除此条草稿', trigger: 'blur' }]">
              <el-input v-model="entry.content" type="textarea" :rows="3" maxlength="20000" show-word-limit placeholder="请输入本次跟进情况" />
            </el-form-item>
            <el-button text type="danger" @click="form.follow_ups.splice(index, 1)">移除此条草稿</el-button>
          </div>
          <el-button @click="addFollowUp">新增跟进情况</el-button>
          <DevelopmentFollowUpHistory :entries="followUpHistory" :legacy="form.follow_up" />
        </section>
        <el-alert v-if="versionConflict" type="warning" :closable="false" title="记录已变化，草稿已保留。重新加载最新资料后再保存；其他未保存的资料和状态修改将被重新加载替换。">
          <el-button :loading="saving" @click="reloadWithDrafts">重新加载（保留文字草稿）</el-button>
        </el-alert>
        <el-form-item v-if="!quickMode" label="备注"><el-input v-model="form.remarks" type="textarea" :rows="5" maxlength="20000" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><span class="muted">Ctrl / ⌘ + Enter：{{ form.revision ? '保存' : '保存并继续新增' }}</span><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button v-if="!form.revision" type="primary" :loading="saving" @click="save(true)">保存并继续新增</el-button><el-button :type="form.revision ? 'primary' : 'default'" :loading="saving" @click="save(false)">保存</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import CompanyWechatAccountSelect from '@/components/common/CompanyWechatAccountSelect.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DevelopmentFollowUpHistory from './DevelopmentFollowUpHistory.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions, progressChannels, progressStatuses, defaultProgressStatus, hasNewPrivateEntry, continueDevelopmentValues, restoreDevelopmentBatch, newDevelopmentId, dateText, previousWorkday, isGroupChannel, developmentDateRange } from '@/utils/resourceDevelopment'
const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), checking = ref(false), formRef = ref(null), bodyRef = ref(null)
const quickMode = ref(false), followUpMode = ref(false), followUpHistory = ref([]), versionConflict = ref(false)
const batchKey = () => `resource-development:entry-batch:${props.options.user_id}`
function readBatch() {
  try { return restoreDevelopmentBatch(JSON.parse(sessionStorage.getItem(batchKey()) || 'null'), props.options) } catch { return {} }
}
function saveShortcut(event) {
  if (event.isComposing || event.repeat || !(event.ctrlKey || event.metaKey) || event.key !== 'Enter') return
  event.preventDefault(); save(!form.revision)
}
const historicalOnly = ref(false), originalActions = ref([])
const greetingNo = ref(''), personId = ref(null), resourceCode = ref(''), savedActionIds = ref([]), nameCandidates = ref([])
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const empty = () => ({ id: newDevelopmentId(), revision: 0, platform_id: '', work_date: props.options.default_date || previousWorkday(), owner_id: props.options.user_id, full_name: '', account_id: null, friend_accounts: [], phone: '', wechat: '', xiaohongshu: '', language_ids: [], follow_up: '', follow_ups: [], remarks: '', actions: [], capabilities: [], link_person_id: null, duplicate_note: '' })
const form = reactive(empty())
const recordCandidates = ref([]), recordTotal = ref(0), recordPage = ref(1), recordChecking = ref(false), recordCheckFailed = ref(false), recordPopover = ref(false)
let recordTimer, recordController, recordSequence = 0, recordQueryKey = ''
const duplicateDate = value => value ? new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString('zh-CN') : '-'
function resetRecordCheck() {
  clearTimeout(recordTimer); recordController?.abort(); recordSequence++
  recordQueryKey = ''; recordChecking.value = false; recordCheckFailed.value = false
  recordCandidates.value = []; recordTotal.value = 0; recordPage.value = 1; recordPopover.value = false
}
async function checkRecordName(page = 1) {
  clearTimeout(recordTimer)
  const name = form.full_name.trim()
  if (!visible.value || form.revision || quickMode.value || !name) return
  const key = `${name}:${page}`
  if (key === recordQueryKey && !recordCheckFailed.value) return
  recordController?.abort()
  const controller = new AbortController(), seq = ++recordSequence
  recordController = controller; recordQueryKey = key; recordChecking.value = true; recordCheckFailed.value = false
  try {
    const result = await api.recordDuplicates({ full_name: name, skip: (page - 1) * 20, limit: 20 }, controller.signal)
    if (seq !== recordSequence) return
    recordCandidates.value = result.items; recordTotal.value = result.total; recordPage.value = page
  } catch (error) {
    if (seq === recordSequence && !controller.signal.aborted) { recordCheckFailed.value = true; recordQueryKey = '' }
  } finally { if (seq === recordSequence) recordChecking.value = false }
}
watch(() => [visible.value, form.revision, quickMode.value, form.full_name], () => {
  // 姓名改变即清除旧候选；新增录入的提示不参与人才入库校验。
  resetRecordCheck()
  if (visible.value && !form.revision && !quickMode.value && form.full_name.trim()) recordTimer = setTimeout(() => checkRecordName(), 400)
}, { flush: 'sync' })
onBeforeUnmount(resetRecordCheck)
const platforms = computed(() => props.options.options.filter(o => o.kind === 'platform'))
const accounts = computed(() => props.options.options.filter(o => o.kind === 'account'))
const needsEnrollment = computed(() => !personId.value && hasNewPrivateEntry(form.actions, originalActions.value))
const capabilityOptions = [{ value: 'written_translation', label: '笔译' }, { value: 'interpretation', label: '口译' }, { value: 'annotation', label: '标注' }, { value: 'recruitment', label: '全职' }]
const required = message => [{ required: true, message, trigger: 'change' }]
const rules = computed(() => ({ platform_id: required('请选择开拓平台'), work_date: required('请选择日期'), owner_id: required('请选择开拓人员'), full_name: required('请填写资源姓名'), capabilities: needsEnrollment.value && !form.link_person_id ? [{ type: 'array', required: true, min: 1, message: '请选择至少一个专业分类', trigger: 'change' }] : [] }))
function payload() {
  const { follow_up, ...record } = form
  return { ...record, account_id: form.account_id || null, actions: form.actions.map(a => ({ id: a.id, channel: a.channel, status: a.status, action_date: a.action_date, operator_id: a.operator_id, account_id: a.account_id || null })) }
}
let checkSequence = 0
async function checkName() {
  if (!form.full_name.trim() || !form.platform_id) return
  const seq = ++checkSequence; checking.value = true
  try { const result = await api.duplicates(payload()); if (seq === checkSequence) nameCandidates.value = result.items }
  catch (e) { if (seq === checkSequence) ElMessage.error(e.message) }
  finally { if (seq === checkSequence) checking.value = false }
}
function addAction(channel = 'wechat', quick = false) { form.actions.push({ id: newDevelopmentId(), channel, status: quick || isGroupChannel(channel) ? defaultProgressStatus(channel) : '一次请求', action_date: isGroupChannel(channel) ? developmentDateRange('month')[1] : dateText(new Date()), operator_id: props.options.user_id, account_id: form.account_id }) }
function changeActionChannel(action) {
  action.status = defaultProgressStatus(action.channel)
  if (isGroupChannel(action.channel) && !savedActionIds.value.includes(action.id)) { action.operator_id = props.options.user_id; action.action_date = developmentDateRange('month')[1] }
}
function addFollowUp() { form.follow_ups.push({ id: newDevelopmentId(), content: '' }) }
async function reloadWithDrafts() {
  const drafts = form.follow_ups.map(entry => ({ ...entry }))
  const channel = followUpMode.value ? 'follow_up' : undefined
  try {
    await open({ id: form.id }, channel)
    // 已保存的同 UUID 草稿说明上次响应丢失，不再重复提交。
    form.follow_ups = drafts.filter(entry => !followUpHistory.value.some(saved => saved.id === entry.id && saved.content === entry.content.trim()))
  } catch (error) { ElMessage.error(error.message) }
}
async function open(row, channel, status) {
  const data = row ? await api.detail(row.id) : null
  Object.assign(form, empty()); nameCandidates.value = []; clearFieldSearch(); checkSequence++
  if (!data) Object.assign(form, readBatch())
  if (data) for (const key of Object.keys(form)) if (key !== 'follow_ups' && key in data) form[key] = data[key]
  followUpHistory.value = data?.follow_ups || []; versionConflict.value = false
  historicalOnly.value = Boolean(data?.historical_only)
  greetingNo.value = data?.greeting_no || ''; personId.value = data?.person_id || null; resourceCode.value = data?.resource_code || ''
  originalActions.value = form.actions.map(a => ({ id: a.id, channel: a.channel, status: a.status })); savedActionIds.value = form.actions.map(a => a.id); quickMode.value = Boolean(channel)
  followUpMode.value = channel === 'follow_up'
  if (followUpMode.value) addFollowUp()
  else if (channel) { addAction(channel, true); if (status) form.actions.at(-1).status = status }
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
    const saved = await api.save(payload())
    if (!form.revision) {
      try { sessionStorage.setItem(batchKey(), JSON.stringify({ user_id: props.options.user_id, day: dateText(new Date()), batch: continueDevelopmentValues(form) })) } catch { /* 浏览器禁用存储时不影响保存。 */ }
    }
    emit('saved'); ElMessage.success(saved.person_id ? (personId.value ? '跟进已保存 · 已关联人才：' : '已入人才总库 · ') + (saved.resource_code || '已关联档案') : '资源开拓已保存')
    if (continueAdding) {
      const retained = continueDevelopmentValues(form)
      await open(); Object.assign(form, retained)
      await nextTick()
      formRef.value?.clearValidate()
      await locateDialogFieldByLabel('资源姓名')
      formRef.value?.clearValidate()
    } else visible.value = false
  } catch (e) {
    if (e.response?.status === 409) versionConflict.value = true
    await formRef.value?.applyServerErrors(e)
    if (e.rawDetail?.duplicates) { nameCandidates.value = e.rawDetail.duplicates; await locateDialogFieldByLabel('关联已有档案') }
    ElMessage.error(e.message)
  } finally { saving.value = false }
}
defineExpose({ open })
</script>

<style>
.record-name-check{width:100%;font-size:12px;line-height:1.6;margin-top:4px;overflow-wrap:anywhere}
.record-name-check .el-button{margin-left:8px}.record-name-warning{color:var(--el-color-warning-dark-2)}
.record-name-duplicates-popover{max-width:calc(100vw - 32px);box-sizing:border-box}
.record-name-duplicates-body{max-height:min(560px,calc(100vh - 200px));overflow-y:auto}
.record-name-duplicate-item{margin-bottom:12px}.record-name-duplicate-item .el-descriptions__table{table-layout:fixed;width:100%}
.record-name-duplicate-item .el-descriptions__cell{overflow-wrap:anywhere;white-space:pre-wrap}
.record-name-duplicates-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px;font-size:12px;color:var(--el-text-color-secondary)}
</style>
