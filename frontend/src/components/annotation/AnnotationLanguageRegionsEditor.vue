<template>
  <div class="language-regions-editor" data-dialog-field-search-group>
    <div class="language-regions-header">
      <span data-dialog-field-search-group-title>{{ label }} · 地区要求（选填）</span>
      <el-button link type="primary" @click="add">添加地区</el-button>
    </div>
    <div v-for="(region,index) in rows" :key="index" class="language-region-row">
      <div v-for="field in fields" :key="field.key" :data-dialog-field-search-label="field.label" :data-dialog-field-search-aliases="field.aliases">
        <el-input :model-value="region[field.key]" :aria-label="`${label} 地区${index + 1} ${field.label}`" :placeholder="`${field.label}（选填）`" :maxlength="100" clearable @update:model-value="update(index,field.key,$event)" />
      </div>
      <el-button link type="danger" :disabled="!modelValue.length" :aria-label="`删除${label}地区${index + 1}`" @click="remove(index)">删除地区</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { copyLanguageRegions, emptyLanguageRegion } from '@/utils/annotationLanguageRegions'

const props = defineProps({ modelValue: { type: Array, default: () => [] }, label: { type: String, default: '语种' } })
const emit = defineEmits(['update:modelValue'])
const fields = [{ key: 'city', label: '城市', aliases: '市' }, { key: 'district', label: '区县', aliases: '区,县' }, { key: 'street', label: '街道', aliases: '乡镇,镇' }]
// 无数据时保留一行录入占位；只有实际输入或添加后才写入表单。
const rows = computed(() => props.modelValue.length ? props.modelValue : [emptyLanguageRegion()])
const update = (index, field, value) => {
  const next = copyLanguageRegions(rows.value)
  next[index][field] = value
  emit('update:modelValue', next)
}
const add = () => emit('update:modelValue', [...copyLanguageRegions(rows.value), emptyLanguageRegion()])
const remove = index => emit('update:modelValue', props.modelValue.filter((_, i) => i !== index))
</script>

<style scoped>
.language-regions-editor { width:100%; min-width:0; margin:8px 0 14px; }
.language-regions-header { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:6px; color:var(--el-text-color-secondary); font-size:13px; }
.language-region-row { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)) auto; align-items:center; gap:8px; margin-top:8px; }
.language-region-row > div { min-width:0; }
@media(max-width:600px) {
  .language-region-row { grid-template-columns:minmax(0,1fr); padding-bottom:8px; border-bottom:1px solid var(--el-border-color-lighter); }
  .language-region-row > .el-button { justify-self:end; }
  .language-regions-header { flex-wrap:wrap; }
}
</style>
