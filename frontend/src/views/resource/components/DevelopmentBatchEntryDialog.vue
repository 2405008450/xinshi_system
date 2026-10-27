<template>
  <DraggableFormDialog v-model="visible" width="min(1600px, calc(100vw - 32px))" top="5vh" append-to-body class="development-dialog development-batch-dialog" destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" class="batch-entry-header" title="新增资源开拓 · 表格录入" placeholder="搜索字段或行号" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch"><template #actions><el-button :disabled="saving" @click="languageDialogRef.open()">增加语言/方言</el-button><TableColumnSettings v-model="selectedFields" :settings-key="fieldSettingsKey" :columns="batchFields" :column-count="2" title="录入字段" hint="勾选显示字段；隐藏不会清空已填内容。保存时自动展开缺失的必填项。" @reset="resetFields" /></template></DialogFieldSearchHeader></template>
    <div ref="bodyRef">
      <p class="muted">每行一位资源；方向键或 Tab 切换单元格，下拉框保留原有按键操作。点击该行右侧“复制”，在弹窗中选择要新增的行数；可删除任意未保存行。</p>
      <AppForm ref="formRef" :model="model" :disabled="saving" label-position="top" @submit.prevent>
        <div class="batch-grid-scroll">
          <table class="batch-grid" @keydown="handleTableArrowNavigation"><thead ref="columnHeaderRef"><tr><th class="batch-index">序号</th><th v-for="field in visibleFields" :key="field.key" :data-column-key="field.key" class="batch-field-header" title="拖动表头调整字段顺序" :style="{ minWidth: `${field.width}px` }">{{ field.label }}</th><th class="batch-row-actions">操作</th></tr></thead>
            <tbody><tr v-for="(row, index) in model.rows" :key="row.id" data-dialog-field-search-group :class="{ 'batch-row-error': row._error }">
              <td class="batch-index"><strong data-dialog-field-search-group-title>第 {{ index + 1 }} 行</strong></td>
              <td v-for="field in visibleFields" :key="field.key">
                <el-form-item v-if="field.type === 'extra'" :label="field.label" :prop="['rows',String(index),'custom_fields',field.customId]"><el-input v-model="row.custom_fields[field.customId]" maxlength="20000" /></el-form-item>
                <template v-else-if="field.type === 'custom'"><DevelopmentResourceAccounts v-model="row.custom_accounts" :prop-prefix="`rows.${index}.custom_accounts`" :disabled="saving" /></template>
                <template v-else-if="field.type === 'statuses'">
                  <details class="batch-status-details"><summary>填写跟进进展（{{ Object.values(row._statuses).filter(Boolean).length }}）</summary>
                  <el-form-item v-for="(label, channel) in progressChannels" :key="channel" :label="label" :prop="`rows.${index}._statuses.${channel}`">
                    <el-select v-model="row._statuses[channel]" clearable filterable :allow-create="!isGroupChannel(channel)" default-first-option placeholder="不新增跟进"><el-option v-for="status in progressStatuses(channel)" :key="status" :label="status" :value="status" /></el-select>
                  </el-form-item>
                  </details>
                </template>
                <template v-else-if="field.type === 'enrollment'">
                  <template v-if="entryNeedsEnrollment(row)">
                    <el-form-item label="专业分类" :prop="`rows.${index}.capabilities`" :rules="row.link_person_id ? [] : [{ type: 'array', required: true, min: 1, message: '请选择至少一项专业分类', trigger: 'change' }]"><el-select v-model="row.capabilities" multiple><el-option v-for="item in capabilityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
                    <el-button :disabled="saving" @click="checkDuplicates(row)">检查重复人才</el-button>
                    <template v-if="row._candidates.length">
                      <el-form-item label="关联已有档案" :prop="`rows.${index}.link_person_id`"><el-select v-model="row.link_person_id" clearable placeholder="选择已有档案"><el-option v-for="person in row._candidates" :key="person.id" :label="`${person.full_name} / ${person.resource_code || '暂无编号'}（${person.match_fields.map(key => ({ name: '同名', phone: '同手机号', wechat: '同微信号' })[key]).join('、')}）`" :value="person.id" /></el-select></el-form-item>
                      <el-form-item v-if="!row.link_person_id" label="不是同一人的说明" :prop="`rows.${index}.duplicate_note`"><el-input v-model="row.duplicate_note" type="textarea" maxlength="2000" placeholder="仅同名时可说明后另建；手机号或微信号冲突需先处理" /></el-form-item>
                    </template>
                  </template><span v-else class="muted">确认已添加微信/企微或已进群时填写</span>
                </template>
                <el-form-item v-else :label="field.label" :prop="`rows.${index}.${field.key}`" :rules="field.required ? [{ required: true, whitespace: true, message: `请填写${field.label}`, trigger: 'change' }] : []">
                  <el-select v-if="field.type === 'platform'" v-model="row.platform_id" filterable><el-option-group v-for="group in categoryOptions" :key="group.value" :label="group.label"><el-option v-for="platform in platforms.filter(item => item.category === group.value)" :key="platform.id" :label="platform.name" :value="platform.id" /></el-option-group></el-select>
                  <el-date-picker v-else-if="field.type === 'date'" v-model="row.work_date" value-format="YYYY-MM-DD" :clearable="false" />
                  <el-select v-else-if="field.type === 'owner'" v-model="row.owner_id" filterable :disabled="saving || !options.can_delegate"><el-option v-for="user in options.users" :key="user.id" :label="user.name" :value="user.id" /></el-select>
                  <el-select v-else-if="field.type === 'account'" v-model="row.account_id" clearable filterable @clear="row.account_id = null"><el-option v-for="account in accounts" :key="account.id" :label="account.name" :value="account.id" /></el-select>
                  <CompanyWechatAccountSelect v-else-if="field.type === 'friends'" v-model="row.friend_accounts" />
                  <el-select v-else-if="field.type === 'languages'" v-model="row.language_ids" multiple filterable><el-option v-for="language in options.languages" :key="language.id" :label="`${language.label}${language.language_type === 'dialect' ? '（方言）' : ''}`" :value="language.id" /></el-select>
                  <el-input v-else v-model="row[field.key]" :type="field.type === 'textarea' ? 'textarea' : 'text'" :maxlength="field.max" :autosize="field.type === 'textarea' ? { minRows: 1, maxRows: 3 } : undefined" />
                </el-form-item>
              </td>
              <td class="batch-row-actions"><el-button link type="primary" :disabled="saving || model.rows.length >= 100" @click="duplicateRow(index)">复制</el-button><el-button link type="danger" :disabled="saving" @click="removeRow(index)">删除</el-button><p v-if="row._error" role="alert" class="batch-error">{{ row._error }}</p></td>
            </tr><tr v-if="!model.rows.length"><td :colspan="visibleFields.length + 2">暂无记录，<el-button link type="primary" :disabled="saving" @click="addRow">新增一行</el-button>开始填写。</td></tr></tbody>
          </table>
        </div>
      </AppForm>
    </div>
    <template #footer><span class="muted">逐行保存；成功行移出，失败行保留内容供修改。</span><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :disabled="!model.rows.length" :loading="saving" @click="save">保存全部</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="copyVisible" :title="`复制第 ${copySourceIndex + 1} 行`" width="min(420px, calc(100vw - 32px))" append-to-body destroy-on-close :close-on-click-modal="false">
    <AppForm ref="copyFormRef" :model="copyForm" label-position="top" @submit.prevent="confirmCopy">
      <el-form-item label="新增行数" prop="count" :rules="copyRules"><el-input-number v-model="copyForm.count" :min="1" :max="copyLimit" :precision="0" step-strictly aria-label="新增行数" /></el-form-item>
      <p class="muted">以选中行的全部填写内容为模板，新复制 {{ copyForm.count || 0 }} 行，原行保留。本次最多可新增 {{ copyLimit }} 行。</p>
    </AppForm>
    <template #footer><el-button :disabled="copying" @click="copyVisible = false">取消</el-button><el-button type="primary" :loading="copying" :disabled="copySourceIndex < 0 || copyLimit < 1" @click="confirmCopy">确定复制</el-button></template>
  </DraggableFormDialog>
  <DevelopmentLanguageDialog ref="languageDialogRef" @created="language => emit('language-created', language)" />
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import CompanyWechatAccountSelect from '@/components/common/CompanyWechatAccountSelect.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { handleTableArrowNavigation } from '@/utils/tableArrowNavigation'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions, progressChannels, progressStatuses, isGroupChannel, restoreDevelopmentBatch } from '@/utils/resourceDevelopment'
import { entryFields, newEntryRow, entryPayload, entryNeedsEnrollment, capabilityOptions } from '@/utils/developmentBatchEntry'
import DevelopmentResourceAccounts from './DevelopmentResourceAccounts.vue'
import DevelopmentLanguageDialog from './DevelopmentLanguageDialog.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumnOrder } from '@/composables/useTableColumnOrder'
import { bindColumnDrag } from '@/utils/columnDragGesture'
import { moveColumn } from '@/utils/tableColumnOrder'

