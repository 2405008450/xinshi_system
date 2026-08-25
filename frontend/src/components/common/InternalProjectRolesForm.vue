<template>
  <section class="internal-roles-section">
    <div class="internal-roles-section__title">内部协作角色</div>
    <div class="internal-roles-section__hint">留空后，该角色任务将进入工作台认领池。</div>
    <el-row :gutter="16">
      <el-col v-for="role in roles" :key="role.code" :xs="24" :md="8">
        <el-form-item :label="role.label">
          <el-select
            :model-value="assignmentValue(role.code)"
            filterable
            clearable
            :loading="loading[role.code]"
            :placeholder="`请选择${role.label}`"
            style="width: 100%"
            @update:model-value="updateAssignment(role.code, $event)"
          >
            <el-option
              v-for="candidate in candidates[role.code]"
              :key="candidate.id"
              :label="candidateLabel(candidate)"
              :value="candidate.id"
              :disabled="candidate.isOnLeave || candidate.is_on_leave"
            />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
  </section>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjectRoleCandidatesAPI } from '@/api/workflow'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const roles = [
  { code: 'project_manager', label: '项目经理' },
  { code: 'project_specialist', label: '项目专员' },
  { code: 'project_assistant', label: '项目助理' },
]
const candidates = reactive(Object.fromEntries(roles.map((role) => [role.code, []])))
const loading = reactive(Object.fromEntries(roles.map((role) => [role.code, false])))

const assignmentValue = (roleCode) => (
  props.modelValue.find((item) => (item.roleCode || item.role_code) === roleCode)?.assigneeId
  || props.modelValue.find((item) => (item.roleCode || item.role_code) === roleCode)?.assignee_id
  || ''
)
const candidateLabel = (candidate) => {
  const name = candidate.fullName || candidate.full_name || candidate.username
  return (candidate.isOnLeave || candidate.is_on_leave) ? `${name}（请假中）` : name
}
const updateAssignment = (roleCode, assigneeId) => {
  const next = roles.map((role) => ({
    roleCode: role.code,
    assigneeId: role.code === roleCode ? (assigneeId || null) : (assignmentValue(role.code) || null),
  }))
  emit('update:modelValue', next)
}
const loadCandidates = async (roleCode) => {
  loading[roleCode] = true
  try {
    candidates[roleCode] = await getProjectRoleCandidatesAPI(roleCode) || []
  } catch (error) {
    ElMessage.error(error.detail || `加载${roles.find((item) => item.code === roleCode)?.label}候选人失败`)
  } finally {
    loading[roleCode] = false
  }
}

onMounted(() => Promise.all(roles.map((role) => loadCandidates(role.code))))
</script>

<style scoped>
.internal-roles-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--el-border-color-lighter); }
.internal-roles-section__title { color: var(--el-text-color-primary); font-size: 15px; font-weight: 600; }
.internal-roles-section__hint { margin: 5px 0 14px; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
