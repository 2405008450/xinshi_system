<template>
  <el-popover
    trigger="click"
    placement="left"
    :width="800"
    :title="title"
    popper-class="business-detail-popover"
  >
    <template #reference>
      <slot name="reference">
        <el-button type="primary" link>查看详情</el-button>
      </slot>
    </template>
    <div class="business-detail-popover__content">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item
          v-for="item in items"
          :key="item.key"
          :label="item.label"
          :span="item.span || 1"
        >
          <el-tag v-if="item.type === 'status'" :type="statusType(row[item.key])" size="small">
            {{ statusLabel(row[item.key]) }}
          </el-tag>
          <span v-else class="business-detail-popover__value">{{ formatValue(item) }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-popover>
</template>

<script setup>
const props = defineProps({
  row: { type: Object, required: true },
  title: { type: String, default: '详情' },
  items: { type: Array, default: () => [] },
  statusLabel: { type: Function, default: (value) => value || '-' },
  statusType: { type: Function, default: () => 'info' }
})

const formatValue = (item) => {
  const value = item.formatter ? item.formatter(props.row[item.key], props.row) : props.row[item.key]
  if (value === null || value === undefined || value === '') return '-'
  if (!item.formatter && /(At|Time|_at|_time|date)$/i.test(item.key) && !Number.isNaN(Date.parse(value))) {
    const date = new Date(value)
    if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
  }
  if (Array.isArray(value)) {
    if (!value.length) return '-'
    return value.map((entry) => {
      if (entry && typeof entry === 'object') return Object.values(entry).filter(Boolean).join('：')
      return String(entry)
    }).join('、')
  }
  return String(value)
}
</script>

<style>
.business-detail-popover { max-width: calc(100vw - 32px) !important; }
.business-detail-popover .el-popover__title { padding-bottom: 10px; margin-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-primary); font-size: 15px; font-weight: 600; }
.business-detail-popover__content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.business-detail-popover .el-descriptions__label { width: 140px; min-width: 140px; white-space: nowrap; font-weight: 500; }
.business-detail-popover .el-descriptions__cell { padding: 9px 12px; }
.business-detail-popover__value { white-space: normal; word-break: break-word; overflow-wrap: anywhere; line-height: 1.6; }
</style>
