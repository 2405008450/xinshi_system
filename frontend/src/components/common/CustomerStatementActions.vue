<template>
  <div class="customer-statement-actions">
    <el-button link type="primary" @click="openHistory(false)">查看历史对账单</el-button>
    <el-button v-if="canWrite" link @click="openHistory(true)">合并月份</el-button>
    <slot />
    <CustomerStatementHistoryDialog
      v-if="historyVisible"
      v-model="historyVisible"
      :client="client"
      :merge-months="mergeMonths"
      @merged="emit('merged')"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CustomerStatementHistoryDialog from './CustomerStatementHistoryDialog.vue'
import { hasPermission } from '@/utils/permission'

defineProps({ client: { type: Object, required: true } })
const emit = defineEmits(['merged'])
const canWrite = hasPermission('projects:write')
const historyVisible = ref(false)
const mergeMonths = ref(false)

function openHistory(merge) {
  mergeMonths.value = merge
  historyVisible.value = true
}
</script>

<style scoped>
.customer-statement-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin: 4px 0 6px;
}
.customer-statement-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
