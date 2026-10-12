<template>
  <div class="request-arrangement-history">
    <h4>已安排的平台</h4>
    <p v-if="!items.length" class="muted">暂未安排</p>
    <el-descriptions v-for="item in items" :key="`${item.work_date}:${item.platform_id}:${item.request_no || ''}`" :column="2" border size="small">
      <el-descriptions-item label="日期">{{ chineseDate(item.work_date) }}</el-descriptions-item>
      <el-descriptions-item label="平台">{{ item.platform_name }}</el-descriptions-item>
      <el-descriptions-item label="账号">{{ item.account_name }}</el-descriptions-item>
      <el-descriptions-item label="负责人">{{ item.owner_name || '暂未分配' }}</el-descriptions-item>
      <el-descriptions-item v-if="item.request_no" label="需求编号">{{ item.request_no }}</el-descriptions-item>
      <el-descriptions-item label="执行状态">{{ item.active === false ? '需求关联已失效' : item.completed ? '已完成' : '未完成' }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>
<script setup>
import { arrangementChineseDate as chineseDate } from '@/utils/resourceArrangements'
defineProps({ items: { type: Array, default: () => [] } })
</script>
<style scoped>
.request-arrangement-history .el-descriptions{margin-bottom:12px}
</style>