const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved', 'language-created'])
const batchFields = computed(() => {
  const definitions = new Map((props.options.options || []).filter(item => item.kind === 'custom_field').map(item => [item.id, item]))
  return [...entryFields, ...[...definitions.values()].map(item => ({key:`custom_field:${item.id}`,label:item.name,width:220,type:'extra',customId:item.id}))]
})
const selectedFields = ref([])
const fieldSettingsKey = 'resource-development-batch-entry'
const { orderedColumns, order: columnOrder, setOrder: setColumnOrder } = useTableColumnOrder(fieldSettingsKey, 'main', batchFields)
const columnHeaderRef = ref(null)
let unbindColumnDrag
watch(columnHeaderRef, root => {
  unbindColumnDrag?.()
  if (!root) return
  unbindColumnDrag = bindColumnDrag(root, element => saving.value ? null : element?.closest('[data-column-key]')?.dataset.columnKey ?? null,
    (from, to) => setColumnOrder(moveColumn(columnOrder.value, from, to)))
}, { flush: 'post' })
onBeforeUnmount(() => unbindColumnDrag?.())
const visibleFields = computed(() => orderedColumns.value.filter(field => selectedFields.value.includes(field.key)))
const selectionStorageKey = () => `table-columns:${fieldSettingsKey}:${props.options.user_id}`
function resetFields() { selectedFields.value = batchFields.value.map(field => field.key) }
function readFields() {
  try {
    const raw = localStorage.getItem(selectionStorageKey())
    if (raw === null) return resetFields()
    const keys = JSON.parse(raw)
    if (!Array.isArray(keys)) throw new Error('invalid settings')
    selectedFields.value = keys.filter(key => batchFields.value.some(field => field.key === key))
  } catch { resetFields() }
}
watch(selectedFields, keys => {
  if (!props.options.user_id) return
  try { localStorage.setItem(selectionStorageKey(), JSON.stringify(keys)) } catch { /* 存储不可用时仍可录入。 */ }
}, { deep: true })
const visible = ref(false), saving = ref(false), bodyRef = ref(null), formRef = ref(null), languageDialogRef = ref(null)
const model = reactive({ rows: [] })
const copyVisible = ref(false), copying = ref(false), copySourceId = ref(null), copyFormRef = ref(null), copyForm = reactive({ count: 1 })
const copySourceIndex = computed(() => model.rows.findIndex(row => row.id === copySourceId.value))
const copyLimit = computed(() => Math.max(0, 100 - model.rows.length))
const copyRules = [{ validator: (_rule, value, done) => done(Number.isInteger(value) && value >= 1 && value <= copyLimit.value ? undefined : new Error(`请输入 1～${copyLimit.value} 的整数`)), trigger: 'change' }]
watch(visible, value => { if (!value) copyVisible.value = false })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const platforms = computed(() => props.options.options.filter(item => item.kind === 'platform'))
const accounts = computed(() => props.options.options.filter(item => item.kind === 'account'))
function beforeClose(done) { if (!saving.value) done() }
async function open() {
  if (saving.value) return
  readFields()
  let batch = {}
  try { batch = restoreDevelopmentBatch(JSON.parse(sessionStorage.getItem(`resource-development:entry-batch:${props.options.user_id}`) || 'null'), props.options) } catch { /* 禁用存储不阻断录入。 */ }
  delete batch.work_date
  model.rows = [newEntryRow(props.options, batch)]
  copyVisible.value = false; clearFieldSearch(); visible.value = true
  await nextTick(); formRef.value?.clearValidate()
}
function addRow() { if (!saving.value && model.rows.length < 100) model.rows.push(newEntryRow(props.options)) }
async function removeRow(index) { model.rows.splice(index, 1); await nextTick(); formRef.value?.clearValidate() }
async function duplicateRow(index) {
  if (saving.value || !model.rows[index] || copyLimit.value < 1) return
  copySourceId.value = model.rows[index].id; copyForm.count = 1; copyVisible.value = true
  await nextTick(); copyFormRef.value?.clearValidate()
}
async function confirmCopy() {
  if (copying.value) return
  copying.value = true
  try {
  if (!await copyFormRef.value?.validate().catch(() => false)) return
  const index = copySourceIndex.value
  if (index < 0 || saving.value) return
  const template = model.rows[index]
  model.rows.splice(index + 1, 0, ...Array.from({ length: copyForm.count }, () => newEntryRow(props.options, template)))
  copyVisible.value = false
  await nextTick(); formRef.value?.clearValidate()
  } finally { copying.value = false }
}
async function checkDuplicates(row) {
  try { row._candidates = (await api.duplicates(entryPayload(row))).items }
  catch (error) { ElMessage.error(error.message || '请先填写平台、日期、人员和姓名') }
}
async function save() {
  if (saving.value || !model.rows.length) return
  saving.value = true
  const savedIds = new Set()
  try {
    // 隐藏不清空填写内容；保存时展开缺失的必填字段再统一校验、定位。
    const needed = batchFields.value.filter(field => field.required && model.rows.some(row => !String(row[field.key] || '').trim())).map(field => field.key)
    if (model.rows.some(row => entryNeedsEnrollment(row) && !row.link_person_id && !row.capabilities.length)) needed.push('capabilities')
    selectedFields.value = [...new Set([...selectedFields.value, ...needed])]
    await nextTick()
    if (!await formRef.value.validate().catch(() => false)) return
    for (const row of model.rows) {
      row._error = ''
      try {
        const payload = entryPayload(row)
        if (entryNeedsEnrollment(row)) {
          row._candidates = (await api.duplicates(payload)).items
          if (row._candidates.length && !row.link_person_id && (row._candidates.some(person => person.match_fields.some(field => ['phone', 'wechat'].includes(field))) || !row.duplicate_note.trim())) throw new Error('发现疑似重复人才，请关联已有档案或填写不是同一人的说明')
        }
        await api.save(payload)
        savedIds.add(row.id)
      } catch (error) {
        row._error = error.message || '保存失败，请修改后重试'
        if (error.rawDetail?.duplicates) row._candidates = error.rawDetail.duplicates
      }
    }
    model.rows = model.rows.filter(row => !savedIds.has(row.id))
    if (savedIds.size) emit('saved')
    if (model.rows.length) {
      ElMessage.warning(`成功 ${savedIds.size} 行，失败 ${model.rows.length} 行，请查看各行提示`)
      await nextTick(); await locateDialogFieldByLabel('资源姓名')
    } else {
      visible.value = false; ElMessage.success(`已保存 ${savedIds.size} 行资源开拓记录`)
    }
  } finally { saving.value = false }
}
defineExpose({ open })
</script>

