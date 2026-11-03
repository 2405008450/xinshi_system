<template>
  <div class="tax-price-fields">
    <el-form-item v-for="field in fields" :key="field.key" :label="field.label" :prop="prefix ? `${prefix}.${field.key}` : field.key">
      <ReadonlyField v-if="readonly" :model-value="modelValue?.[field.key] ?? '-'" source="auto" />
      <el-input-number v-else :model-value="modelValue?.[field.key]" :min="0" :precision="field.precision" :controls="false" :placeholder="`请输入${field.label}`" @update:model-value="update(field.key,$event)" />
    </el-form-item>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import ReadonlyField from './ReadonlyField.vue'
const props = defineProps({ modelValue: Object, prefix: { type: String, default: '' }, showTotals: { type: Boolean, default: true }, readonly: Boolean, showUnitPrices: { type: Boolean, default: true } })
const emit = defineEmits(['update:modelValue', 'change'])
const fields = computed(() => [
  ...(props.showUnitPrices ? [{ key: 'unitPriceExclTax', label: '不含税单价', precision: 6 },
  { key: 'unitPriceInclTax', label: '含税单价', precision: 6 }] : []),
  ...(props.showTotals ? [{ key: 'totalExclTax', label: '不含税总价', precision: 2 }, { key: 'totalInclTax', label: '含税总价', precision: 2 }] : []),
])
function update(key, value) { const result = { ...props.modelValue, [key]: value }; emit('update:modelValue', result); emit('change', result) }
</script>
<style scoped>
.tax-price-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; width: 100%; }
.tax-price-fields :deep(.el-input-number) { width: 100%; }
@media (max-width: 600px) { .tax-price-fields { grid-template-columns: minmax(0, 1fr); } }
</style>
