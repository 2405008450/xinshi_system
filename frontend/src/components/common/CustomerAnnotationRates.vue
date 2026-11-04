<template>
  <section class="customer-annotation-rates" v-loading="loading">
    <div class="rate-toolbar">
      <el-button v-if="canWrite" type="primary" :disabled="!clientId || loading || saving" @click="openEditor()">新增客户单价</el-button>
      <small v-if="!clientId">请先保存客户，再维护标注单价</small>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link type="primary" @click="load">重新加载</el-button>
    </el-alert>
    <el-table v-if="clientId" :data="items" border size="small" row-key="id" max-height="360" empty-text="暂无客户标注单价">
      <el-table-column label="标注类型" min-width="150"><template #default="{ row }">{{ label(projectTypes, row.project_type) }}</template></el-table-column>
      <el-table-column label="不含税单价" min-width="140"><template #default="{row}">{{row.tax_prices?.unit_price_excl_tax ?? '-'}}</template></el-table-column><el-table-column label="含税单价" min-width="140"><template #default="{row}">{{row.tax_prices?.unit_price_incl_tax ?? '-'}}</template></el-table-column>
      <el-table-column label="货币" min-width="130"><template #default="{ row }">{{ label(currencies, row.currency) }}</template></el-table-column>
      <el-table-column label="单位" min-width="110"><template #default="{ row }">{{ label(units, row.unit) }}</template></el-table-column>
      <el-table-column v-if="canWrite" label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="saving" @click="openEditor(row)">编辑</el-button>
          <el-button link type="danger" :disabled="saving" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <CustomerRateDifferences v-if="clientId && canReadProjects" module="annotation" :client-id="clientId" :revision="revision" :disabled="saving || visible" @saved="load" />

    <DraggableFormDialog v-model="visible" append-to-body class="customer-annotation-rate-dialog" width="min(680px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="beforeClose" @closed="clearFieldSearch">
      <template #header>
        <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="draft.id ? '编辑客户标注单价' : '新增客户标注单价'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
      </template>
      <div ref="body">
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
        <AppForm ref="form" :model="draft" :rules="rules" :disabled="saving" label-position="top">
          <el-form-item label="标注类型" prop="project_type">
            <el-select v-model="draft.project_type" placeholder="请选择标注类型" filterable clearable>
              <el-option v-for="option in projectTypes" :key="option.value" v-bind="option" />
            </el-select>
          </el-form-item>
          <p v-if="draft.amount!=null && !taxPriceSummary(draft.taxPrices)">原单价（税口径未确认）：{{draft.amount}}</p>
          <TaxPriceFields v-model="draft.taxPrices" prefix="taxPrices" :show-totals="false" @change="value=>draft.amount=taxUnitAmount(value,draft.amount)" />
          <el-form-item label="货币" prop="currency">
            <el-select v-model="draft.currency" placeholder="请选择货币"><el-option v-for="option in currencies" :key="option.value" v-bind="option" /></el-select>
          </el-form-item>
          <el-form-item label="单位" prop="unit">
            <el-select v-model="draft.unit" placeholder="请选择计价单位" filterable clearable><el-option v-for="option in units" :key="option.value" v-bind="option" /></el-select>
          </el-form-item>
        </AppForm>
      </div>
      <template #footer>
        <el-button :disabled="saving" @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存单价</el-button>
      </template>
    </DraggableFormDialog>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppForm from './AppForm.vue'
import TaxPriceFields from './TaxPriceFields.vue'
import {taxPriceForm,taxPricePayload,taxUnitAmount,taxPriceSummary} from '@/utils/taxPrices'
import CustomerRateDifferences from './CustomerRateDifferences.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { annotationProjectTypeOptions as projectTypes } from '@/utils/annotationCatalog'
import { settlementCurrencyOptions as currencies, settlementUnitOptions as units, settlementLabel as label } from '@/utils/talentSettlement'
import { hasPermission } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { getCustomerAnnotationRates, createCustomerAnnotationRate, updateCustomerAnnotationRate, deleteCustomerAnnotationRate } from '@/api/customerAnnotationRates'

