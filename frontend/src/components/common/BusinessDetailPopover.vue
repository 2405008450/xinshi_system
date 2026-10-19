<template>
  <el-popover
    trigger="click"
    :placement="placement"
    :width="760"
    :title="title"
    :popper-class="popperClass"
    @show="emit('show')"
    @hide="handleHide"
  >
    <template #reference>
      <slot name="reference">
        <el-button type="primary" link>查看详情</el-button>
      </slot>
    </template>
    <BusinessDetailContent :row="row" :items="items" :status-label="statusLabel" :status-type="statusType" :loading="loading" :editable="editable" :disabled="disabled" :save-field="saveField" @field-saved="(updated, item) => emit('field-saved', updated, item)" @conflict="emit('conflict')">
      <template v-if="$slots.content" #default="slotProps"><slot name="content" v-bind="slotProps" /></template>
    </BusinessDetailContent>
  </el-popover>
</template>

<script setup>
import BusinessDetailContent from './BusinessDetailContent.vue'

const emit = defineEmits(['show', 'hide', 'field-saved', 'conflict'])

const props = defineProps({
  placement: { type: String, default: 'left' },
  popperClass: { type: String, default: 'business-detail-popover' },
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

const handleHide = () => {
  window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
  emit('hide')
}

</script>
