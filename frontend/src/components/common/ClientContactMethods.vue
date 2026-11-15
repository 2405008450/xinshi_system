<template>
  <div class="contact-methods">
    <div v-for="row in rows" :key="row.id" class="contact-method">
      <el-select v-model="row.type" filterable allow-create default-first-option
        :aria-label="`${label}类型`" placeholder="选择或输入类型" @change="publish">
        <el-option label="未分类" value="" />
        <el-option v-for="type in contactTypes" :key="type" :label="type" :value="type" />
        <el-option v-if="row.type && !contactTypes.includes(row.type)" :label="row.type" :value="row.type" />
      </el-select>
      <el-input v-model="row.value" maxlength="5000" :aria-label="`${label}内容`" placeholder="请输入联系方式" @input="publish" />
      <el-button link type="danger" :aria-label="`移除${row.type || ''}联系方式`" @click="remove(row.id)">移除</el-button>
    </div>
    <el-button link type="primary" @click="add">{{ rows.length ? '继续添加' : '添加联系方式' }}</el-button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '联系方式' },
})
const emit = defineEmits(['update:modelValue'])
const contactTypes = ['微信', '手机', '邮箱', '固话', 'WhatsApp']
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
    rows.value = value ? value.split(/\r?\n/).map(parseLine) : []
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
  rows.value.push({ id: nextId++, type: '', value: '' })
}

function remove(id) {
  rows.value = rows.value.filter(row => row.id !== id)
  publish()
}
</script>

<style scoped>
.contact-methods { display: grid; gap: 8px; width: 100%; min-width: 0; }
.contact-method { display: grid; grid-template-columns: minmax(100px, 1fr) minmax(0, 2fr) auto; align-items: center; gap: 8px; }
.contact-methods > .el-button { justify-self: start; }
@media (max-width: 460px) {
  .contact-method { grid-template-columns: minmax(0, 1fr) auto; }
  .contact-method .el-select { grid-column: 1 / -1; }
}
</style>
