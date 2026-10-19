<template>
  <ResourceRequestDetailPopover :model-value="modelValue" :virtual-ref="anchor" :teleported="false" :request="requestLink" title="开拓方向详情" back-label="返回开拓方向" @update:model-value="$emit('update:modelValue', $event)">
    <template #default="{ openProject, hasProject }">
      <div class="arrangement-option-detail" v-loading="loading" @mousedown.stop @click.stop>
        <div class="arrangement-option-detail-actions"><el-button link type="primary" @click="$emit('update:modelValue', false)">关闭</el-button></div>
        <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
        <ResourceRequestDetailContent v-if="detail" :request="detail" :owner-label="ownerLabel">
          <template #project><el-button v-if="hasProject" link type="primary" @click="openProject($event.currentTarget)">{{ target.project?.project_name || detail.currentProjectName || detail.sourceProjectNameSnapshot }}</el-button><span v-else>{{ detail.currentProjectName || detail.sourceProjectNameSnapshot || '-' }}</span></template>
        </ResourceRequestDetailContent>
        <el-descriptions v-else :column="2" border size="small">
          <el-descriptions-item label="项目名称" :span="2"><el-button v-if="hasProject" link type="primary" @click="openProject($event.currentTarget)">{{ target.project.project_name }}</el-button><span v-else>{{ target.label || '-' }}</span></el-descriptions-item>
          <el-descriptions-item label="订单号">{{ target.project?.order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="语种" :span="2">{{ target.project?.languages?.join('、') || '未配置语种' }}</el-descriptions-item>
          <el-descriptions-item label="需求编号">{{ target.request_no || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </ResourceRequestDetailPopover>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getResourceRequest } from '@/api/resourceRequests'
import ResourceRequestDetailPopover from './ResourceRequestDetailPopover.vue'
import ResourceRequestDetailContent from './ResourceRequestDetailContent.vue'
const props = defineProps({ modelValue: Boolean, anchor: Object, target: { type: Object, required: true }, users: { type: Array, default: () => [] } })
defineEmits(['update:modelValue'])
const detail = ref(null), loading = ref(false), error = ref('')
const requestLink = computed(() => detail.value || { sourceType: props.target.project?.source_type, [`${props.target.project?.source_type}ProjectId`]: props.target.project?.project_id })
const ownerLabel = computed(() => props.users.find(u => u.id === detail.value?.ownerId)?.name || '-')
let sequence = 0
async function load() {
  const seq = ++sequence; detail.value = null; error.value = ''; loading.value = false
  if (!props.modelValue || !props.target.request_id) return
  loading.value = true
  try { const value = await getResourceRequest(props.target.request_id); if (seq === sequence) detail.value = value }
  catch (e) { if (seq === sequence) error.value = e.message || '需求详情加载失败，请重试' }
  finally { if (seq === sequence) loading.value = false }
}
watch(() => [props.modelValue, props.target], load, { immediate: true })
onBeforeUnmount(() => { sequence++ })
</script>
<style>
.arrangement-option-detail { max-height: min(560px, calc(100vh - 140px)); overflow-y: auto; overflow-wrap: anywhere; white-space: normal; font-weight: normal; color: var(--el-text-color-primary); }
.arrangement-option-detail .el-button { white-space: normal; height: auto; text-align: left; }
.arrangement-option-detail-actions { display: flex; justify-content: flex-end; margin-bottom: 8px; }
</style>
