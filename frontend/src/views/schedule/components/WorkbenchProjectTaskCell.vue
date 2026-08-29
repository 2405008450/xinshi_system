<template>
  <div class="workbench-project-cell">
    <span class="workbench-project-cell__title" :title="title">{{ title }}</span>
    <div v-if="showMeta" class="workbench-project-cell__meta">
      <el-tag v-if="isSubOrder" type="warning" size="small" effect="plain">子订单</el-tag>
      <span v-if="taskTypeText">{{ taskTypeText }}</span>
      <span v-if="parentProjectText">母项目：{{ parentProjectText }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  row: { type: Object, required: true }
})

const isSubOrder = computed(() => props.row?.entity_type === 'suborder')
const title = computed(() => {
  const value = isSubOrder.value
    ? (props.row?.sub_project_name || props.row?.project_name)
    : props.row?.project_name
  return String(value || '-').trim() || '-'
})
const taskTypeText = computed(() => {
  const taskType = String(props.row?.task_type || '').trim()
  const projectType = String(props.row?.project_type_label || '').trim()
  return taskType && taskType !== projectType ? taskType : ''
})
const parentProjectText = computed(() => (
  isSubOrder.value && props.row?.project_name
    ? String(props.row.project_name).trim()
    : ''
))
const showMeta = computed(() => Boolean(isSubOrder.value || taskTypeText.value || parentProjectText.value))
</script>
