<template>
  <div class="card-header">
    <span class="card-title">{{ title }}</span>
    <div class="header-actions">
      <el-date-picker
        :model-value="modelValue"
        type="date"
        placeholder="选择安排日期"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        style="width: 170px"
        :disabled="readonly"
        @update:model-value="$emit('update:modelValue', $event)"
        @change="$emit('change')"
      />
      <el-tag type="info" effect="plain">{{ weekdayLabel }}</el-tag>
      <template v-if="showAdminActions">
        <el-button type="primary" @click="$emit('addTask')">新增任务</el-button>
        <el-button @click="$emit('copyFromYesterday')">从昨日复制</el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '工作安排' },
  modelValue: { type: String, default: '' },
  weekdayLabel: { type: String, default: '' },
  showAdminActions: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false }
})
defineEmits(['update:modelValue', 'change', 'addTask', 'copyFromYesterday'])
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
</style>
