<template>
  <div class="manager-cell-editor" :class="{ 'manager-cell-editor--pending': dirty }"
    :title="dirty ? '选择尚未确认，可打开下拉框继续调整' : ''" @click.stop @keydown.esc.capture.stop.prevent="closeDropdown">
    <el-select ref="selectRef" v-model="draft" :multiple="multiple" :collapse-tags="multiple" collapse-tags-tooltip
      filterable clearable size="small" class="inline-manager-select" popper-class="annotation-manager-select-popper"
      :loading="busy" :disabled="disabled || busy" :aria-label="`${roleLabel}${dirty ? '（未确认）' : ''}`"
      @change="handleDraftChange" @visible-change="opened = $event">
      <el-option v-for="user in selectOptions" :key="user.id" :value="user.id" :label="user.full_name || user.fullName || user.username" :disabled="user.unavailable" />
      <template #footer>
        <div class="manager-pending-actions" @keydown.esc.capture.stop.prevent="closeDropdown">
          <span class="manager-selection-count">已选 {{ draftIds.length }} 人</span>
          <el-button type="primary" size="small" :disabled="disabled || busy || !dirty" :aria-label="`确认${roleLabel}调整`" @click="save">确认调整</el-button>
          <el-button size="small" :disabled="busy" :aria-label="`取消${roleLabel}调整`" @click="cancelDraft">取消</el-button>
        </div>
      </template>
    </el-select>
    <ProjectClientManagerHistory v-if="!multiple" project-type="annotation" :project-id="row.id" />
  </div>
  <AnnotationManagerChangeReasonDialog ref="reasonDialog" :users="selectOptions" />
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { updateAnnotationProjectManagers } from '@/api/annotationProjects'
import { managerIds, sameManagers } from '@/utils/annotationManagerChange'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import AnnotationManagerChangeReasonDialog from './AnnotationManagerChangeReasonDialog.vue'
import ProjectClientManagerHistory from '@/components/common/ProjectClientManagerHistory.vue'
const props = defineProps({ row: { type: Object, required: true }, role: { type: String, required: true }, options: { type: Array, default: () => [] }, disabled: Boolean })
const emit = defineEmits(['updated'])
const multiple = computed(() => props.role === 'project_manager')
const roleLabel = computed(() => multiple.value ? '项目经理' : '客户经理')
const selectOptions = computed(() => {
  const users = [...props.options]
  for (const id of managerIds(props.row, props.role)) {
    if (users.some(user => user.id === id)) continue
    const assignment = props.row.roleAssignments?.find(item => (item.assigneeId || item.assignee_id) === id)
    users.push({ id, fullName: multiple.value ? (assignment?.assigneeName || assignment?.assignee_name || id) : (props.row.clientManagerName || id), unavailable: true })
  }
  return users
})
const busy = ref(false), opened = ref(false), draft = ref(), reasonDialog = ref(), selectRef = ref()
const savedIds = ref([]), savedVersion = ref(), previouslyAssigned = ref(false)
const draftIds = computed(() => multiple.value ? (draft.value || []) : (draft.value ? [draft.value] : []))
const dirty = computed(() => !sameManagers(savedIds.value, draftIds.value))
const reset = () => {
  savedIds.value = managerIds(props.row, props.role)
  savedVersion.value = props.row.updatedAt
  previouslyAssigned.value = savedIds.value.length > 0 || Boolean(props.row.managerAssignmentHistory?.[props.role])
  draft.value = multiple.value ? [...savedIds.value] : (savedIds.value[0] || null)
}
const closeDropdown = () => selectRef.value?.blur()
const cancelDraft = () => { closeDropdown(); reset() }
const handleDraftChange = async () => {
  if (multiple.value) return
  // 单选默认选中即关闭，暂存模式需继续展示底部确认操作。
  await nextTick()
  if (!opened.value && !busy.value && !props.disabled) selectRef.value?.toggleMenu()
}
watch(() => [props.row, props.row.updatedAt, managerIds(props.row, props.role).join(',')], () => { if (!busy.value) reset() }, { immediate: true })
async function save() {
  if (busy.value || props.disabled) return
  const previous = [...savedIds.value]
  const next = [...draftIds.value]
  if (sameManagers(previous, next)) return
  const expectedUpdatedAt = savedVersion.value
  closeDropdown()
  busy.value = true
  try {
    const requiresReason = !multiple.value || previouslyAssigned.value
    const reason = requiresReason ? await reasonDialog.value.request({ orderNo: props.row.orderNo, changes: [{
      role: props.role, label: roleLabel.value, previous, next,
    }] }) : null
    if (requiresReason && reason === null) return
    const updated = await updateAnnotationProjectManagers(props.row.id, {
      [multiple.value ? 'projectManagerIds' : 'clientManagerId']: multiple.value ? next : (next[0] || null),
      reason, expectedUpdatedAt,
    })
    Object.assign(props.row, updated)
    ElMessage.success(`${multiple.value ? '项目经理' : '客户经理'}已更新`)
    emit('updated', updated)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '负责人更新失败'))
    if (error?.status === 409 || error?.response?.status === 409) emit('updated')
  } finally { busy.value = false; reset() }
}
</script>

<style scoped>
.inline-manager-select{width:100%}
.manager-cell-editor{width:100%;min-width:0}
.manager-pending-actions{display:flex;align-items:center;gap:8px;line-height:24px}
.manager-selection-count{margin-right:auto;white-space:nowrap;color:var(--el-text-color-secondary);font-size:12px}
.manager-pending-actions .el-button+.el-button{margin-left:0}
.manager-cell-editor--pending :deep(.el-select__wrapper){box-shadow:0 0 0 1px var(--el-color-primary) inset}
:global(.annotation-manager-select-popper){min-width:min(280px,calc(100vw - 32px))!important;max-width:calc(100vw - 32px)}
</style>
