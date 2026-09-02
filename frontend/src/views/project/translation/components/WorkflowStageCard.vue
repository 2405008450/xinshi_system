<template>
  <el-card v-if="currentProject" class="stage-card" shadow="never">
    <template #header>
      <div class="stage-card-header">
        <span class="stage-name">
          当前阶段：{{ currentStage?.title || '-' }}
          <el-tag
            v-if="currentEntityType === 'suborder'"
            type="warning"
            size="small"
            style="margin-left: 6px"
          >
            [子订单] {{ currentSubOrder?.subOrderNo || currentSubOrder?.sub_order_no }}
          </el-tag>
        </span>
        <el-tag type="primary" effect="plain">{{ currentStage?.role || '-' }}</el-tag>
        <el-tag v-if="workflowState.currentAssigneeUserName" type="success" effect="plain" class="assignee-tag">
          当前负责人：{{ workflowState.currentAssigneeUserName }}
        </el-tag>
        <el-tag v-else-if="workflowState.groupAssignRole" type="warning" effect="plain" class="assignee-tag">
          同组指派：{{ workflowState.groupAssignRole }}
        </el-tag>
        <el-tag v-if="workflowState.difficulty" type="info" effect="plain" class="difficulty-tag">
          难度：{{ difficultyLabel(workflowState.difficulty) }}
        </el-tag>
      </div>
    </template>

    <div v-if="isAtReception && !workflowState.difficulty" class="stage-difficulty">
      <div class="section-label">来稿难度评级（客户专员初步判断）</div>
      <p class="handover-hint">请根据来稿情况选择难度，将决定后续流程是否经过「项目经理」「译审」环节。</p>
      <el-radio-group v-model="uiState.pendingDifficulty" class="difficulty-radio">
        <el-radio label="simple">简单（直接指派 HR）</el-radio>
        <el-radio label="normal">普通（跳过译审）</el-radio>
        <el-radio label="complex">复杂（全流程）</el-radio>
      </el-radio-group>

      <div class="section-label">文件是否可编辑</div>
      <p class="handover-hint">不可编辑文件将自动增加「预处理」阶段（由排版专员承接）。</p>
      <el-radio-group v-model="uiState.pendingFileEditable" class="difficulty-radio">
        <el-radio :label="true">无需预处理</el-radio>
        <el-radio :label="false">需要预处理</el-radio>
      </el-radio-group>

      <div v-if="currentStageEditableFields.length" class="stage-progress">
        <div class="section-label">本阶段进度填写</div>
        <p class="handover-hint">请填写接稿阶段的关键进度信息，提交后将传递给下一阶段查看。</p>
        <AppForm :disabled="!canOperateCurrentStage" label-width="130px" size="small" class="stage-form">
          <template v-for="field in currentStageEditableFields" :key="field.key">
            <el-form-item :label="field.label">
              <el-date-picker
                v-if="field.type === 'date'"
                v-model="stageFormData[field.key]"
                type="datetime"
                placeholder="请选择日期时间"
                format="YYYY-MM-DD HH:mm"
                value-format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
                time-format="HH:mm"
                :show-now="true"
                :show-confirm="true"
                :show-footer="true"
              />
              <el-select
                v-else-if="field.type === 'select'"
                v-model="stageFormData[field.key]"
                placeholder="请选择"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="option in field.options"
                  :key="typeof option === 'object' ? option.value : option"
                  :label="typeof option === 'object' ? option.label : option"
                  :value="typeof option === 'object' ? option.value : option"
                />
              </el-select>
              <el-input v-else v-model="stageFormData[field.key]" placeholder="请输入" />
            </el-form-item>
          </template>
        </AppForm>
        <div class="stage-actions">
          <el-button type="info" plain :disabled="!canOperateCurrentStage" @click="$emit('save-progress')">
            更新本阶段进度
          </el-button>
        </div>
      </div>

      <div class="section-label">处理备注 / 交接留言</div>
      <p class="handover-hint">向下一阶段负责人传递关键信息，提交后将推进流程并锁定本阶段备注。</p>
      <el-input
        v-model="uiState.handoverNote"
        type="textarea"
        :rows="4"
        placeholder="请输入本阶段处理说明、注意事项或交接给下一阶段的留言..."
        maxlength="500"
        show-word-limit
      />

      <template v-if="nextStageAfterReception">
        <div class="section-label">下一环节负责人</div>
        <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageAfterReception.title }}」，或选择同组指派给整个角色组。</p>
        <el-radio-group v-model="uiState.assignMode" class="assign-mode-radio" style="margin-bottom: 12px">
          <el-radio-button label="personal">指定个人</el-radio-button>
          <el-radio-button label="group">同组指派</el-radio-button>
        </el-radio-group>
        <template v-if="uiState.assignMode === 'personal'">
          <el-select
            v-model="uiState.nextAssigneeUserId"
            placeholder="请选择下一环节负责人"
            filterable
            clearable
            style="width: 100%; margin-bottom: 12px"
            :loading="nextStageUsersLoading"
          >
            <el-option
              v-for="user in nextStageUsers"
              :key="user.id"
              :label="user.is_on_leave ? `${user.full_name || user.username || user.id}（${user.assignment_disabled_reason || '请假中'}）` : (user.full_name || user.username || user.id)"
              :value="user.id"
              :disabled="user.is_on_leave"
            />
          </el-select>
        </template>
        <template v-else>
          <el-select
            v-model="uiState.groupAssignRole"
            placeholder="请选择要指派的角色组"
            style="width: 100%; margin-bottom: 12px"
          >
            <el-option v-for="role in nextStageRoleOptions" :key="role" :label="role" :value="role" />
          </el-select>
          <el-alert v-if="uiState.groupAssignRole" type="info" :closable="false" style="margin-bottom: 12px">
            <template #title>将指派给所有「{{ uiState.groupAssignRole }}」角色的成员，该组所有成员均可在「待我处理」中看到此任务</template>
          </el-alert>
        </template>
      </template>

      <div v-if="!canOperateCurrentStage" class="stage-permission-hint">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>仅客户专员或项目经理可设定难度</template>
        </el-alert>
      </div>
      <div v-else class="stage-actions">
        <p v-if="!uiState.pendingDifficulty || uiState.pendingFileEditable === null || !receptionAssignReady" class="action-hint">
          请先选择难度与文件是否可编辑，再选择下一环节负责人后即可点击下方按钮提交。
        </p>
        <el-button
          type="primary"
          :disabled="!uiState.pendingDifficulty || uiState.pendingFileEditable === null || !receptionAssignReady"
          @click="$emit('confirm-difficulty')"
        >
          确认难度并进入下一环节
        </el-button>
      </div>
    </div>

    <template v-else>
      <div v-if="currentStageEditableFields.length && !isCurrentStageDone" class="stage-progress">
        <div class="section-label">本阶段进度填写</div>
        <p class="handover-hint">请填写本阶段的关键进度信息，提交后将传递给下一阶段查看。</p>
        <AppForm :disabled="!canOperateCurrentStage" label-width="130px" size="small" class="stage-form">
          <template v-for="field in currentStageEditableFields" :key="field.key">
            <el-form-item :label="field.label">
              <el-date-picker
                v-if="field.type === 'date'"
                v-model="stageFormData[field.key]"
                type="datetime"
                placeholder="请选择日期时间"
                format="YYYY-MM-DD HH:mm"
                value-format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
                time-format="HH:mm"
                :show-now="true"
                :show-confirm="true"
                :show-footer="true"
              />
              <el-select
                v-else-if="field.type === 'select'"
                v-model="stageFormData[field.key]"
                placeholder="请选择"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="option in field.options"
                  :key="typeof option === 'object' ? option.value : option"
                  :label="typeof option === 'object' ? option.label : option"
                  :value="typeof option === 'object' ? option.value : option"
                />
              </el-select>
              <el-input v-else v-model="stageFormData[field.key]" placeholder="请输入" />
            </el-form-item>
          </template>
        </AppForm>
        <div class="stage-actions">
          <el-button type="info" plain :disabled="!canOperateCurrentStage" @click="$emit('save-progress')">
            更新本阶段进度
          </el-button>
        </div>
      </div>

      <div v-if="currentStageEditableFields.length && isCurrentStageDone" class="stage-progress">
        <div class="section-label">本阶段已填写的进度信息</div>
        <el-descriptions :column="2" border size="small">
          <template v-for="field in currentStageEditableFields" :key="field.key">
            <el-descriptions-item :label="field.label">
              <span class="readonly-value">{{ resolveFieldValue(field.key) }}</span>
            </el-descriptions-item>
          </template>
        </el-descriptions>
      </div>

      <div v-if="!isCurrentStageDone" class="stage-handover">
        <div class="section-label">处理备注 / 交接留言</div>
        <p class="handover-hint">向下一阶段负责人传递关键信息，提交后将推进流程并锁定本阶段备注。</p>
        <el-input
          v-model="uiState.handoverNote"
          type="textarea"
          :rows="4"
          placeholder="请输入本阶段处理说明、注意事项或交接给下一阶段的留言..."
          maxlength="500"
          show-word-limit
        />
        <template v-if="nextStageForAssignee">
          <div class="section-label">下一环节负责人</div>
          <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageForAssignee.title }}」，或选择同组指派给整个角色组。</p>
          <el-radio-group v-model="uiState.assignMode" class="assign-mode-radio" style="margin-bottom: 12px">
            <el-radio-button label="personal">指定个人</el-radio-button>
            <el-radio-button label="group">同组指派</el-radio-button>
          </el-radio-group>
          <template v-if="uiState.assignMode === 'personal'">
            <el-select
              v-model="uiState.nextAssigneeUserId"
              placeholder="请选择下一环节负责人"
              filterable
              clearable
              style="width: 100%; margin-bottom: 12px"
              :loading="nextStageUsersLoading"
            >
              <el-option
                v-for="user in nextStageUsers"
                :key="user.id"
                :label="user.is_on_leave ? `${user.full_name || user.username || user.id}（${user.assignment_disabled_reason || '请假中'}）` : (user.full_name || user.username || user.id)"
                :value="user.id"
                :disabled="user.is_on_leave"
              />
            </el-select>
          </template>
          <template v-else>
            <el-select
              v-model="uiState.groupAssignRole"
              placeholder="请选择要指派的角色组"
              style="width: 100%; margin-bottom: 12px"
            >
              <el-option v-for="role in nextStageRoleOptions" :key="role" :label="role" :value="role" />
            </el-select>
            <el-alert v-if="uiState.groupAssignRole" type="info" :closable="false" style="margin-bottom: 12px">
              <template #title>将指派给所有「{{ uiState.groupAssignRole }}」角色的成员，该组所有成员均可在「待我处理」中看到此任务</template>
            </el-alert>
          </template>
        </template>

        <div v-if="!canOperateCurrentStage" class="stage-permission-hint">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>您不是当前阶段的负责人，无法执行操作</template>
          </el-alert>
        </div>
        <div v-else class="stage-actions stage-actions-multi">
          <el-button type="primary" :disabled="!!nextStageForAssignee && !transitionAssignReady" @click="$emit('complete-stage')">
            完成本阶段并提交
          </el-button>
          <el-button v-if="canRollbackOne" type="warning" plain @click="$emit('rollback', 1, false)">
            打回上一环节
          </el-button>
          <el-button v-if="canRollbackTwo" type="warning" plain @click="$emit('rollback', 2, false)">
            打回上两环节
          </el-button>
          <el-button v-if="canRollbackToStart" type="danger" plain @click="$emit('rollback', 0, true)">
            打回初始节点
          </el-button>
        </div>
      </div>

      <div v-else class="stage-handover-readonly">
        <div class="section-label">本阶段交接留言</div>
        <div class="readonly-note">{{ stageNoteForCurrentStage || '（无）' }}</div>
        <div v-if="canRollbackOne || canRollbackTwo || canRollbackToStart" class="stage-actions" style="margin-top: 12px">
          <el-button v-if="canRollbackOne" type="warning" plain @click="$emit('rollback', 1, false)">
            打回上一环节
          </el-button>
          <el-button v-if="canRollbackTwo" type="warning" plain @click="$emit('rollback', 2, false)">
            打回上两环节
          </el-button>
          <el-button v-if="canRollbackToStart" type="danger" plain @click="$emit('rollback', 0, true)">
            打回初始节点
          </el-button>
        </div>
      </div>
    </template>
  </el-card>
