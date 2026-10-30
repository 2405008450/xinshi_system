<template>
  <el-form-item label="客户经理" prop="clientManagerId">
    <div class="manager-field">
      <el-select :model-value="modelValue" filterable remote :remote-method="search" :loading="loading" clearable :placeholder="baselineName || '请选择客户经理'" @update:model-value="emit('update:modelValue', $event || '')" @visible-change="opened => opened && search('')">
        <el-option v-for="user in choices" :key="user.id" :value="user.id" :label="user.display_name || user.full_name || user.username" />
      </el-select>
      <ProjectClientManagerHistory v-if="projectId" :project-type="projectType" :project-id="projectId" />
    </div>
  </el-form-item>
  <el-form-item v-if="changed" label="客户经理调整原因" prop="clientManagerChangeReason" :rules="reasonRules">
    <el-input :model-value="reason" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="请说明调整客户经理的原因，保存后保留记录" @update:model-value="emit('update:reason', $event)" />
  </el-form-item>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getUserOptions } from '@/api/users'
import ProjectClientManagerHistory from './ProjectClientManagerHistory.vue'
const props = defineProps({ modelValue: String, reason: String, baselineId: String, baselineName: String, projectId: String, projectType: String })
const emit = defineEmits(['update:modelValue','update:reason'])
const users = ref([]), loading = ref(false)
const changed = computed(() => String(props.modelValue || '') !== String(props.baselineId || ''))
const reasonRules = [{validator:(_rule,value,done)=>String(value||'').trim()?done():done(new Error('请填写客户经理调整原因')),trigger:'blur'}]
const choices = computed(() => {
  const result = [...users.value]
  if (props.modelValue && !result.some(u=>u.id===props.modelValue)) result.unshift({id:props.modelValue,display_name:props.modelValue===localStorage.getItem('user_id')?(localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||props.modelValue):(props.baselineName||props.modelValue)})
  return result
})
let sequence = 0, controller
async function search(keyword) {
  const request = ++sequence
  controller?.abort(); controller = new AbortController(); loading.value = true
  try { const data = await getUserOptions({keyword,limit:50},controller.signal); if(request===sequence) users.value = data || [] }
  catch { /* 已选人员保留；接口统一处理错误。 */ }
  finally { if(request===sequence) loading.value = false }
}
onMounted(()=>search(''))
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.manager-field{display:flex;align-items:center;gap:12px;width:100%;flex-wrap:wrap}.manager-field .el-select{flex:1;min-width:160px}</style>
