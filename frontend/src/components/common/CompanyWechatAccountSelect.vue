<template>
  <div class="company-wechat-select">
    <el-select :model-value="modelValue" multiple clearable filterable allow-create default-first-option
      placeholder="请选择账号，可输入其他账号并回车添加" @update:model-value="change">
      <el-option v-for="item in options" :key="item" :label="item" :value="item" />
      <el-option label="其他（自主添加）" value="__custom_company_wechat__" />
    </el-select>
    <div v-if="customVisible" class="company-wechat-custom">
      <el-input v-model="customName" maxlength="100" placeholder="请输入其他账号名称" @keydown.enter.prevent="addCustom" />
      <el-button @click="addCustom">添加</el-button><el-button text @click="customVisible = false">取消</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { companyWechatAccounts, deletedWechatMarkers, normalizeWechatAccounts } from '@/utils/companyWechatAccounts'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, includeDeleted: Boolean })
const emit = defineEmits(['update:modelValue'])
const customVisible = ref(false), customName = ref('')
const options = computed(() => [...new Set([...companyWechatAccounts, ...(props.includeDeleted ? deletedWechatMarkers : []), ...props.modelValue])])
function change(values) {
  if (values.includes('__custom_company_wechat__')) customVisible.value = true
  const cleaned = normalizeWechatAccounts(values.filter(value => value !== '__custom_company_wechat__'))
  if (cleaned.length > 100 || cleaned.some(value => value.length > 100)) return ElMessage.warning('最多选择100个账号，每个账号最多100个字符')
  if (!props.includeDeleted && cleaned.some(value => deletedWechatMarkers.includes(value))) return ElMessage.warning('请在跟进状态中记录删除情况')
  emit('update:modelValue', cleaned)
}
function addCustom() {
  if (!customName.value.trim()) return ElMessage.warning('请输入账号名称')
  change([...props.modelValue, customName.value.trim()]); customName.value = ''; customVisible.value = false
}
</script>

<style scoped>
.company-wechat-select{width:100%;min-width:0}.company-wechat-select :deep(.el-select){width:100%}
.company-wechat-custom{display:flex;gap:8px;margin-top:8px;align-items:center}.company-wechat-custom .el-input{min-width:0}
</style>
