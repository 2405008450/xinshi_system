<template>
  <DraggableFormDialog v-model="visible" class="annotation-child-create-dialog project-suborder-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="(done) => !saving && done()">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="dialogTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <AppForm ref="formRef" :model="form" label-position="top" :disabled="saving">
        <el-form-item :label="isGrandchild ? '子订单' : '订单'" prop="parentId" :rules="[{ required: true, message: isGrandchild ? '请选择子订单' : '请选择订单', trigger: 'change' }]">
          <ReadonlyField v-if="parent" :model-value="`${parent.orderNo} · ${parent.projectName || ''}`" source="auto" />
          <el-select v-else v-model="form.parentId" remote filterable :remote-method="searchParents" :loading="parentLoading" style="width:100%" @change="selectParent"><el-option v-for="item in parents" :key="item.id" :value="item.id" :label="`${item.orderNo} · ${item.projectName || ''}`" /></el-select>
        </el-form-item>
        <el-alert :title="inheritanceEnabled ? '上级业务信息自动带入，未独立修改的字段持续跟随上级更新；下级修改后保留自己的内容。资料只在创建时复制，聊天、进度历史和账号分配不复制。' : '创建时复制上级业务信息，保存后各子订单独立维护。资料只在创建时复制，聊天、进度历史和账号分配不复制。'" type="info" :closable="false" />
        <el-form-item v-if="!single && !isGrandchild" label="批量选择语种"><el-select v-model="selectedLanguages" multiple filterable style="width:100%"><el-option v-for="language in languages" :key="language.id" :value="language.id" :label="language.label" /></el-select><el-button @click="addSelected">添加到预览</el-button></el-form-item>
        <div v-for="(item,index) in form.items" :key="item.key" class="child-preview-row" data-dialog-field-search-group>
          <div class="child-preview-title"><strong data-dialog-field-search-group-title>{{ isGrandchild ? '三级订单' : '子订单' }} {{ index + 1 }}</strong><el-button v-if="!single" link type="danger" @click="form.items.splice(index,1)">移除</el-button></div>
          <el-row :gutter="16">
            <el-col v-if="isGrandchild" :xs="24" :md="12"><el-form-item label="语种方向"><ReadonlyField :model-value="currentParent?.languageItemsDisplay" source="auto" /></el-form-item></el-col>
            <el-col v-if="isGrandchild" :xs="24" :md="12"><el-form-item label="片区" :prop="['items', String(index), 'areaId']" :rules="required('请选择片区')"><AnnotationAreaSelect v-model="item.areaId" @changed="$emit('areas-changed')" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="任务名称" :prop="['items', String(index), 'projectName']" :rules="required('请输入任务名称')"><el-input v-model="item.projectName" maxlength="500" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="项目类型" :prop="['items', String(index), 'projectTypes']" :rules="required('请选择项目类型')"><el-select v-model="item.projectTypes" multiple style="width:100%"><el-option v-for="type in projectTypes" :key="type.value" :value="type.value" :label="type.label" /></el-select></el-form-item></el-col>
            <el-col v-if="!isGrandchild" :xs="24" :md="12"><el-form-item label="语种" :prop="['items', String(index), 'sourceLanguageId']" :rules="required('请选择语种')"><el-select v-model="item.sourceLanguageId" filterable style="width:100%"><el-option v-for="language in languages" :key="language.id" :value="language.id" :label="language.label" /></el-select></el-form-item></el-col>
            <el-col v-if="!isGrandchild" :xs="24" :md="12"><el-form-item label="目标语种" :prop="['items', String(index), 'targetLanguageId']" :rules="[{ validator: (_rule,value,callback) => callback(value && value === item.sourceLanguageId ? new Error('两个语种不能相同') : undefined), trigger: 'change' }]"><el-select v-model="item.targetLanguageId" filterable clearable placeholder="单语种任务留空" style="width:100%"><el-option v-for="language in languages" :key="language.id" :value="language.id" :label="language.label" /></el-select></el-form-item></el-col>
            <el-col v-if="!isGrandchild" :xs="24" :md="12"><el-form-item label="复制来源方向"><el-select v-model="item.copySourceLanguageItemId" style="width:100%" @change="item.regions=copyLanguageRegions(sourceItem(item)?.regions)"><el-option v-for="direction in currentParent?.languageItems || []" :key="direction.id" :value="direction.id" :label="direction.display || direction.sourceLanguageLabel" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="项目经理"><el-select v-model="item.managerIds" multiple filterable style="width:100%"><el-option v-for="manager in managers" :key="manager.id" :value="manager.id" :label="manager.fullName || manager.full_name || manager.username" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="提交时间"><el-date-picker v-model="item.taskSubmittedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" placeholder="留空表示待定" /></el-form-item></el-col>
          </el-row>
          <AnnotationLanguageRegionsEditor v-if="languageRegionsEnabled && item.sourceLanguageId" v-model="item.regions" :label="languages.find(language => language.id === item.sourceLanguageId)?.label || '语种'" />
          <p v-if="languageRegionsEnabled" class="region-copy-note">地区要求仅在创建时带入，之后由各订单独立维护。</p>
          <el-form-item label="具体任务" :prop="['items', String(index), 'taskDescription']" :rules="required('请输入具体任务')"><el-input v-model="item.taskDescription" type="textarea" :rows="2" /></el-form-item>
          <el-descriptions :column="2" border size="small" class="child-copy-summary">
            <el-descriptions-item label="客户">{{ currentParent?.clientShortName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="需求量">{{ currentParent?.potentialDemand || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">沿用上级状态，独立修改后保留</el-descriptions-item>
            <el-descriptions-item label="复制的价格/人员">{{ sourcePrices(item).length }} 条价格 / {{ sourcePeople(item).length }} 条人员安排</el-descriptions-item>
            <el-descriptions-item label="资料与其他信息" :span="2">项目、报价、合同资料及路径、优先级、派发时间、咨询确认时间均带入；创建后可通过“编辑”逐项调整。</el-descriptions-item>
          </el-descriptions>
          <AnnotationCustomFieldInputs ref="customEditors" :fields="customFields" :values="item.customValues" validate-values :model-path="['items', String(index), 'customValues']" />
        </div>
        <el-button v-if="!single" @click="addRow()">添加任务行</el-button>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </AppForm>
    </div>
    <template #footer><span class="child-preview-count">预览共 {{ form.items.length }} 个{{ isGrandchild ? '三级订单' : '子订单' }}</span><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!form.items.length || !form.parentId" @click="save">确认创建</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { createIdempotencyKey } from '@/utils/idempotency'
import { ElMessage } from 'element-plus'
import { getAnnotationProject, getAnnotationProjectPage, createAnnotationChildren } from '@/api/annotationProjects'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AnnotationLanguageRegionsEditor from './AnnotationLanguageRegionsEditor.vue'
import { copyLanguageRegions, normalizeLanguageRegions } from '@/utils/annotationLanguageRegions'
import AnnotationAreaSelect from './AnnotationAreaSelect.vue'
import AnnotationCustomFieldInputs from './AnnotationCustomFieldInputs.vue'

const props = defineProps({ modelValue: Boolean, parent: Object, languageRegionsEnabled: { type: Boolean, default: true }, inheritanceEnabled: { type: Boolean, default: true }, grandchild: Boolean, single: Boolean, split: Boolean, languages: { type: Array, default: () => [] }, projectTypes: { type: Array, default: () => [] }, managers: { type: Array, default: () => [] }, customFields: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue', 'created', 'areas-changed'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const bodyRef = ref(null), formRef = ref(null), selectedLanguages = ref([]), parents = ref([]), currentParent = ref(null), saving = ref(false), parentLoading = ref(false), error = ref('')
const form = reactive({ parentId: '', items: [] })
const customEditors = ref([])
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const isGrandchild=computed(()=>Boolean(currentParent.value?.parentProjectId)||props.grandchild)
const dialogTitle=computed(()=>props.split?'分拆标注子订单':`${props.single?'新增':'批量新增'}标注${isGrandchild.value?'三级':'子'}订单`)
const required = message => [{ required: true, message, trigger: ['blur', 'change'] }]
let requestId = 0, controller, parentSelectionId = 0, key = '', signature = ''
const searchParents = async (keyword = '') => {
  controller?.abort(); controller = new AbortController(); const current = ++requestId
  parentLoading.value = true
  try { const page = await getAnnotationProjectPage({ order_scope: props.grandchild ? 'child' : 'parent', keyword, limit: 50 }, { signal: controller.signal }); if (current === requestId) parents.value = page.items }
  catch (failure) { if (failure.code !== 'ERR_CANCELED') error.value = failure.detail || '上级订单加载失败' }
  finally { if (current === requestId) parentLoading.value = false }
}
const clone = value => JSON.parse(JSON.stringify(value ?? {}))
const sourceItem = item => currentParent.value?.languageItems?.find(direction => direction.id === item.copySourceLanguageItemId)
const sourcePrices = item => (currentParent.value?.priceItems || []).filter(price => !price.sourceLanguageId || (price.sourceLanguageId === sourceItem(item)?.sourceLanguageId && (price.targetLanguageId || '') === (sourceItem(item)?.targetLanguageId || '')))
const sourcePeople = item => (currentParent.value?.assignees || []).filter(person => !person.languageItemId || person.languageItemId === item.copySourceLanguageItemId)
const addRow = (languageId = '', targetId = '', sourceId = '') => {
  if (form.items.length >= 100) return ElMessage.warning('每次最多创建 100 个子订单')
  const parent = currentParent.value
  const direction = parent?.languageItems?.find(item => sourceId ? item.id === sourceId : item.sourceLanguageId === languageId && (item.targetLanguageId || '') === targetId) || parent?.languageItems?.[0]
  form.items.push({ areaId:null, key: createIdempotencyKey(), projectName: parent?.projectName || '标注任务', projectTypes: [...(parent?.projectTypes || [])], taskDescription: parent?.taskDescription || '', sourceLanguageId: languageId || direction?.sourceLanguageId || '', targetLanguageId: targetId || (!languageId ? direction?.targetLanguageId || '' : ''), copySourceLanguageItemId: direction?.id || null, regions:copyLanguageRegions(direction?.regions), customValues: clone(parent?.customValues), managerIds: (parent?.roleAssignments || []).filter(item => item.roleCode === 'project_manager').map(item => item.assigneeId).filter(Boolean), taskSubmittedAt: businessDateTimeInputValue(parent?.taskSubmittedAt||null) || '' })
}
const selectParent = async (id) => {
  const current = ++parentSelectionId
  try {
    const detail = await getAnnotationProject(id)
    if (current !== parentSelectionId) return
    currentParent.value = detail
    form.items = []
    if (props.split) { for (const direction of detail.languageItems || []) addRow(direction.sourceLanguageId, direction.targetLanguageId || '', direction.id) }
    else addRow()
  } catch (failure) { error.value = failure.detail || '上级订单详情加载失败' }
}
const addSelected = () => { for (const id of selectedLanguages.value) addRow(id); selectedLanguages.value = [] }
watch(() => props.modelValue, async (open) => {
  if (!open) { ++parentSelectionId; controller?.abort(); await Promise.allSettled(customEditors.value.map(editor => editor.cleanupPending())); return }
  clearFieldSearch(); error.value = ''; selectedLanguages.value = []; key = ''; signature = ''; form.items = []
  form.parentId = props.parent?.id || ''; currentParent.value = props.parent || null
  if (props.parent) await selectParent(props.parent.id)
  else await searchParents()
})
const save = async () => {
  if (saving.value || !await formRef.value?.validate().catch(() => false)) return
  if (!form.items.length) return
  const items = form.items.map(item => ({ areaId:item.areaId||null, projectName: item.projectName.trim(), projectTypes: item.projectTypes, taskDescription: item.taskDescription.trim(), languageItems: [{ sourceLanguageId: item.sourceLanguageId, targetLanguageId: item.targetLanguageId || null, ...(props.languageRegionsEnabled ? {regions:normalizeLanguageRegions(item.regions)} : {}) }], taskSubmittedAt: item.taskSubmittedAt || null, copySourceLanguageItemId: item.copySourceLanguageItemId, expectedParentUpdatedAt: currentParent.value?.updatedAt || null, customValues: item.customValues, roleAssignments: [...(currentParent.value?.roleAssignments || []).filter(role => role.roleCode !== 'project_manager').map(role => ({ roleCode: role.roleCode, assigneeId: role.assigneeId || null })), ...item.managerIds.map(id => ({ roleCode: 'project_manager', assigneeId: id }))] }))
  const nextSignature = JSON.stringify({ parent: form.parentId, items })
  if (nextSignature !== signature) { key = createIdempotencyKey(); signature = nextSignature }
  saving.value = true; error.value = ''
  try {
    const created = await createAnnotationChildren(form.parentId, items, key, props.single)
    customEditors.value.forEach(editor => editor.markSaved()); ElMessage.success(`已创建 ${items.length} 个${isGrandchild.value?'三级':'子'}订单`); visible.value = false; emit('created', created)
  } catch (failure) { error.value = failure.detail || '创建失败，请重试'; await formRef.value?.applyServerErrors(failure) }
  finally { saving.value = false }
}
onBeforeUnmount(() => { controller?.abort(); ++parentSelectionId })
</script>

<style scoped>
.region-copy-note { color:var(--el-text-color-secondary); font-size:12px; }
.child-preview-row { border:1px solid var(--el-border-color-lighter); border-radius:6px; background:#fff; padding:16px; margin:16px 0; }
.child-copy-summary { margin-bottom: 12px; }
.child-preview-title { display:flex; justify-content:space-between; margin-bottom:10px; }
.child-preview-count { margin-right:12px; }
</style>
