<template>
  <el-select ref="selectRef"
    :model-value="modelValue"
    filterable
    remote
    :debounce="0"
    :remote-method="queueSearch"
    :loading="loading"
    placeholder="从人才总库搜索姓名、别名或资源编号"
    style="width: 100%"
    @visible-change="searchVisible=$event"
    @update:model-value="selectTalent"
  >
    <el-option v-for="person in displayOptions" :key="person.id" :label="talentLabel(person)" :value="person.id" />
    <template #label="{ label }">{{ selectedLabel || label }}</template>
    <template #empty><div class="el-select__empty">{{ loading ? '正在搜索人才总库…' : '无匹配的人才' }}<el-button v-if="!loading&&lastKeyword&&canCreate" link type="primary" @click="openRegistration(lastKeyword)">登记新译员</el-button></div></template>
  </el-select>
  <InlineTalentRegistrationDialog v-if="registrationReady" ref="registrationRef" @saved="talentCreated" />
</template>

<script setup>
import { computed,nextTick,onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import InlineTalentRegistrationDialog from '@/views/resource/components/InlineTalentRegistrationDialog.vue'
import {hasPermission} from '@/utils/permission'
import { getTalentIdentityOptions } from '@/api/talents'
import { createRemoteTalentSearch } from '@/utils/remoteTalentSearch'

const props=defineProps({
  modelValue: { type: String, default: '' },
  selectedLabel: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'select'])
const options = ref([])
const loading = ref(false)
const selectRef=ref(),registrationRef=ref(),registrationReady=ref(false),searchVisible=ref(false),lastKeyword=ref('')
const canCreate=computed(()=>hasPermission(['talents:write','translators:write']))
let lastPopupKeyword=''
let searchTimer
// Element Plus 需要真实 option 才能可靠渲染远程下拉的已选姓名。
const displayOptions=computed(()=>{
 const rows=options.value
 if(!props.modelValue||!props.selectedLabel||lastKeyword.value||rows.some(row=>String(row.id)===String(props.modelValue)))return rows
 return [{id:props.modelValue,fullName:props.selectedLabel},...rows]
})
const talentLabel = person => person.resourceCode ? `${person.fullName}（${person.resourceCode}）` : person.fullName
const search = createRemoteTalentSearch({
  fetchOptions: (keyword, signal) => getTalentIdentityOptions({ keyword }, { signal }),
  onUpdate: state => {
    options.value = state.items
    loading.value = state.loading
  },
  onError: () => ElMessage.error('人才总库资源加载失败，请重试'),
  onSuccess:(keyword,rows)=>{if(keyword.trim()&&!rows.length&&canCreate.value&&searchVisible.value&&lastPopupKeyword!==keyword.trim())void openRegistration(keyword.trim())},
})

function queueSearch(value) {
  clearTimeout(searchTimer)
  const keyword = value.trim()
  lastKeyword.value=keyword
  if(!keyword)lastPopupKeyword=''
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

async function openRegistration(name){
 lastPopupKeyword=name;registrationReady.value=true;selectRef.value?.blur();await nextTick();await registrationRef.value?.open(name)
}
function talentCreated(person){
 const option={...person,fullName:person.fullName||person.full_name,resourceCode:person.resourceCode||person.resource_code}
 options.value=[option,...options.value.filter(item=>item.id!==option.id)]
 emit('update:modelValue',option.id);emit('select',option)
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  search.dispose()
})
</script>
