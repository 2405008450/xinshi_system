<template>
  <el-descriptions :column="2" border size="small">
    <el-descriptions-item label="需求编号">{{ request.requestNo || '-' }}</el-descriptions-item>
    <el-descriptions-item label="需求状态">{{ demandStatusLabels[request.demandStatus] || '-' }}</el-descriptions-item>
    <el-descriptions-item label="项目类型">{{ projectTypes || request.sourceProjectTypesSnapshot?.map(value => projectTypeLabels[value] || value).join('、') || '-' }}</el-descriptions-item>
    <el-descriptions-item label="项目状态">{{ projectStatus || getProjectStatusLabel(request.sourceType, request.currentProjectStatus || request.sourceStatusSnapshot) }}</el-descriptions-item>
    <el-descriptions-item label="请求状态">{{ statuses[request.requestStatus] || '-' }}</el-descriptions-item>
    <el-descriptions-item label="需求项目订单号">{{ request.currentOrderNo || request.sourceOrderNoSnapshot || '-' }}</el-descriptions-item>
    <el-descriptions-item label="需求项目"><slot name="project">{{ request.currentProjectName || request.sourceProjectNameSnapshot || '-' }}</slot></el-descriptions-item>
    <el-descriptions-item label="客户编号">{{ request.clientCodeSnapshot || '-' }}</el-descriptions-item>
    <el-descriptions-item label="客户简称">{{ request.clientShortNameSnapshot || '-' }}</el-descriptions-item>
    <el-descriptions-item :label="request.sourceType==='annotation' ? '项目经理' : '负责人'">{{ request.projectManagers?.map(p=>p.name).join('、') || ownerLabel || '-' }}</el-descriptions-item>
    <el-descriptions-item label="优先级">{{ priorities[request.priority] || '-' }}</el-descriptions-item>
    <el-descriptions-item label="发起时间">{{ formatBusinessDateTime(request.requestedAt) }}</el-descriptions-item>
    <el-descriptions-item label="需求详情" :span="2"><details><summary>总体需求</summary><ScreenshotText :text="request.requestDetail || '-'" /></details><ResourceRequestVersions :model-value="request.requestContent?.versions || []" /><ResourceRequestDispatchNotes :notes="request.requestContent?.dispatchNotes || {}" /></el-descriptions-item>
    <el-descriptions-item label="语种、人数及要求" :span="2">
      <slot name="items">
        <el-table :data="request.items || []" border size="small" max-height="360">
          <el-table-column label="需求语种" min-width="140"><template #default="{ row }">{{ row.languageLabels?.join(' → ') || '-' }}</template></el-table-column>
          <el-table-column label="需求人数" width="90"><template #default="{ row }">{{ row.requiredCount ?? '-' }}</template></el-table-column>
          <el-table-column prop="requirementDetail" label="具体要求" min-width="180" />
        </el-table>
      </slot>
    </el-descriptions-item>
  </el-descriptions>
</template>
<script setup>
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import ResourceRequestVersions from './ResourceRequestVersions.vue'
import ResourceRequestDispatchNotes from './ResourceRequestDispatchNotes.vue'
import { demandStatusLabels } from '@/utils/resourceRequestLifecycle'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { getProjectStatusLabel } from '@/utils/projectStatus'
import { projectTypeLabels } from '@/utils/resourceRequestProjectTypes'
defineProps({ request: { type: Object, required: true }, projectTypes: String, projectStatus: String, ownerLabel: String })
const statuses = { draft: '草稿', submitted: '已提交', in_progress: '进行中', fulfilled: '已完成', cancelled: '已取消' }
const priorities = { high: '高', medium: '中', low: '低' }
</script>