<style scoped>
.batch-field-header { cursor: grab; touch-action: none; }
.batch-field-header:active { cursor: grabbing; }
.batch-entry-header :deep(.dialog-field-search-header__heading){flex:1 1 auto;min-width:0}
.batch-entry-header :deep(.dialog-field-search-header__extra){margin-left:auto;margin-right:auto}
@media(max-width:768px){.batch-entry-header :deep(.dialog-field-search-header__extra){margin-left:0;margin-right:0}}
.batch-grid-scroll{overflow:auto;max-height:60vh;border:1px solid var(--el-border-color)}
.batch-grid{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:13px}
.batch-grid th,.batch-grid td{padding:6px 8px;vertical-align:top;border-right:1px solid var(--el-border-color-lighter);border-bottom:1px solid var(--el-border-color-lighter);background:var(--el-bg-color)}
.batch-grid th{position:sticky;top:0;z-index:3;background:var(--el-fill-color-light);text-align:left}
.batch-grid .batch-index{position:sticky;left:0;min-width:70px;z-index:2}
.batch-grid th.batch-index{z-index:4}
.batch-grid .batch-row-actions{position:sticky;right:0;min-width:150px;max-width:200px;z-index:2;box-shadow:-3px 0 5px #00000008}
.batch-grid th.batch-row-actions{z-index:4}
.batch-grid :deep(.el-form-item){margin-bottom:2px}
.batch-grid :deep(.el-form-item__label){font-size:12px;line-height:16px;margin-bottom:3px;padding:0}
.batch-grid :deep(.app-screenshot-tools){display:none}
.batch-grid :deep(.app-screenshot-input:focus-within .app-screenshot-tools){display:flex}
.batch-grid .muted{font-size:12px;line-height:18px}
.batch-grid :deep(.el-select),.batch-grid :deep(.el-date-editor.el-input){width:100%}
.batch-error{color:var(--el-color-danger);white-space:pre-wrap;overflow-wrap:anywhere;max-width:180px}
.batch-status-details>summary{cursor:pointer;color:var(--el-color-primary);margin-bottom:10px}
.batch-row-error>td{background:var(--el-color-danger-light-9)}
</style>
