<template>
  <el-input
    :class="stateClass"
    :model-value="displayValue"
    :placeholder="placeholder"
    :readonly="isAuto"
    :disabled="isLocked"
    @update:model-value="isEditable && $emit('update:modelValue', $event)"
  >
    <template v-if="!isEditable" #suffix>
      <el-tooltip :content="resolvedTooltip" placement="top">
        <el-icon class="readonly-field__icon">
          <Lock v-if="isLocked" />
          <MagicStick v-else />
        </el-icon>
      </el-tooltip>
    </template>
  </el-input>
</template>

<script setup>
import { computed } from 'vue'
import { Lock, MagicStick } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  /**
   * auto     系统生成或从关联对象带出，底层 readonly，可选中复制
   * locked   前置条件未满足或键值不可改，底层 disabled，Tab 键跳过
   * editable 可正常填写，白底。用于「选了老客户就带出、新客户可手填」这类
   *          条件只读字段，调用方用计算属性在 auto/editable 间切换即可。
   */
  source: { type: String, default: 'auto' },
  placeholder: { type: String, default: '' },
  tooltip: { type: String, default: '' },
})

defineEmits(['update:modelValue'])

const isLocked = computed(() => props.source === 'locked')
const isEditable = computed(() => props.source === 'editable')
const isAuto = computed(() => !isLocked.value && !isEditable.value)

const stateClass = computed(() => {
  if (isLocked.value) return 'field-locked'
  if (isEditable.value) return ''
  return 'field-readonly'
})

const displayValue = computed(() =>
  props.modelValue === null || props.modelValue === undefined ? '' : String(props.modelValue)
)

const resolvedTooltip = computed(() => {
  if (props.tooltip) return props.tooltip
  return isLocked.value ? '满足前置条件后可用' : '由系统自动填写，不可修改'
})
</script>

<style scoped>
.readonly-field__icon {
  font-size: 13px;
}
</style>