</template>

<script setup>
defineEmits(['save-progress', 'confirm-difficulty', 'complete-stage', 'rollback'])

defineProps({
  currentProject: {
    type: Object,
    default: null
  },
  currentEntityType: {
    type: String,
    default: 'project'
  },
  currentSubOrder: {
    type: Object,
    default: null
  },
  workflowState: {
    type: Object,
    default: () => ({})
  },
  currentStage: {
    type: Object,
    default: null
  },
  currentStageEditableFields: {
    type: Array,
    default: () => []
  },
  canOperateCurrentStage: {
    type: Boolean,
    default: false
  },
  isAtReception: {
    type: Boolean,
    default: false
  },
  isCurrentStageDone: {
    type: Boolean,
    default: false
  },
  stageNoteForCurrentStage: {
    type: String,
    default: ''
  },
  nextStageAfterReception: {
    type: Object,
    default: null
  },
  nextStageForAssignee: {
    type: Object,
    default: null
  },
  nextStageRoleOptions: {
    type: Array,
    default: () => []
  },
  nextStageUsers: {
    type: Array,
    default: () => []
  },
  nextStageUsersLoading: {
    type: Boolean,
    default: false
  },
  receptionAssignReady: {
    type: Boolean,
    default: false
  },
  transitionAssignReady: {
    type: Boolean,
    default: false
  },
  canRollbackOne: {
    type: Boolean,
    default: false
  },
  canRollbackTwo: {
    type: Boolean,
    default: false
  },
  canRollbackToStart: {
    type: Boolean,
    default: false
  },
  resolveFieldValue: {
    type: Function,
    required: true
  },
  difficultyLabel: {
    type: Function,
    required: true
  },
  uiState: {
    type: Object,
    required: true
  },
  stageFormData: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.stage-card {
  margin-bottom: 20px;
  border: 1px solid var(--el-border-color-lighter);
}

.stage-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.stage-name {
  font-weight: 600;
  font-size: 15px;
}

.assignee-tag {
  margin-left: 4px;
}

.difficulty-tag {
  margin-left: auto;
}

.section-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.stage-difficulty .handover-hint,
.stage-handover .handover-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.difficulty-radio {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.assign-mode-radio {
  display: flex;
  gap: 0;
}

.stage-difficulty .action-hint {
  font-size: 13px;
  color: var(--el-color-warning);
  margin: 0 0 10px 0;
}

.stage-progress {
  margin-bottom: 20px;
}

.stage-form {
  max-width: 600px;
}

.stage-form .el-form-item {
  margin-bottom: 14px;
}

.readonly-value {
  color: var(--el-text-color-regular);
}

.stage-handover-readonly .readonly-note {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 0 0 8px 0;
}

.stage-actions {
  margin-top: 12px;
}

.stage-actions-multi {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.readonly-note {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