const props = defineProps({ clientId: { type: [String, Number], default: '' }, canWrite: Boolean })
const canReadProjects = hasPermission('projects:read') || hasPermission('projects:write')
const items = ref([]), loading = ref(false), saving = ref(false), visible = ref(false)
const revision = ref(0)
const error = ref(''), saveError = ref(''), form = ref(), body = ref()
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(body)
const empty = () => ({ id: '', project_type: '', amount: null, taxPrices: taxPriceForm(), currency: 'CNY', unit: '', revision: 1 })
const draft = reactive(empty())
const rules = {
  project_type: [{ required: true, message: '请选择标注类型', trigger: 'change' }],
  amount: [{ required: true, type: 'number', min: 0.000001, message: '请输入大于零的单价金额', trigger: 'blur' }],
  currency: [{ required: true, message: '请选择货币', trigger: 'change' }],
  unit: [{ required: true, message: '请选择计价单位', trigger: 'change' }],
}
let controller, requestId = 0, editorClientId = '', alive = true

async function load() {
  controller?.abort()
  const current = ++requestId
  error.value = ''; items.value = []; loading.value = false
  if (!props.clientId) return
  controller = new AbortController(); loading.value = true
  try {
    const data = await getCustomerAnnotationRates(props.clientId, { signal: controller.signal })
    if (current === requestId) items.value = data.items || []
  } catch (e) {
    if (current === requestId && e?.code !== 'ERR_CANCELED') error.value = getLocalizedErrorMessage(e, '客户标注单价加载失败')
  } finally {
    if (current === requestId) loading.value = false
  }
}

async function openEditor(row) {
  if (!props.canWrite || !props.clientId || saving.value) return
  editorClientId = props.clientId
  Object.assign(draft, empty(), row ? { ...row, amount: Number(row.amount), taxPrices: taxPriceForm(row.tax_prices) } : {})
  saveError.value = ''; clearFieldSearch(); visible.value = true
  await nextTick(); form.value?.clearValidate()
}

function beforeClose(done) { if (!saving.value) done() }

async function save() {
  if (!props.canWrite || saving.value || !editorClientId || editorClientId !== props.clientId) return
  if (!await form.value?.validate().catch(() => false)) return
  if (draft.amount == null) { saveError.value='请填写不含税单价或含税单价'; await locateDialogFieldByLabel('不含税单价'); return }
  const target = editorClientId
  saving.value = true; saveError.value = ''
  try {
    const payload = { project_type: draft.project_type, amount: String(draft.amount), tax_prices: taxPricePayload(draft.taxPrices), currency: draft.currency, unit: draft.unit }
    if (draft.id) await updateCustomerAnnotationRate(target, draft.id, { ...payload, revision: draft.revision })
    else await createCustomerAnnotationRate(target, payload)
    if (!alive || props.clientId !== target) return
    visible.value = false; revision.value++; ElMessage.success('客户标注单价已保存'); await load()
  } catch (e) {
    if (alive && props.clientId === target) {
      saveError.value = getLocalizedErrorMessage(e, '保存单价失败')
      await form.value?.applyServerErrors(e)
    }
  } finally { if (alive) saving.value = false }
}

async function remove(row) {
  if (!props.canWrite || saving.value) return
  const target = props.clientId
  try { await ElMessageBox.confirm(`确定删除“${label(projectTypes, row.project_type)}”的这条客户单价吗？`, '删除客户单价', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }) } catch { return }
  if (!alive || target !== props.clientId) return
  saving.value = true
  try {
    await deleteCustomerAnnotationRate(target, row)
    if (alive && target === props.clientId) { revision.value++; ElMessage.success('客户单价已删除'); await load() }
  } catch (e) { if (alive) ElMessage.error(getLocalizedErrorMessage(e, '删除单价失败')) }
  finally { if (alive) saving.value = false }
}

watch(() => props.clientId, () => { visible.value = false; load() }, { immediate: true })
onBeforeUnmount(() => { alive = false; ++requestId; controller?.abort() })
</script>

<style scoped>
.rate-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.rate-toolbar small { color: var(--el-text-color-secondary); }
.customer-annotation-rates > .el-alert { margin-bottom: 12px; }
:global(.customer-annotation-rate-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.customer-annotation-rate-dialog .el-dialog__header),
:global(.customer-annotation-rate-dialog .el-dialog__footer) { flex: none; }
:global(.customer-annotation-rate-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.customer-annotation-rate-dialog .el-dialog__footer) { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); }
:global(.customer-annotation-rate-dialog .el-select),
:global(.customer-annotation-rate-dialog .el-input-number) { width: 100%; }
</style>
