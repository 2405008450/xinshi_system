<template>
    <div class="annotation-project-detail__content" v-loading="loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-if="displayRow.parentProjectId" :label="displayRow.orderLevel === 2 ? '所属子订单' : '所属订单'" :span="2"><router-link v-if="allowNestedDetails" :to="{name: 'AnnotationProjectDetails', query: {projectId: displayRow.parentProjectId, openEditor: '1'}}">{{ displayRow.parentOrderNo }} · {{ displayRow.parentProjectName }}</router-link><span v-else>{{ displayRow.parentOrderNo }} · {{ displayRow.parentProjectName }}</span></el-descriptions-item>
        <el-descriptions-item v-if="displayRow.directionSummary" label="子订单方向检查" :span="2">
          <div v-if="displayRow.directionSummary.missingDirections?.length">{{ displayRow.directionSummary.automaticEnabled ? '缺失方向' : '单方向无需自动生成' }}：{{ displayRow.directionSummary.missingDirections.join('；') }}</div>
          <div v-if="displayRow.directionSummary.extraDirections?.length">额外方向：{{ displayRow.directionSummary.extraDirections.join('；') }}；已有子订单保留，请人工处理。</div>
          <div v-if="displayRow.directionSummary.invalidChildOrderNos?.length">非单方向子订单：{{ displayRow.directionSummary.invalidChildOrderNos.join('、') }}；请人工调整为一个方向。</div>
          <span v-if="!displayRow.directionSummary.missingDirections?.length && !displayRow.directionSummary.extraDirections?.length && !displayRow.directionSummary.invalidChildOrderNos?.length">方向对应完整</span>
        </el-descriptions-item>
        <el-descriptions-item label="订单号">{{ textValue(displayRow.orderNo) }}</el-descriptions-item>
        <el-descriptions-item label="项目进度"><el-tag :type="statusType(displayRow.projectStatus)">{{ statusLabel(displayRow.projectStatus) }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="最新客户进度" :span="2">{{ textValue(displayRow.latestCustomerProgressNote) }}</el-descriptions-item>
        <el-descriptions-item label="客户进度时间">{{ formatCustomerProgressTime(displayRow.latestCustomerProgressEffectiveOn) }}</el-descriptions-item>
        <el-descriptions-item label="优先次序"><el-tag :type="priorityType(displayRow.priority)">{{ priorityLabel(displayRow.priority) }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="状态生效时间">{{ formatDateTime(displayRow.statusEffectiveOn) }}</el-descriptions-item>
        <el-descriptions-item label="片区">{{ displayRow.areaLabels?.join('、') || '-' }}</el-descriptions-item>
        <el-descriptions-item label="语言地区"><InlineTextField :model-value="displayRow.languageRegion" :editable="editable" label="语言地区" :maxlength="255" :save-field="(value) => saveText('languageRegion', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="项目名称" :span="2">{{ textValue(displayRow.projectName) }}</el-descriptions-item>
        <el-descriptions-item label="内部协作角色" :span="2">{{ internalRolesText(displayRow) }}</el-descriptions-item>
        <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(displayRow.projectTypes) }}</el-descriptions-item>
        <el-descriptions-item label="具体任务" :span="2"><InlineTextField :model-value="displayRow.taskDescription" :editable="editable" label="具体任务" multiline :save-field="(value) => saveText('taskDescription', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="语言方向" :span="2"><LanguageTalentReservePopover v-if="allowNestedDetails && displayRow.languageItems?.length" :language-items="displayRow.languageItems" /><span v-else>{{ textValue(displayRow.languageItemsDisplay || (displayRow.languageItems || []).map(item => item.display || item.sourceLanguageLabel).filter(Boolean).join('；')) }}</span></el-descriptions-item>
        <el-descriptions-item label="（潜在）需求量" :span="2"><InlineTextField :model-value="displayRow.potentialDemand" :editable="editable" label="（潜在）需求量" multiline :save-field="(value) => saveText('potentialDemand', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="客户简称">{{ textValue(displayRow.clientShortName) }}</el-descriptions-item>
        <el-descriptions-item label="客户编号">{{ textValue(displayRow.clientCode) }}</el-descriptions-item>
        <el-descriptions-item label="客户全称" :span="2">{{ textValue(displayRow.clientFullName) }}</el-descriptions-item>
        <el-descriptions-item label="子客户/联系人"><InlineTextField :model-value="displayRow.contactName" :display-value="displayRow.contactName || displayRow.subClientContact" :editable="editable" label="子客户/联系人" :maxlength="255" :save-field="(value) => saveText('contactName', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="客户单号/项目标识"><InlineTextField :model-value="displayRow.customerOrderNo" :editable="editable" label="客户单号/项目标识" :maxlength="150" :save-field="(value) => saveText('customerOrderNo', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="邮件主题预览" :span="2"><InlineTextField :model-value="displayRow.emailSubjectPreview" :editable="editable" label="邮件主题预览" multiline :maxlength="1000" :save-field="(value) => saveText('emailSubjectPreview', value)" @conflict="emit('conflict')" /></el-descriptions-item>
        <el-descriptions-item label="客户单价" :span="2">
          <div v-if="displayRow.priceItems?.length" class="annotation-project-detail__list"><div v-for="item in displayRow.priceItems" :key="item.id">{{ item.display }}<span v-if="item.remarks">（{{ item.remarks }}）</span></div></div><span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="标注人员安排" :span="2">
          <div v-if="displayRow.assignees?.length" class="annotation-project-detail__list">
            <div v-for="item in displayRow.assignees" :key="item.id" class="annotation-project-detail__assignee">
              <div>{{ item.personName }}<span v-if="item.resourceCode" class="detail-secondary">（{{ item.resourceCode }}）</span> <el-tag size="small" :type="assignmentStatusType(item.assignmentStatus)">{{ assignmentStatusLabel(item.assignmentStatus) }}</el-tag></div>
              <div v-if="item.qualityScore || item.evaluationNote" class="detail-secondary"><span v-if="item.qualityScore">质量评分：{{ item.qualityScore }} </span><span v-if="item.evaluationNote">评价备注：{{ item.evaluationNote }}</span></div>
              <div v-if="item.audioDurationValue != null" class="detail-secondary">音频时长：{{ item.audioDurationValue }} {{ item.audioDurationUnit || '' }}</div>
              <div v-if="item.rate" class="detail-secondary">人员计价：{{ item.rate.amount }} {{ item.rate.currency || 'CNY' }} / {{ item.rate.unit }}</div>
            </div>
          </div><span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="任务派发时间">{{ formatDateTime(displayRow.taskDispatchedAt) }}</el-descriptions-item>
        <el-descriptions-item label="任务提交时间">{{ displayRow.taskSubmittedAt ? formatDateTime(displayRow.taskSubmittedAt) : '待定' }}</el-descriptions-item>
        <el-descriptions-item label="客户经理">{{ textValue(displayRow.clientManagerName) }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ textValue(displayRow.createdByName) }}</el-descriptions-item>
        <el-descriptions-item label="文件路径" :span="2">{{ textValue(displayRow.projectPath) }}</el-descriptions-item>
        <el-descriptions-item v-if="displayRow.quotationPath" label="历史报价单路径" :span="2">{{ displayRow.quotationPath }}</el-descriptions-item>
        <el-descriptions-item v-if="displayRow.contractPath" label="历史合同路径" :span="2">{{ displayRow.contractPath }}</el-descriptions-item>
        <el-descriptions-item label="关联咨询编号">{{ textValue(displayRow.consultationCode) }}</el-descriptions-item>
        <el-descriptions-item label="客户咨询时间">{{ formatDateTime(displayRow.customerConsultationTime) }}</el-descriptions-item>
        <el-descriptions-item label="客户确认时间">{{ formatDateTime(displayRow.customerConfirmationTime) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(displayRow.createdAt) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(displayRow.updatedAt) }}</el-descriptions-item>
        <el-descriptions-item v-if="displayRow.legacyOrderNo" label="原笔译订单号">{{ displayRow.legacyOrderNo }}</el-descriptions-item>
        <el-descriptions-item v-if="displayRow.legacyStatus" label="迁移前状态">{{ displayRow.legacyStatus }}</el-descriptions-item>
        <el-descriptions-item v-for="field in visibleCustomFields" :key="field.id" :label="field.fieldLabel" :span="field.dataType === 'textarea' ? 2 : 1">
          <InlineTextField v-if="field.dataType === 'text'" :model-value="displayRow.customValues?.[field.id]" :editable="editable && field.isActive !== false" :label="field.fieldLabel" :required="field.isRequired" multiline :save-field="(value) => saveCustom(field, value)" @conflict="emit('conflict')" />
          <template v-else>{{ customFieldText(displayRow.customValues?.[field.id]) }}</template>
        </el-descriptions-item>
        <el-descriptions-item label="状态履历" :span="2">
          <el-timeline v-if="history.length" class="status-timeline"><el-timeline-item v-for="item in history" :key="item.id" :timestamp="`${formatDateTime(item.effectiveOn)} · ${formatDateTime(item.changedAt)}`"><el-tag size="small" :type="statusType(item.toStatus)">{{ statusLabel(item.toStatus) }}</el-tag><span v-if="item.changeNote" class="history-note">{{ item.changeNote }}</span></el-timeline-item></el-timeline><span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="云端项目资料" :span="2"><AnnotationMaterialManager v-if="allowNestedDetails && materialsActive" :project-id="String(projectId)" readonly /><template v-else><div v-for="file in materials" :key="file.file_id">{{ file.original_name }} · V{{ file.version_no }} · {{ formatDateTime(file.created_at) }}</div><span v-if="!materials.length">{{ materialsError || '暂无文件' }}</span></template></el-descriptions-item>
      </el-descriptions>
    </div>
