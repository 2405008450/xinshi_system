<template>
              <div class="detail-content interpretation-project-detail-content" v-loading="loading">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="订单号">{{ textValue(row.orderNo) }}</el-descriptions-item>
                  <el-descriptions-item label="项目状态">{{ statusLabel(row.projectStatus) }}</el-descriptions-item>
                  <el-descriptions-item label="项目名称" :span="2">{{ textValue(row.projectName) }}</el-descriptions-item>
                  <el-descriptions-item label="内部协作角色" :span="2">{{ internalRolesText(row) }}</el-descriptions-item>
                  <el-descriptions-item label="具体任务" :span="2"><InlineTextField :model-value="row.taskDescription" :editable="editable" label="具体任务" multiline :save-field="(value) => saveField('taskDescription', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(row) }}</el-descriptions-item>
                  <el-descriptions-item label="客户简称">{{ textValue(row.clientShortName) }}</el-descriptions-item>
                  <el-descriptions-item label="客户编号">{{ textValue(row.clientCode) }}</el-descriptions-item>
                  <el-descriptions-item label="客户全称">{{ textValue(row.clientFullName) }}</el-descriptions-item>
                  <el-descriptions-item label="客户领域">{{ textValue(row.clientDomain) }}</el-descriptions-item>
                  <el-descriptions-item label="现客户经理">{{ textValue(row.currentClientManager) }}</el-descriptions-item>
                  <el-descriptions-item label="客户经理联系方式">{{ textValue(row.managerContact) }}</el-descriptions-item>
                  <el-descriptions-item label="子客户/联系人"><InlineTextField :model-value="row.contactName" :display-value="row.contactName || row.subClientContact" :editable="editable" label="子客户/联系人" :maxlength="255" :save-field="(value) => saveField('contactName', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="客户单号/项目标识" :span="2"><InlineTextField :model-value="row.customerOrderNo" :editable="editable" label="客户单号/项目标识" :maxlength="150" :save-field="(value) => saveField('customerOrderNo', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="项目时间" :span="2">{{ timeRangesText(row.timeRanges) }}</el-descriptions-item>
                  <el-descriptions-item label="项目地点" :span="2">{{ arrayText(row.locations, '、') }}</el-descriptions-item>
                  <el-descriptions-item label="口译方向" :span="2">{{ textValue(row.languageDirectionsDisplay) }}</el-descriptions-item>
                  <el-descriptions-item label="客户预算" :span="2"><InlineTextField :model-value="row.customerBudget" :editable="editable" label="客户预算" multiline :maxlength="500" :save-field="(value) => saveField('customerBudget', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="客户咨询时间">{{ formatDateTime(row.customerConsultationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="客户确认时间">{{ formatDateTime(row.customerConfirmationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="口译领域" :span="2"><InlineTextField :model-value="row.interpretationDomain" :editable="editable" label="口译领域" multiline :save-field="(value) => saveField('interpretationDomain', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="口译内容" :span="2"><InlineTextField :model-value="row.interpretationContent" :editable="editable" label="口译内容" multiline :save-field="(value) => saveField('interpretationContent', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="总需求人数">{{ textValue(row.requiredInterpreterCount) }}</el-descriptions-item>
                  <el-descriptions-item label="译员性别">{{ textValue(row.requiredInterpreterGender) }}</el-descriptions-item>
                  <el-descriptions-item label="口译水平">{{ textValue(row.requiredInterpretationLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="特殊要求"><InlineTextField :model-value="row.interpreterSpecialRequirements" :editable="editable" label="特殊要求" multiline :save-field="(value) => saveField('interpreterSpecialRequirements', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="译员身高"><InlineTextField :model-value="row.interpreterHeightRequirement" :editable="editable" label="译员身高" :maxlength="100" :save-field="(value) => saveField('interpreterHeightRequirement', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="译员相貌"><InlineTextField :model-value="row.interpreterAppearanceRequirement" :editable="editable" label="译员相貌" :maxlength="255" :save-field="(value) => saveField('interpreterAppearanceRequirement', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="着装要求" :span="2"><InlineTextField :model-value="row.interpreterDressRequirement" :editable="editable" label="着装要求" :maxlength="255" multiline :save-field="(value) => saveField('interpreterDressRequirement', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="译员安排" :span="2">{{ textValue(row.assignedInterpretersDisplay) }}</el-descriptions-item>
                  <el-descriptions-item label="译员编号" :span="2">{{ textValue(row.translatorCodes) }}</el-descriptions-item>
                  <el-descriptions-item label="项目文件路径" :span="2"><InlineTextField :model-value="row.filePath" :editable="editable" label="项目文件路径" multiline :save-field="(value) => saveField('filePath', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="报价单路径" :span="2"><InlineTextField :model-value="row.quotationPath" :editable="editable" label="报价单路径" multiline :save-field="(value) => saveField('quotationPath', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="合同路径" :span="2"><InlineTextField :model-value="row.contractPath" :editable="editable" label="合同路径" multiline :save-field="(value) => saveField('contractPath', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="客户对信实评价">{{ textValue(row.clientRating) }}</el-descriptions-item>
                  <el-descriptions-item label="评价备注"><InlineTextField :model-value="row.clientRatingNote" :editable="editable" label="评价备注" multiline :save-field="(value) => saveField('clientRatingNote', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="客户对译员评价" :span="2">
                    {{ interpreterRatingsText(row.interpreterAssignments) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="发圈请求" :span="2"><InlineTextField :model-value="row.socialPostRequest" :editable="editable" label="发圈请求" multiline :save-field="(value) => saveField('socialPostRequest', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="资源请求" :span="2"><InlineTextField :model-value="row.resourceRequest" :editable="editable" label="资源请求" multiline :save-field="(value) => saveField('resourceRequest', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                  <el-descriptions-item label="来源咨询 ID" :span="2">{{ textValue(row.consultationId) }}</el-descriptions-item>
                  <el-descriptions-item label="创建时间">{{ formatDateTime(row.createdAt) }}</el-descriptions-item>
                  <el-descriptions-item label="更新时间">{{ formatDateTime(row.updatedAt) }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="2">
                    <InlineTextField :model-value="row.remarks" :editable="editable" label="备注" multiline :save-field="(value) => saveField('remarks', value)" @conflict="emit('conflict')" />
                  </el-descriptions-item>
                  <el-descriptions-item label="邮件主题预览" :span="2"><InlineTextField :model-value="row.emailSubjectPreview" :editable="editable" label="邮件主题预览" multiline :save-field="(value) => saveField('emailSubjectPreview', value)" @conflict="emit('conflict')" /></el-descriptions-item>
                </el-descriptions>
              </div>
</template>
<script setup>
import InlineTextField from '@/components/common/InlineTextField.vue'
import { formatBusinessDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { statusLabel, statusType, textValue, internalRolesText, arrayText, timeRangesText, projectTypesText, interpreterRatingsText } from '@/utils/interpretationProjectDetail'
defineProps({ row: { type: Object, required: true }, editable: Boolean, loading: Boolean, saveField: Function })
const emit = defineEmits(['conflict'])
</script>
<style>
.interpretation-project-detail-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; overflow-wrap: anywhere; }
.interpretation-project-detail-content .el-descriptions__content { white-space: normal; overflow-wrap: anywhere; }
</style>
