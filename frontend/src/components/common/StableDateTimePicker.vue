<template>
  <span class="stable-date-time-picker" @input.capture="handleNativeInput">
    <el-date-picker
      v-bind="$attrs"
      :model-value="modelValue"
      type="datetime"
      value-format="YYYY-MM-DDTHH:mm:ss"
      @update:model-value="$emit('update:modelValue', $event)"
    />
  </span>
</template>

<script setup>
defineOptions({ inheritAttrs: false })

defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])

const normalizeTypedDateTime = (value) => {
  const match = String(value || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/)
  if (!match) return ''
  const [, year, month, day, hour, minute, second = '00'] = match
  const normalized = `${year}-${month}-${day}T${hour}:${minute}:${second}`
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return ''
  if (
    parsed.getFullYear() !== Number(year) || parsed.getMonth() + 1 !== Number(month)
    || parsed.getDate() !== Number(day) || parsed.getHours() !== Number(hour)
    || parsed.getMinutes() !== Number(minute) || parsed.getSeconds() !== Number(second)
  ) return ''
  return normalized
}

const handleNativeInput = (event) => {
  if (!(event.target instanceof HTMLInputElement) || event.isComposing) return
  const normalized = normalizeTypedDateTime(event.target.value)
  if (normalized) emit('update:modelValue', normalized)
}
</script>

<style scoped>
.stable-date-time-picker { display: inline-flex; max-width: 100%; }
</style>