</template>
<script setup>
import { computed } from 'vue'
import { annotationStatusLabel as statusLabel, annotationStatusType as statusType } from '@/utils/annotationStatus'
import { annotationInternalRolesText as internalRolesText } from '@/utils/annotationInternalRoles'
import { formatBusinessDateTime as formatDateTime, formatBusinessDateTimeMinute as formatCustomerProgressTime } from '@/utils/dateTime'
import InlineTextField from '@/components/common/InlineTextField.vue'
import LanguageTalentReservePopover from './LanguageTalentReservePopover.vue'
import AnnotationMaterialManager from './AnnotationMaterialManager.vue'
const props = defineProps({ row: { type: Object, required: true }, projectId: [String, Number], history: { type: Array, default: () => [] }, customFields: { type: Array, default: () => [] }, editable: Boolean, loading: Boolean, allowNestedDetails: { type: Boolean, default: true }, materialsActive: Boolean, materials: { type: Array, default: () => [] }, materialsError: String, saveTextField: Function, saveCustomField: Function })
const emit = defineEmits(['conflict'])
const displayRow = computed(() => props.row)
const visibleCustomFields = computed(() => props.customFields.filter(field => !['项目经理', '跟进状态'].includes(field.fieldLabel?.trim())))
const saveText = (field, value) => props.saveTextField(field, value)
const saveCustom = (field, value) => props.saveCustomField(field, value)
const projectTypeMap = { audio_collection:'音频采集',audio_annotation:'音频标注',audio_evaluation:'音频评测',text_evaluation:'文本评测',text_annotation:'文本标注',quality_inspection:'质检',listening_test:'测听',slot_deduction:'扣槽',generalization:'泛化',translation:'翻译',ai_evaluation:'ai评测' }
const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const customFieldText = (value) => Array.isArray(value) ? value.join('、') : value === true ? '是' : value === false ? '否' : textValue(value)
const projectTypesText = (values) => Array.isArray(values) && values.length ? values.map((value) => projectTypeMap[value] || value).join('；') : '-'
const priorityLabel = (value) => ({low:'低',medium:'中',high:'高'}[value] || '-')
const priorityType = (value) => ({high:'danger',medium:'warning',low:'info'}[value] || 'info')
const assignmentStatusLabel = (value) => ({assigned:'已安排',in_progress:'进行中',completed:'已完成',cancelled:'已取消'}[value] || value || '-')
const assignmentStatusType = (value) => ({assigned:'info',in_progress:'primary',completed:'success',cancelled:'danger'}[value] || 'info')
</script>
<style>
.annotation-detail-popover { max-width: calc(100vw - 32px) !important; }
.annotation-project-detail__content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.annotation-project-detail__content .el-descriptions__label { width: 140px; min-width: 140px; white-space: nowrap; }
.annotation-project-detail__content .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.annotation-project-detail__list { display: grid; gap: 6px; }
.annotation-project-detail__assignee { display: grid; gap: 3px; }
.annotation-project-detail__content .detail-secondary { margin-left: 6px; color: var(--el-text-color-secondary); }
.annotation-project-detail__content .history-note { margin-left: 8px; white-space: pre-wrap; }
</style>
