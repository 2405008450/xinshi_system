<template>
  <el-popover
    trigger="click"
    placement="left"
    :width="760"
    :title="title"
    popper-class="business-detail-popover"
    @show="emit('show')"
    @hide="handleHide"
  >
    <template #reference>
      <slot name="reference">
        <el-button type="primary" link>查看详情</el-button>
      </slot>
    </template>
    <div v-loading="loading" class="business-detail-popover__content">
      <slot name="content" :row="row">
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
            <InlineTextField
              v-else-if="item.editable"
              :model-value="rawValue(item)"
              :display-value="formatValue(item)"
              :editable="editable"
              :disabled="disabled"
              :label="item.label"
              :multiline="item.multiline"
              :maxlength="item.maxlength || 0"
              :required="item.required"
              :empty-as-null="item.emptyAsNull !== false"
              :placeholder="item.placeholder || ''"
              :save-field="(value) => saveItem(item, value)"
              @saved="(updated) => emit('field-saved', updated, item)"
              @conflict="emit('conflict')"
            />
            <span v-else class="business-detail-popover__value">{{ formatValue(item) }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </slot>
    </div>
  </el-popover>
</template>

<script setup>
import InlineTextField from './InlineTextField.vue'

const emit = defineEmits(['show', 'hide', 'field-saved', 'conflict'])

const props = defineProps({
  row: { type: Object, required: true },
  title: { type: String, default: '详情' },
  items: { type: Array, default: () => [] },
  statusLabel: { type: Function, default: (value) => value || '-' },
  statusType: { type: Function, default: () => 'info' },
  loading: { type: Boolean, default: false },
  editable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  saveField: { type: Function, default: null }
})

const rawValue = (item) => {
  if (item.valueGetter) return item.valueGetter(props.row)
  return props.row[item.valueKey || item.key]
}

const saveItem = (item, value) => {
  if (!props.saveField) return Promise.reject(new Error('未配置保存方法'))
  return props.saveField(item.field || item.key, value, item)
}

const handleHide = () => {
  window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
  emit('hide')
}

const formatValue = (item) => {
  const raw = rawValue(item)
  const value = item.formatter ? item.formatter(raw, props.row) : raw
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
