<template>
  <el-popover trigger="click" placement="left" :width="460">
    <template #reference>
      <el-button type="primary" link size="small" class="assignee-trigger" @click.stop>
        {{ triggerLabel }}
      </el-button>
    </template>

    <div class="role-popover">
      <div class="role-popover__title">项目负责人</div>
      <el-descriptions :column="1" border size="small" class="current-assignee-summary">
        <el-descriptions-item label="当前阶段角色">
          {{ currentStageRoleName || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="当前处理人">
          <el-tag v-if="currentAssigneeName" type="success" size="small" effect="plain">
            {{ currentAssigneeName }}
          </el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">
            {{ groupAssignRole || currentStageRoleName || '对应角色' }}角色池
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="role-list">
        <div
          v-for="role in normalizedRoles"
          :key="role.roleCode"
          class="role-list__item"
          :class="{ 'is-current': role.roleCode === currentStageRoleCode }"
        >
          <div class="role-list__label">
            <span>{{ role.roleName }}</span>
            <el-tag v-if="role.roleCode === currentStageRoleCode" size="small" type="primary">当前阶段</el-tag>
          </div>
          <el-tag v-if="role.assigneeId" type="success" size="small" effect="plain">
            {{ role.assigneeName || '已绑定' }}
          </el-tag>
          <el-tag v-else type="info" size="small" effect="plain">角色池</el-tag>
        </div>
      </div>
      <div class="role-popover__hint">
        客户专员显示当前接单阶段的承接人；临时任务交接只改变当前处理人，不修改其他项目固定角色。
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed } from 'vue'

const PROJECT_ROLES = [
  { roleCode: 'project_manager', roleName: '项目经理' },
  { roleCode: 'customer_specialist', roleName: '客户专员' },
  { roleCode: 'project_specialist', roleName: '项目专员' },
  { roleCode: 'project_assistant', roleName: '项目助理' },
  { roleCode: 'layout_specialist', roleName: '排版专员' }
]

const props = defineProps({
  currentAssigneeName: { type: String, default: '' },
  currentStageRoleCode: { type: String, default: '' },
  currentStageRoleName: { type: String, default: '' },
  groupAssignRole: { type: String, default: '' },
  roleAssignments: { type: Array, default: () => [] }
})

const normalizedRoles = computed(() => {
  const byCode = Object.fromEntries((props.roleAssignments || []).map((item) => [
    item.roleCode || item.role_code,
    item
  ]))
  return PROJECT_ROLES.map((definition) => {
    const source = byCode[definition.roleCode] || {}
    const isCurrentCustomerSpecialist = definition.roleCode === 'customer_specialist'
      && props.currentStageRoleCode === definition.roleCode
    const currentStageAssigneeId = isCurrentCustomerSpecialist && props.currentAssigneeName
      ? 'current-stage-assignee'
      : ''
    return {
      ...definition,
      roleName: source.roleName || source.role_name || definition.roleName,
      assigneeId: source.assigneeId || source.assignee_id || currentStageAssigneeId,
      assigneeName: source.assigneeName || source.assignee_name
        || (isCurrentCustomerSpecialist ? props.currentAssigneeName : '')
    }
  })
})

const triggerLabel = computed(() => {
  if (props.currentAssigneeName) return props.currentAssigneeName
  return `${props.groupAssignRole || props.currentStageRoleName || '对应角色'}角色池`
})
</script>

<style scoped>
.assignee-trigger {
  max-width: 100%;
  padding: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-popover {
  display: grid;
  gap: 12px;
}

.role-popover__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.role-list {
  display: grid;
  gap: 8px;
}

.role-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.role-list__item.is-current {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.role-list__label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.role-popover__hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
</style>
