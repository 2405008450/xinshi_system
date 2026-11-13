<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    :debounce="0"
    :remote-method="queueSearch"
    :loading="loading"
    placeholder="从人才总库搜索姓名、别名或资源编号"
    style="width: 100%"
    @update:model-value="selectTalent"
  >
    <el-option v-for="person in options" :key="person.id" :label="talentLabel(person)" :value="person.id" />
    <template #label="{ label }">{{ selectedLabel || label }}</template>
    <template #empty><div class="el-select__empty">{{ loading ? '正在搜索人才总库…' : '无匹配的人才' }}</div></template>
  </el-select>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTalentIdentityOptions } from '@/api/talents'
import { createRemoteTalentSearch } from '@/utils/remoteTalentSearch'

defineProps({
  modelValue: { type: String, default: '' },
  selectedLabel: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'select'])
const options = ref([])
const loading = ref(false)
let searchTimer
const talentLabel = person => person.resourceCode ? `${person.fullName}（${person.resourceCode}）` : person.fullName
const search = createRemoteTalentSearch({
  fetchOptions: (keyword, signal) => getTalentIdentityOptions({ keyword }, { signal }),
  onUpdate: state => {
    options.value = state.items
    loading.value = state.loading
  },
  onError: () => ElMessage.error('人才总库资源加载失败，请重试'),
})

function queueSearch(value) {
  clearTimeout(searchTimer)
  const keyword = value.trim()
  if (!keyword) {
    void search.search('')
    return
  }
  search.input(keyword)
  loading.value = true
  searchTimer = setTimeout(() => search.search(keyword), 300)
}

function selectTalent(id) {
  const person = options.value.find(option => option.id === id)
  emit('update:modelValue', id)
  if (person) emit('select', person)
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  search.dispose()
})
</script>
