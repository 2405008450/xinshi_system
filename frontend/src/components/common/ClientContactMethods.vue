<template>
  <div class="contact-methods">
    <details v-for="(row, index) in rows" :key="row.id" class="contact-method-panel" :open="row.expanded" @toggle="row.expanded = $event.target.open">
      <summary>{{ row.type || '其他联系方式' }}</summary>
      <div class="contact-method" :class="{'contact-method--preset':row.preset}">
      <el-select v-if="!row.preset" v-model="row.type" filterable allow-create default-first-option
        :aria-label="`${label}类型`" placeholder="选择或输入类型" @change="publish">
        <el-option label="未分类" value="" />
        <el-option v-for="type in contactTypes" :key="type" :label="type" :value="type" />
        <el-option v-if="row.type && !contactTypes.includes(row.type)" :label="row.type" :value="row.type" />
      </el-select>
      <el-input v-model="row.value" maxlength="5000" :aria-label="`${label}${row.type || '其他'}内容${index + 1}`" :placeholder="`请输入${row.type || '联系方式'}（选填）`" @input="publish" />
      <el-button link type="danger" :aria-label="`${row.preset ? '清空' : '移除'}${row.type || ''}联系方式`" @click="remove(row.id)">{{ row.preset ? '清空' : '移除' }}</el-button>
      </div>
    </details>
    <el-button link type="primary" @click="add">添加其他联系方式</el-button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '联系方式' },
})
const emit = defineEmits(['update:modelValue'])
const contactTypes = ['手机', '微信', '邮箱', '固话', 'WhatsApp']
const rows = ref([])
let nextId = 0
let published

function parseLine(line) {
  const match = /^([^：:]+)([：:])\s*(.+)$/.exec(line)
  const preset = match && contactTypes.find(type => type.toLowerCase() === match[1].trim().toLowerCase())
  if (match && (preset || match[2] === '：')) {
    return { id: nextId++, type: preset || match[1].trim(), value: match[3].trim() }
  }
  return { id: nextId++, type: '', value: line }
}

watch(() => props.modelValue, value => {
  if (value !== published) {
    const parsed = value ? value.split(/\r?\n/).filter(line=>line.trim()).map(parseLine) : []
    const used = new Set()
    rows.value = parsed.map(row => {
      const preset = contactTypes.includes(row.type) && !used.has(row.type)
      if (preset) used.add(row.type)
      return {...row, preset, expanded:false}
    })
    for (const type of contactTypes) {
      if (!used.has(type)) rows.value.push({id:nextId++,type,value:'',preset:true,expanded:false})
    }
  }
  published = value
}, { immediate: true })

function publish() {
  published = rows.value.filter(row => row.value.trim()).map(row => {
    const type = row.type.trim().replace(/[\s：:]+/g, ' ')
    return type ? `${type}：${row.value.trim()}` : row.value.trim()
  }).join('\n')
  emit('update:modelValue', published)
}

function add() {
  rows.value.push({ id: nextId++, type: '', value: '', preset:false, expanded:true })
}

function remove(id) {
  const row = rows.value.find(row=>row.id===id)
  if (row?.preset) row.value=''
  else rows.value = rows.value.filter(row => row.id !== id)
  publish()
}
</script>

<style scoped>
.contact-methods { display: grid; gap: 8px; width: 100%; min-width: 0; }
.contact-method-panel { min-width: 0; border: 1px solid var(--el-border-color-light); border-radius: 6px; background: #fff; }
.contact-method-panel summary { padding: 7px 10px; cursor: pointer; color: var(--el-text-color-regular); font-size: 13px; }
.contact-method-panel[open] summary { border-bottom: 1px solid var(--el-border-color-lighter); }
.contact-method { display: grid; grid-template-columns: minmax(100px, 1fr) minmax(0, 2fr) auto; align-items: center; gap: 8px; }
.contact-method-panel .contact-method { padding: 8px 10px; }
.contact-method--preset { grid-template-columns: minmax(0, 1fr) auto; }
.contact-methods > .el-button { justify-self: start; }
@media (max-width: 460px) {
  .contact-method { grid-template-columns: minmax(0, 1fr) auto; }
  .contact-method .el-select { grid-column: 1 / -1; }
}
</style>
