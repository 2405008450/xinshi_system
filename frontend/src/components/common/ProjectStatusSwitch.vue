<template>
  <div class="project-status-switch" @click.stop>
    <el-dropdown
      v-if="canSwitch"
      trigger="click"
      placement="bottom-start"
      max-height="min(360px, calc(100vh - 32px))"
      popper-class="project-status-dropdown-popper"
      :popper-options="STATUS_DROPDOWN_POPPER_OPTIONS"
      :disabled="saving"
      @command="changeStatus"
    >
      <el-tag
        :type="statusType"
        size="small"
        class="status-switch-tag"
        :class="{ 'is-updating': saving }"
      >
        <span class="status-switch-text">{{ statusLabel }}</span>
        <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
      </el-tag>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="item in options"
            :key="item.value"
            :command="item.value"
            :disabled="isOptionDisabled(item.value) || saving"
          >
            <span class="status-option-row">
              <el-tag :type="typeOf(item.value)" size="small" effect="plain">{{ item.label }}</el-tag>
              <el-icon v-if="item.value === normalizedStatus" class="status-current-icon"><Check /></el-icon>
            </span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
    <el-tag v-else :type="statusType" size="small" effect="plain">{{ statusLabel }}</el-tag>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretBottom, Check } from '@element-plus/icons-vue'
import { updateProject } from '@/api/projects'
import { updateInterpretationProjectStatus } from '@/api/interpretationProjects'
import { updateAnnotationProjectStatus } from '@/api/annotationProjects'
import { patchRecruitmentProjectStatus } from '@/api/recruitmentProjects'
import {
  getProjectStatusLabel,
  getProjectStatusOptions,
  getProjectStatusType,
  isProjectStatusOptionDisabled,
  normalizeProjectStatus,
} from '@/utils/projectStatus'

// 使用视口固定定位，避免长菜单成为页面滚动溢出的一部分；
// 菜单高度由 el-dropdown 的 max-height 控制，超出后在菜单内部滚动。
const STATUS_DROPDOWN_POPPER_OPTIONS = {
  strategy: 'fixed',
  modifiers: [
    {
      name: 'preventOverflow',
      options: {
        rootBoundary: 'viewport',
        padding: 8,
      },
    },
  ],
}

const props = defineProps({
  projectType: { type: String, default: 'translation' },
  projectId: { type: [String, Number], default: '' },
  status: { type: String, default: '' },
  writable: { type: Boolean, default: false },
})

const emit = defineEmits(['updated'])
const saving = ref(false)
const options = computed(() => getProjectStatusOptions(props.projectType))
const normalizedStatus = computed(() => normalizeProjectStatus(props.projectType, props.status))
const statusLabel = computed(() => getProjectStatusLabel(props.projectType, props.status))
const statusType = computed(() => getProjectStatusType(props.projectType, props.status))
const canSwitch = computed(() => props.writable && !!props.projectId)

function typeOf(value) {
  return getProjectStatusType(props.projectType, value)
}

function isOptionDisabled(value) {
  return isProjectStatusOptionDisabled(props.projectType, value, props.status)
}

async function persistStatus(projectType, projectId, nextStatus) {
  if (projectType === 'interpretation') {
    return updateInterpretationProjectStatus(projectId, nextStatus)
  }
  if (projectType === 'annotation') {
    return updateAnnotationProjectStatus(projectId, { projectStatus: nextStatus })
  }
  if (projectType === 'recruitment') {
    return patchRecruitmentProjectStatus(projectId, nextStatus)
  }
  return updateProject(projectId, { projectStatus: nextStatus })
}

async function changeStatus(value) {
  const nextStatus = normalizeProjectStatus(props.projectType, value)
  if (!props.projectId || !nextStatus || nextStatus === normalizedStatus.value || saving.value) return
  saving.value = true
  try {
    const updated = await persistStatus(props.projectType, props.projectId, nextStatus)
    const savedStatus = updated?.projectStatus || updated?.project_status || nextStatus
    ElMessage.success('项目状态已更新')
    emit('updated', {
      projectId: props.projectId,
      projectType: props.projectType,
      status: savedStatus,
      project: updated,
    })
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.detail || error?.message || '项目状态更新失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.project-status-switch {
  display: inline-flex;
  max-width: 100%;
  vertical-align: middle;
}

.status-switch-tag.el-tag {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  cursor: pointer;
  user-select: none;
  vertical-align: middle;
  transition: opacity 0.15s ease;
}

.status-switch-tag :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;
  line-height: 1;
}

.status-switch-text {
  line-height: 1;
}

.status-switch-caret {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  margin: 0;
  font-size: 10px;
}

.status-switch-tag:hover {
  opacity: 0.85;
}

.status-switch-tag.is-updating {
  pointer-events: none;
  opacity: 0.55;
}

.status-option-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.status-current-icon {
  color: var(--el-color-primary);
}

:global(.project-status-dropdown-popper .el-scrollbar__wrap) {
  overscroll-behavior: contain;
}
</style>
