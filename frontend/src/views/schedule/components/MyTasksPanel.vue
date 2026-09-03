<template>
  <div class="section-block" :class="{ 'is-multi-page': filteredTasks.length > PAGE_SIZE }">
    <div class="task-toolbar">
      <div class="task-toolbar__actions">
        <TableColumnSettings
          v-model="visibleColumnKeys"
          title="执行层字段"
          hint="勾选结果仅对当前用户生效；序号、跟进明细和操作列固定保留。"
          :columns="taskTableColumns"
          :column-count="2"
          @reset="resetColumns"
        />
        <el-button
          v-if="canOperateWorkflow"
          type="primary"
          size="small"
          :disabled="!directSelectedTasks.length"
          @click="openHandoverDialog"
        >
          交接所选任务（{{ directSelectedTasks.length }}）
        </el-button>
        <el-button
          v-if="canOperateWorkflow"
          type="primary"
          plain
          size="small"
          :loading="claimingRolePool"
          :disabled="!rolePoolSelectedTasks.length"
          @click="claimSelectedRolePoolTasks"
        >认领任务（{{ rolePoolSelectedTasks.length }}）</el-button>
        <el-button v-if="canOperateWorkflow" plain size="small" @click="openClaimDialog">继承他人任务</el-button>
      </div>
    </div>

    <el-table
      ref="taskTableRef"
      v-if="tasksList.length"
      :data="pagedTasks"
      border
      size="small"
      class="data-table workbench-data-table row-click-select-table"
      :row-key="taskKey"
      :expand-row-keys="expandedTaskKeys"
      :row-class-name="rowClassName"
      @expand-change="handleTaskExpandChange"
      @selection-change="selectedTasks = $event"
      @row-click="toggleTaskRowSelection"
    >
      <template #empty>
        <span class="table-filter-empty">没有符合当前筛选条件的任务，可调整列头筛选条件</span>
      </template>
      <el-table-column type="expand" width="1" class-name="task-expand-column" label-class-name="task-expand-column">
        <template #default="{ row }">
          <div v-if="hasExecutionItems(row)" class="translator-execution-panel">
            <div class="translator-execution-panel__header">
              <div class="translator-execution-panel__summary">
                <strong>译员执行明细</strong>
                <el-tag v-if="row.translator_execution.attention_count" type="warning" size="small">
                  待回稿 {{ row.translator_execution.attention_count }} 项
                </el-tag>
                <el-tag v-if="row.translator_execution.overdue_count" type="danger" size="small">
                  已逾期 {{ row.translator_execution.overdue_count }} 项
                </el-tag>
              </div>
              <el-button
                v-if="hasHiddenExecutionItems(row)"
                type="primary"
                link
                size="small"
                @click.stop="toggleAllExecutionItems(row)"
              >
                {{ isShowingAllExecutionItems(row) ? '只看待回稿' : `查看全部执行明细（${row.translator_execution.items.length}）` }}
              </el-button>
            </div>
            <el-table :data="getVisibleExecutionItems(row)" border size="small" class="translator-execution-table">
              <el-table-column label="订单" min-width="210">
                <template #default="{ row: item }">
                  <div class="execution-order-cell">
                    <div>
                      <el-tag :type="item.entity_type === 'suborder' ? 'warning' : 'info'" size="small" effect="plain">
                        {{ item.entity_type === 'suborder' ? '子订单' : '母订单' }}
                      </el-tag>
                      <span>{{ item.order_no }}</span>
                    </div>
                    <span v-if="item.sub_project_name" class="execution-order-cell__name">{{ item.sub_project_name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="译员回稿时间" min-width="250">
                <template #default="{ row: item }">
                  <div v-if="item.assigned_translators.length" class="execution-translator-list">
                    <div v-for="translator in item.assigned_translators" :key="translator.arrangement_id" class="execution-translator-item">
                      <span class="execution-translator-item__name">{{ translator.translator_name }}</span>
                      <DeadlineHintCell
                        v-if="translator.translator_return_time"
                        :deadline="translator.translator_return_time"
                        :status="item.status"
                        mode="translator"
                      />
                      <el-tag v-else type="warning" size="small" effect="plain">未设置回稿时间</el-tag>
                    </div>
                  </div>
                  <span v-else class="muted-text">未安排译员</span>
                </template>
              </el-table-column>
              <el-table-column label="任务完成情况" min-width="240">
                <template #default="{ row: item }">
                  <div class="execution-completion-list">
                    <div v-for="translator in item.assigned_translators" :key="translator.arrangement_id">
                      <span v-if="translator.completion_remarks">{{ translator.translator_name }}：{{ translator.completion_remarks }}</span>
                    </div>
                    <span v-if="!hasEntityCompletion(item)" class="muted-text">-</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row: item }">
                  <el-tag :type="executionStatusType(item.status)" size="small">{{ executionStatusLabel(item.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right" align="center">
                <template #default="{ row: item }">
                  <el-button v-if="canOpenManuscript" type="primary" link size="small" @click.stop="openManuscript(row, item)">
                    进入稿件安排
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column type="selection" :width="WORKBENCH_COLUMN_WIDTHS.selection" :selectable="isTaskSelectable" />
      <el-table-column
        type="index"
        label="序号"
        :width="WORKBENCH_COLUMN_WIDTHS.index"
        :index="getTaskIndex"
      />
      <el-table-column label="跟进" width="58" align="center">
        <template #default="{ row }">
          <el-badge v-if="hasExecutionItems(row)" :value="row.translator_execution.attention_count" :hidden="!row.translator_execution.attention_count" type="danger">
            <TableExpandButton
              :expanded="isTaskExpanded(row)"
              expand-label="展开译员执行明细"
              collapse-label="收起译员执行明细"
              @click="toggleTaskExpansion(row)"
            />
          </el-badge>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('orderNo')" prop="order_no" :label="WORKBENCH_FIELD_LABELS.orderNo" :width="WORKBENCH_COLUMN_WIDTHS.orderNo" show-overflow-tooltip />
      <el-table-column v-if="isColumnVisible('projectType')" :label="WORKBENCH_FIELD_LABELS.projectType" :width="WORKBENCH_COLUMN_WIDTHS.projectType">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.projectType"
            :active="!!searchForm.project_types.length"
            :width="220"
            @clear="searchForm.project_types = []"
          >
            <el-checkbox-group v-model="searchForm.project_types" class="project-type-filter-group">
              <el-checkbox
                v-for="option in WORKBENCH_PROJECT_TYPE_OPTIONS"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </el-checkbox>
            </el-checkbox-group>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }"><el-tag type="info" size="small" effect="plain">{{ row.project_type_label || '笔译项目' }}</el-tag></template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('projectTask')" :label="WORKBENCH_FIELD_LABELS.projectTask" :width="WORKBENCH_COLUMN_WIDTHS.projectTask">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.projectTask"
            :active="!!projectSearchKeyword"
            :width="240"
            @clear="searchForm.project = ''"
          >
            <el-input
              v-model="searchForm.project"
              placeholder="项目、子项目或订单号"
              clearable
              size="small"
              @change="normalizeProjectSearch"
            />
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <WorkbenchProjectTaskCell :row="row" />
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('client')" :label="WORKBENCH_FIELD_LABELS.client" :width="WORKBENCH_COLUMN_WIDTHS.client" show-overflow-tooltip>
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.client"
            :active="!!searchForm.client"
            :width="220"
            @clear="searchForm.client = ''"
          >
            <el-input
              v-model="searchForm.client"
              placeholder="客户全称或简称"
              clearable
              size="small"
            />
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">{{ row.client_short_name || '-' }}</template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('projectNode')" :label="WORKBENCH_FIELD_LABELS.projectNode" :width="WORKBENCH_COLUMN_WIDTHS.customerDeadline">
        <template #default="{ row }">
          <DeadlineHintCell :deadline="getTaskDeadline(row)" :status="row.project_status" />
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('projectStatus')" prop="project_status" :label="WORKBENCH_FIELD_LABELS.projectStatus" :width="WORKBENCH_COLUMN_WIDTHS.projectStatus">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.projectStatus"
            :active="!!searchForm.project_statuses.length"
            :width="260"
            @clear="searchForm.project_statuses = []"
          >
            <el-checkbox-group v-model="searchForm.project_statuses" class="project-status-filter-group">
              <el-checkbox
                v-for="option in projectStatusFilterOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}（{{ option.count }}）
              </el-checkbox>
            </el-checkbox-group>
            <div v-if="!projectStatusFilterOptions.length" class="column-filter-empty">暂无可筛选状态</div>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <ProjectStatusSwitch
            :project-type="resolveProjectType(row)"
            :project-id="resolveProjectId(row)"
            :status="row.project_status"
            :writable="canWriteProjects"
            @updated="handleProjectStatusUpdated(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('languageDirection')" prop="language_pair" :label="WORKBENCH_FIELD_LABELS.languageDirection" :width="WORKBENCH_COLUMN_WIDTHS.languagePair">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.languageDirection"
            :active="!!searchForm.language_pair"
            :width="220"
            @clear="searchForm.language_pair = ''"
          >
            <el-input
              v-model="searchForm.language_pair"
              placeholder="按语言方向筛选"
              clearable
              size="small"
            />
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <LanguagePairText :value="row.language_pair" />
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('translatorReturn')" :label="WORKBENCH_FIELD_LABELS.translatorReturn" :width="WORKBENCH_COLUMN_WIDTHS.translatorReturn">
        <template #default="{ row }">
          <div v-if="getTranslatorReturnSummary(row)" class="translator-return-summary">
            <span class="translator-return-summary__name">{{ getTranslatorReturnSummary(row).translatorName }}</span>
            <DeadlineHintCell
              v-if="getTranslatorReturnSummary(row).time"
              :deadline="getTranslatorReturnSummary(row).time"
              status="sent_to_translator"
              mode="translator"
            />
            <el-tag v-else type="warning" size="small" effect="plain">未设置回稿时间</el-tag>
            <span v-if="getAttentionTranslatorEntries(row).length > 1" class="translator-return-summary__extra">
              另 {{ getAttentionTranslatorEntries(row).length - 1 }} 位译员待回稿
            </span>
          </div>
          <span v-else>{{ row.translator_execution ? '暂无待回稿' : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('taskCompletion')" :label="WORKBENCH_FIELD_LABELS.taskCompletion" :width="WORKBENCH_COLUMN_WIDTHS.taskCompletion">
        <template #default="{ row }">
          <el-tooltip v-if="getCompletionSummaries(row).length" placement="top" effect="dark">
            <template #content>
              <div class="completion-summary-tooltip">
                <div v-for="(summary, index) in getCompletionSummaries(row)" :key="`${index}:${summary}`">{{ summary }}</div>
              </div>
            </template>
            <div class="completion-summary">
              <span class="completion-summary__text">{{ getCompletionSummaries(row)[0] }}</span>
              <span v-if="getCompletionSummaries(row).length > 1" class="completion-summary__count">+{{ getCompletionSummaries(row).length - 1 }}</span>
            </div>
          </el-tooltip>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('currentAssignee')" prop="current_assignee_name" :label="WORKBENCH_FIELD_LABELS.currentAssignee" :width="WORKBENCH_COLUMN_WIDTHS.currentAssignee">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.currentAssignee"
            :active="!!searchForm.assignees.length"
            :width="240"
            @clear="searchForm.assignees = []"
          >
            <el-checkbox-group v-model="searchForm.assignees" class="assignee-filter-group">
              <el-checkbox
                v-for="option in assigneeFilterOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}（{{ option.count }}）
              </el-checkbox>
            </el-checkbox-group>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <div class="assignee-cell">
            <ProjectRoleAssigneesPopover
              :current-assignee-name="row.current_assignee_name || ''"
              :current-stage-role-code="row.current_stage_role_code || ''"
              :current-stage-role-name="row.current_stage_role_name || ''"
              :group-assign-role="row.group_assign_role || ''"
              :role-assignments="row.role_assignments || []"
            />
            <el-tag v-if="row.transfer_mode === 'delegation'" :type="row.delegation_overdue ? 'danger' : 'primary'" size="small" effect="plain">
              代 {{ row.original_assignee_name || '原负责人' }} 处理{{ row.delegation_overdue ? ' · 已到期' : '' }}
            </el-tag>
            <span
              v-else-if="row.transfer_mode === 'permanent' && row.original_assignee_name"
              class="previous-assignee"
              :title="`前负责人：${row.original_assignee_name}`"
            >
              前 {{ row.original_assignee_name }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('currentRole')" prop="current_stage_role_name" :label="WORKBENCH_FIELD_LABELS.currentRole" :width="WORKBENCH_COLUMN_WIDTHS.currentRole" show-overflow-tooltip>
        <template #default="{ row }">{{ row.current_stage_role_name || formatStage(row.current_stage_role_code) }}</template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('assignmentMethod')" :label="WORKBENCH_FIELD_LABELS.assignmentMethod" :width="WORKBENCH_COLUMN_WIDTHS.assignmentMethod">
        <template #header>
          <ColumnHeaderFilter
            :label="WORKBENCH_FIELD_LABELS.assignmentMethod"
            :active="!!searchForm.assignment_scopes.length"
            :width="220"
            @clear="searchForm.assignment_scopes = []"
          >
            <el-checkbox-group v-model="searchForm.assignment_scopes" class="assignment-scope-filter-group">
              <el-checkbox
                v-for="option in assignmentScopeFilterOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}（{{ option.count }}）
              </el-checkbox>
            </el-checkbox-group>
          </ColumnHeaderFilter>
        </template>
        <template #default="{ row }">
          <el-tag :type="assignmentTagType(row)" size="small" effect="plain">
            {{ assignmentLabel(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="stageColumnEnabled" prop="current_stage_key" label="流程阶段（待启用）" width="145">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ formatStage(row.current_stage_key) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="WORKBENCH_FIELD_LABELS.operation" width="190" align="center" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="$emit('open-project', row)">进入项目</el-button>
          <el-button
            v-if="projectMessageEnabled && row.translation_project_id"
            type="primary"
            link
            size="small"
            @click="$emit('open-chat', row.translation_project_id)"
          >
            留言
          </el-button>
          <el-button v-if="row.assignment_type === 'direct'" type="success" link size="small" @click="$emit('record-work', row)">记进展</el-button>
          <el-button v-if="hasAction(row, 'return_delegation')" type="warning" link size="small" @click="returnDelegation(row)">归还任务</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="filteredTasks.length" class="task-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="PAGE_SIZE"
        :total="filteredTasks.length"
        layout="total, prev, pager, next"
        size="small"
        background
        @current-change="handlePageChange"
      />
    </div>
    <template v-if="!tasksList.length">
      <div v-if="currentUserName" class="empty-tip">暂无待处理任务或可认领的角色池任务。</div>
      <el-empty v-else description="请先登录，登录账号将用于匹配「我的任务」" />
    </template>

    <el-dialog v-model="handoverVisible" title="交接所选任务" width="720px" destroy-on-close>
      <el-alert
        :title="handoverTransferMode === 'delegation'
          ? `将 ${directSelectedTasks.length} 项${handoverRoleName || ''}任务临时委托给相同角色的其他负责人，接收人确认后生效。`
          : `将 ${directSelectedTasks.length} 项${handoverRoleName || ''}任务永久转交给相同角色的其他负责人，接收人确认后生效。`"
        type="warning"
        :closable="false"
        show-icon
        class="dialog-alert"
      />
      <AppForm label-width="92px">
        <el-form-item label="责任方式" required>
          <el-radio-group v-model="handoverTransferMode">
            <el-radio label="permanent">永久转交</el-radio>
            <el-radio label="delegation">临时代办</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="handoverTransferMode === 'delegation'" label="计划结束" required>
          <div class="delegation-end-field">
            <el-date-picker
              v-model="delegationEndAt"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="请选择计划结束时间"
              style="width: 100%"
              format="YYYY-MM-DD HH:mm"
              time-format="HH:mm"
              :show-now="true"
              :show-confirm="true"
              :show-footer="true"
            />
            <span>到期仅提醒，不会自动归还。</span>
          </div>
        </el-form-item>
        <el-form-item label="交接类型" required>
          <div class="handover-type-field">
            <el-radio-group v-model="handoverType">
              <el-radio label="daily_shift">每日班次交接</el-radio>
              <el-radio label="weekend_holiday">周末/节假日交接</el-radio>
              <el-radio label="leave_time_off">请假调休交接</el-radio>
              <el-radio label="other">其他</el-radio>
            </el-radio-group>
            <el-input
              v-if="handoverType === 'other'"
              v-model="handoverReasonDetail"
              maxlength="500"
              show-word-limit
              placeholder="请填写具体交接原因"
            />
          </div>
        </el-form-item>
        <el-form-item label="接收人" required>
          <el-select v-model="handoverTargetUserId" filterable placeholder="请选择可承接全部所选任务的用户" style="width: 100%">
            <el-option
              v-for="user in eligibleUsers"
              :key="user.id"
              :label="user.is_on_leave ? `${user.full_name || user.username}（${user.assignment_disabled_reason || '请假中'}）` : (user.full_name || user.username)"
              :value="user.id"
              :disabled="String(user.id) === currentUserId || user.is_on_leave"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交接留言">
          <TransferNoteEditor v-model="handoverNote" style="width: 100%" />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="handoverVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingHandover" :disabled="!canSubmitHandover" @click="submitHandover">
          发起交接
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="claimVisible" title="继承他人任务" width="1080px" destroy-on-close>
      <el-alert
        title="仅展示你具备当前阶段角色、且由其他用户直接负责的未完成任务；继承无需原负责人审批。"
        type="info"
        :closable="false"
        show-icon
        class="dialog-alert"
      />
      <AppForm :inline="true" class="claim-search">
        <el-form-item label="原负责人">
          <el-select v-model="claimFilters.ownerUserId" clearable filterable placeholder="全部" style="width: 180px" @change="loadTransferableTasks">
            <el-option v-for="owner in claimOwnerOptions" :key="owner.id" :label="owner.name" :value="owner.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="claimFilters.keyword"
            clearable
            placeholder="客户、项目或订单号"
            style="width: 240px"
            @input="onClaimKeywordInput"
            @keyup.enter="runClaimSearch"
            @clear="runClaimSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="claimLoading" @click="runClaimSearch">查询</el-button>
        </el-form-item>
      </AppForm>
      <el-table
        v-loading="claimLoading"
        :data="transferableTasks"
        border
        size="small"
        max-height="360"
        @selection-change="claimSelectedTasks = $event"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="current_assignee_name" label="原负责人" width="120" />
        <el-table-column prop="client_name" label="客户" min-width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="母项目" min-width="180" show-overflow-tooltip />
        <el-table-column prop="sub_project_name" label="子项目" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.sub_project_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="order_no" label="订单编号" width="165" />
        <el-table-column label="流程阶段（待启用）" width="145">
          <template #default="{ row }">{{ formatStage(row.current_stage_key) }}</template>
        </el-table-column>
      </el-table>
      <div class="claim-note">
        <div class="claim-note__label">继承留言（已选择 {{ claimSelectedTasks.length }} 项）</div>
        <TransferNoteEditor v-model="claimNote" />
      </div>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="warning" :loading="submittingClaim" :disabled="!claimSelectedTasks.length" @click="submitClaim">
          确认继承
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TransferNoteEditor from '@/components/TransferNoteEditor.vue'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import ProjectStatusSwitch from '@/components/common/ProjectStatusSwitch.vue'
import LanguagePairText from '@/components/common/LanguagePairText.vue'
import ColumnHeaderFilter from '@/components/common/ColumnHeaderFilter.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { WORKBENCH_COLUMN_WIDTHS } from '@/constants/workbenchColumns'
import {
  WORKBENCH_FIELD_LABELS,
  WORKBENCH_PROJECT_TYPE_LABELS,
  WORKBENCH_PROJECT_TYPE_OPTIONS,
  WORKBENCH_PROJECT_TYPE_VALUES
} from '@/constants/workbenchFields'
import { canViewManuscriptArrangements, hasPermission, hasRole } from '@/utils/permission'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { parseBusinessDateTime } from '@/utils/deadlineDisplay'
import {
  filterTranslatorExecutionItems,
  getAttentionTranslatorEntries,
  getTranslatorCompletionSummaries,
  getTranslatorExecutionRiskRank,
  getWorkbenchExecutionDefaultColumnKeys,
  getWorkbenchTaskKey,
  hasTranslatorExecutionItems,
  reconcileTranslatorExpandedKeys
} from '@/utils/workbenchTranslatorExecution'
import {
  getProjectStatusLabel,
  getProjectStatusType,
  normalizeProjectStatus,
  resolveProjectId,
  resolveProjectType
} from '@/utils/projectStatus'
import ProjectRoleAssigneesPopover from './ProjectRoleAssigneesPopover.vue'
import WorkbenchProjectTaskCell from './WorkbenchProjectTaskCell.vue'
import {
  DEADLINE_STATE,
  compareWorkItemsByDeadline,
  getWorkItemDeadline,
  getWorkItemDeadlineState,
  isWorkItemOpen
} from '@/utils/workItemDeadline'
import { isDefaultVisibleWorkItem, isRolePoolWorkItem } from '@/utils/workItemScope'
import {
  claimWorkflowTasksAPI,
  claimRolePoolTasksAPI,
  getEligibleTransferUsersAPI,
  getTransferableTasksAPI,
  handoverWorkflowTasksAPI,
  returnDelegatedTasksAPI
} from '@/api/workflow'

const STAGE_LABELS = {
  reception: '客户专员',
  layout_assign: '预处理',
  project_manager: '项目经理',
  project_specialist: '项目专员',
  project_assistant: '项目助理',
  review: '译审',
  special_qc: '专检',
  layout: '排版',
  completed: '完成'
}

function formatStage(stageKey) {
  return STAGE_LABELS[stageKey] || stageKey || '-'
}

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})

const emit = defineEmits(['open-chat', 'open-project', 'open-manuscript', 'record-work', 'refresh', 'visible-count-change'])
const canWriteProjects = hasPermission('projects:write')
const canOperateWorkflow = hasPermission(['projects:read', 'workflow:operate'])
const canOpenManuscript = canViewManuscriptArrangements()

const taskTableColumns = [
  { key: 'orderNo', label: WORKBENCH_FIELD_LABELS.orderNo },
  { key: 'projectType', label: WORKBENCH_FIELD_LABELS.projectType },
  { key: 'projectTask', label: WORKBENCH_FIELD_LABELS.projectTask },
  { key: 'client', label: WORKBENCH_FIELD_LABELS.client },
  { key: 'projectNode', label: WORKBENCH_FIELD_LABELS.projectNode },
  { key: 'projectStatus', label: WORKBENCH_FIELD_LABELS.projectStatus },
  { key: 'languageDirection', label: WORKBENCH_FIELD_LABELS.languageDirection },
  { key: 'translatorReturn', label: WORKBENCH_FIELD_LABELS.translatorReturn },
  { key: 'taskCompletion', label: WORKBENCH_FIELD_LABELS.taskCompletion },
  { key: 'currentAssignee', label: WORKBENCH_FIELD_LABELS.currentAssignee },
  { key: 'currentRole', label: WORKBENCH_FIELD_LABELS.currentRole },
  { key: 'assignmentMethod', label: WORKBENCH_FIELD_LABELS.assignmentMethod }
]
const taskDefaultColumnKeys = getWorkbenchExecutionDefaultColumnKeys(taskTableColumns, hasRole('项目助理'))
const {
  selectedKeys: visibleColumnKeys,
  isVisible: isColumnVisible,
  reset: resetColumns
} = useTableColumns(
  'workbench-execution-v1',
  taskTableColumns,
  taskDefaultColumnKeys
)

function handleProjectStatusUpdated(row, payload) {
  const projectId = String(payload?.projectId || resolveProjectId(row) || '')
  if (projectId) {
    props.tasksList.forEach((item) => {
      if (String(resolveProjectId(item)) === projectId) {
        item.project_status = payload.status
      }
    })
  } else {
    row.project_status = payload.status
  }
  emit('refresh')
}
// 项目留言板块尚未开放，保留入口代码便于后续启用。
const projectMessageEnabled = false
// 流程阶段功能待启用，主表默认隐藏该列以节省横向空间，启用时改为 true。
const stageColumnEnabled = false

const selectedTasks = ref([])
const currentPage = ref(1)
const PAGE_SIZE = 10
const claimingRolePool = ref(false)
const taskTableRef = ref(null)
const expandedTaskKeys = ref([])
const manuallyCollapsedTaskKeys = ref(new Set())
const showAllExecutionTaskKeys = ref(new Set())
const eligibleUsers = ref([])
const handoverVisible = ref(false)
const handoverTargetUserId = ref('')
const handoverType = ref('daily_shift')
const handoverReasonDetail = ref('')
const handoverTransferMode = ref('permanent')
const delegationEndAt = ref('')
const submittingHandover = ref(false)
const claimVisible = ref(false)
const claimLoading = ref(false)
const submittingClaim = ref(false)
const transferableTasks = ref([])
const claimSelectedTasks = ref([])
const currentUserId = (() => {
  try {
    return String(localStorage.getItem('user_id') || '')
  } catch {
    return ''
  }
})()

const taskKey = getWorkbenchTaskKey
const hasExecutionItems = hasTranslatorExecutionItems

function isTaskExpanded(row) {
  return expandedTaskKeys.value.includes(taskKey(row))
}

function toggleTaskExpansion(row) {
  if (!hasExecutionItems(row)) return
  const key = taskKey(row)
  const targetExpanded = !isTaskExpanded(row)
  if (targetExpanded) {
    manuallyCollapsedTaskKeys.value.delete(key)
    expandedTaskKeys.value = [...new Set([...expandedTaskKeys.value, key])]
  } else {
    manuallyCollapsedTaskKeys.value.add(key)
    expandedTaskKeys.value = expandedTaskKeys.value.filter(item => item !== key)
  }
}

function handleTaskExpandChange(row, expandedRows) {
  const key = taskKey(row)
  const expanded = expandedRows.some(item => taskKey(item) === key)
  if (expanded) {
    manuallyCollapsedTaskKeys.value.delete(key)
    expandedTaskKeys.value = [...new Set([...expandedTaskKeys.value, key])]
  } else {
    manuallyCollapsedTaskKeys.value.add(key)
    expandedTaskKeys.value = expandedTaskKeys.value.filter(item => item !== key)
  }
}

function isShowingAllExecutionItems(row) {
  return showAllExecutionTaskKeys.value.has(taskKey(row))
}

function toggleAllExecutionItems(row) {
  const key = taskKey(row)
  const next = new Set(showAllExecutionTaskKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  showAllExecutionTaskKeys.value = next
}

function getVisibleExecutionItems(row) {
  return filterTranslatorExecutionItems(row, isShowingAllExecutionItems(row))
}

function hasHiddenExecutionItems(row) {
  const items = row?.translator_execution?.items || []
  return Boolean(row?.translator_execution?.attention_count) && items.some(item => !item.needs_attention)
}

function getTranslatorReturnSummary(row) {
  return getAttentionTranslatorEntries(row)[0] || null
}

const getCompletionSummaries = getTranslatorCompletionSummaries

function hasEntityCompletion(item) {
  return (item?.assigned_translators || []).some(translator => String(translator.completion_remarks || '').trim())
}

function executionStatusLabel(status) {
  return getProjectStatusLabel('translation', status)
}

function executionStatusType(status) {
  return getProjectStatusType('translation', status)
}

function openManuscript(task, item) {
  emit('open-manuscript', {
    projectId: task.translation_project_id || task.project_id,
    entityType: item.entity_type,
    subOrderId: item.entity_type === 'suborder' ? item.entity_id : undefined,
    orderNo: item.order_no
  })
}

const emptyNote = () => ({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  attachments: []
})
const handoverNote = ref(emptyNote())
const claimNote = ref(emptyNote())
const claimFilters = reactive({ ownerUserId: '', keyword: '' })
const SEARCH_DEBOUNCE_MS = 400
let claimSearchTimer = null
let claimRequestId = 0
let claimController = null

function projectStatusFilterKey(row) {
  const projectType = resolveProjectType(row)
  return `${projectType}:${normalizeProjectStatus(projectType, row?.project_status)}`
}

function isValidStoredStatusKey(value) {
  if (typeof value !== 'string') return false
  const [projectType, status] = value.split(':', 2)
  return WORKBENCH_PROJECT_TYPE_VALUES.includes(projectType) && !!status
}

function assigneeFilterKey(row) {
  if (row?.current_assignee_id) return `user:${row.current_assignee_id}`
  if (row?.current_assignee_name) return `name:${row.current_assignee_name}`
  return 'unassigned'
}

function isValidStoredAssigneeKey(value) {
  return typeof value === 'string' && (
    value === 'unassigned' || value.startsWith('user:') || value.startsWith('name:')
  )
}

const ASSIGNMENT_SCOPE_DEFINITIONS = [
  { value: 'mine', label: '我的任务' },
  { value: 'role_pool', label: '角色池任务' },
  { value: 'delegated_out', label: '我已委托' },
  { value: 'overview', label: '全局查看' }
]

function isValidStoredAssignmentScope(value) {
  return ASSIGNMENT_SCOPE_DEFINITIONS.some(option => option.value === value)
}

// 筛选条件按“页面 + 当前用户”持久化，不同登录用户互不影响（例如只负责口译项目的用户）
const FILTER_STORAGE_KEY = `workbench-filters:my-tasks:${
  localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
}`

function readStoredFilters() {
  const fallback = { project_types: [], project_statuses: [], assignees: [], assignment_scopes: [], client: '', project: '', language_pair: '' }
  try {
    const raw = localStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return {
      project_types: Array.isArray(parsed.project_types)
        ? parsed.project_types.filter(value => WORKBENCH_PROJECT_TYPE_VALUES.includes(value))
        : [],
      project_statuses: Array.isArray(parsed.project_statuses)
        ? parsed.project_statuses.filter(isValidStoredStatusKey)
        : [],
      assignees: Array.isArray(parsed.assignees)
        ? parsed.assignees.filter(isValidStoredAssigneeKey)
        : [],
      assignment_scopes: Array.isArray(parsed.assignment_scopes)
        ? parsed.assignment_scopes.filter(isValidStoredAssignmentScope)
        : [],
      client: typeof parsed.client === 'string' ? parsed.client : '',
      project: typeof parsed.project === 'string' ? parsed.project : '',
      language_pair: typeof parsed.language_pair === 'string' ? parsed.language_pair : ''
    }
  } catch {
    localStorage.removeItem(FILTER_STORAGE_KEY)
    return fallback
  }
}

const searchForm = reactive(readStoredFilters())
const projectSearchKeyword = computed(() => searchForm.project.trim())

function normalizeProjectSearch() {
  searchForm.project = projectSearchKeyword.value
}

const getTaskDeadline = getWorkItemDeadline
const deadlineState = getWorkItemDeadlineState

function isRolePoolTask(row) {
  return isRolePoolWorkItem(row)
}

function isDefaultVisibleTask(row) {
  return isDefaultVisibleWorkItem(row, currentUserId)
}

function isCurrentUserResponsible(row) {
  if (row?.current_assignee_id && currentUserId) {
    return String(row.current_assignee_id) === currentUserId
  }
  // direct / project_role 均由后端按当前登录用户生成；兼容旧数据未返回负责人 ID 的情况。
  return ['direct', 'project_role'].includes(row?.assignment_type)
}

function compareProjectTasks(left, right, now) {
  const responsibilityDifference = Number(isCurrentUserResponsible(right)) - Number(isCurrentUserResponsible(left))
  if (responsibilityDifference) return responsibilityDifference
  const riskDifference = getTranslatorExecutionRiskRank(left, now) - getTranslatorExecutionRiskRank(right, now)
  if (riskDifference) return riskDifference
  const leftReturnTime = parseBusinessDateTime(left?.translator_execution?.next_return_time)?.getTime()
  const rightReturnTime = parseBusinessDateTime(right?.translator_execution?.next_return_time)?.getTime()
  if (Number.isFinite(leftReturnTime) || Number.isFinite(rightReturnTime)) {
    if (!Number.isFinite(leftReturnTime)) return 1
    if (!Number.isFinite(rightReturnTime)) return -1
    if (leftReturnTime !== rightReturnTime) return leftReturnTime - rightReturnTime
  }
  return compareWorkItemsByDeadline(left, right, now)
}

const openTasks = computed(() => props.tasksList.filter(isWorkItemOpen))

function assignmentScopeKey(row) {
  if (row?.assignment_type === 'delegated_out') return 'delegated_out'
  if (isRolePoolTask(row)) return 'role_pool'
  if (row?.assignment_type === 'overview') return 'overview'
  if (isCurrentUserResponsible(row)) return 'mine'
  return 'overview'
}

const assignmentScopeFilterOptions = computed(() => {
  const counts = Object.fromEntries(ASSIGNMENT_SCOPE_DEFINITIONS.map(option => [option.value, 0]))
  openTasks.value.forEach((row) => {
    counts[assignmentScopeKey(row)] += 1
  })
  return ASSIGNMENT_SCOPE_DEFINITIONS.map(option => ({
    ...option,
    count: counts[option.value]
  }))
})

const projectStatusFilterOptions = computed(() => {
  const options = new Map()
  openTasks.value.forEach((row) => {
    const projectType = resolveProjectType(row)
    const status = normalizeProjectStatus(projectType, row?.project_status)
    if (!status) return
    const value = projectStatusFilterKey(row)
    const existing = options.get(value)
    if (existing) {
      existing.count += 1
      return
    }
    options.set(value, {
      value,
      label: `${WORKBENCH_PROJECT_TYPE_LABELS[projectType] || '项目'} · ${getProjectStatusLabel(projectType, status)}`,
      count: 1,
      projectType,
      status
    })
  })
  return Array.from(options.values()).sort((left, right) => {
    const typeDifference = WORKBENCH_PROJECT_TYPE_VALUES.indexOf(left.projectType) - WORKBENCH_PROJECT_TYPE_VALUES.indexOf(right.projectType)
    if (typeDifference) return typeDifference
    return left.label.localeCompare(right.label, 'zh-CN')
  })
})

const assigneeFilterOptions = computed(() => {
  const options = new Map()
  openTasks.value.forEach((row) => {
    const value = assigneeFilterKey(row)
    const existing = options.get(value)
    if (existing) {
      existing.count += 1
      return
    }
    options.set(value, {
      value,
      label: value === 'unassigned' ? '待认领（角色池）' : (row.current_assignee_name || '未知负责人'),
      count: 1
    })
  })
  return Array.from(options.values()).sort((left, right) => {
    if (left.value === 'unassigned') return 1
    if (right.value === 'unassigned') return -1
    return left.label.localeCompare(right.label, 'zh-CN')
  })
})

const filteredTasks = computed(() => {
  let list = searchForm.assignment_scopes.length
    ? openTasks.value.filter(row => searchForm.assignment_scopes.includes(assignmentScopeKey(row)))
    : openTasks.value.filter(isDefaultVisibleTask)

  if (searchForm.project_types.length) {
    list = list.filter(t => searchForm.project_types.includes(t.project_type || 'translation'))
  }
  if (searchForm.project_statuses.length) {
    list = list.filter(t => searchForm.project_statuses.includes(projectStatusFilterKey(t)))
  }
  if (searchForm.assignees.length) {
    list = list.filter(t => searchForm.assignees.includes(assigneeFilterKey(t)))
  }

  if (searchForm.client) {
    list = list.filter(t => [t.client_name, t.client_short_name].some(value => value && value.includes(searchForm.client)))
  }
  if (projectSearchKeyword.value) {
    list = list.filter(t => [t.project_name, t.sub_project_name, t.order_no].some(value => value && value.includes(projectSearchKeyword.value)))
  }
  if (searchForm.language_pair) {
    list = list.filter(t => t.language_pair && t.language_pair.includes(searchForm.language_pair))
  }
  const now = new Date()
  return list.sort((a, b) => compareProjectTasks(a, b, now))
})

const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredTasks.value.slice(start, start + PAGE_SIZE)
})

watch(pagedTasks, (rows) => {
  expandedTaskKeys.value = reconcileTranslatorExpandedKeys(
    rows,
    expandedTaskKeys.value,
    manuallyCollapsedTaskKeys.value
  )
}, { immediate: true, deep: true })

function getTaskIndex(index) {
  return (currentPage.value - 1) * PAGE_SIZE + index + 1
}

function clearTaskSelection() {
  selectedTasks.value = []
  taskTableRef.value?.clearSelection()
}

function handlePageChange() {
  clearTaskSelection()
}

watch(searchForm, (value) => {
  currentPage.value = 1
  clearTaskSelection()
  try {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
      project_types: value.project_types.filter(item => WORKBENCH_PROJECT_TYPE_VALUES.includes(item)),
      project_statuses: value.project_statuses.filter(isValidStoredStatusKey),
      assignees: value.assignees.filter(isValidStoredAssigneeKey),
      assignment_scopes: value.assignment_scopes.filter(isValidStoredAssignmentScope),
      client: value.client,
      project: value.project,
      language_pair: value.language_pair
    }))
  } catch {}
})

watch(() => filteredTasks.value.length, (total) => {
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (currentPage.value > lastPage) currentPage.value = lastPage
  emit('visible-count-change', total)
}, { immediate: true })

function rowClassName({ row }) {
  const translatorRisk = getTranslatorExecutionRiskRank(row)
  if (translatorRisk === 0) return 'overdue-row'
  if (translatorRisk === 1) return 'urgent-row'
  const state = deadlineState(row)
  if (state === DEADLINE_STATE.OVERDUE) return 'overdue-row'
  if (state === DEADLINE_STATE.URGENT) return 'urgent-row'
  if (row.delegation_overdue) return 'delegation-overdue-row'
  return ''
}

function hasAction(row, action) {
  return Array.isArray(row.available_actions) && row.available_actions.includes(action)
}

const directSelectedTasks = computed(() => selectedTasks.value.filter(
  row => row.assignment_type === 'direct' && !row.delegation_id
))
const rolePoolSelectedTasks = computed(() => selectedTasks.value.filter(isRolePoolTask))
const directSelectedRoleCodes = computed(() => new Set(
  directSelectedTasks.value.map(row => row.current_stage_role_code).filter(Boolean)
))
const handoverRoleName = computed(() => (
  directSelectedRoleCodes.value.size === 1
    ? directSelectedTasks.value[0]?.current_stage_role_name || ''
    : ''
))
const isTaskSelectable = (row) => (row.assignment_type === 'direct' && !row.delegation_id) || isRolePoolTask(row)

function assignmentTagType(row) {
  if (row.assignment_type === 'direct' || row.assignment_type === 'project_role') return 'success'
  if (isRolePoolTask(row)) return 'info'
  if (row.assignment_type === 'overview') return 'warning'
  if (row.assignment_type === 'delegated_out') return 'info'
  return 'info'
}

function assignmentLabel(row) {
  if (row.assignment_type === 'direct') return '直接负责'
  if (row.assignment_type === 'project_role') return '固定角色'
  if (isRolePoolTask(row)) return '角色池'
  if (row.assignment_type === 'overview') return '全局查看'
  if (row.assignment_type === 'delegated_out') return '我已委托'
  return '角色池'
}

function toggleTaskRowSelection(row, _column, event) {
  if (!isTaskSelectable(row)) return
  if (event?.target?.closest?.('button, a, input, textarea, select, label, .el-checkbox, .el-radio, .el-switch, .el-dropdown, .project-status-switch')) return
  const selected = selectedTasks.value.includes(row)
  taskTableRef.value?.toggleRowSelection(row, !selected)
}

const claimOwnerOptions = computed(() => {
  const owners = new Map()
  transferableTasks.value.forEach(task => {
    if (task.current_assignee_id && task.current_assignee_name) {
      owners.set(task.current_assignee_id, task.current_assignee_name)
    }
  })
  return Array.from(owners, ([id, name]) => ({ id, name }))
})

const openHandoverDialog = async () => {
  if (!directSelectedTasks.value.length) return
  if (directSelectedRoleCodes.value.size !== 1) {
    ElMessage.warning('一次只能交接同一角色类型的任务，请按角色分别选择')
    return
  }
  handoverTargetUserId.value = ''
  handoverType.value = 'daily_shift'
  handoverReasonDetail.value = ''
  handoverTransferMode.value = 'permanent'
  delegationEndAt.value = ''
  handoverNote.value = emptyNote()
  handoverVisible.value = true
  try {
    eligibleUsers.value = await getEligibleTransferUsersAPI(directSelectedTasks.value)
  } catch (error) {
    eligibleUsers.value = []
    ElMessage.error(getLocalizedErrorMessage(error, '加载可交接用户失败'))
  }
}

const canSubmitHandover = computed(() => (
  !!handoverTargetUserId.value &&
  !!handoverType.value &&
  (handoverTransferMode.value !== 'delegation' || !!delegationEndAt.value) &&
  (handoverType.value !== 'other' || !!handoverReasonDetail.value.trim())
))

const submitHandover = async () => {
  if (!handoverTargetUserId.value || !directSelectedTasks.value.length) return
  submittingHandover.value = true
  try {
    await handoverWorkflowTasksAPI({
      items: directSelectedTasks.value,
      target_user_id: handoverTargetUserId.value,
      handover_type: handoverType.value,
      transfer_mode: handoverTransferMode.value,
      delegation_end_at: handoverTransferMode.value === 'delegation' ? delegationEndAt.value : undefined,
      reason_detail: handoverType.value === 'other' ? handoverReasonDetail.value.trim() : undefined,
      content: handoverNote.value.content,
      content_json: handoverNote.value.contentJson,
      attachment_ids: handoverNote.value.attachments.map(item => item.id)
    })
    ElMessage.success(`已发起 ${directSelectedTasks.value.length} 项任务交接，等待接收人确认`)
    handoverVisible.value = false
    selectedTasks.value = []
    taskTableRef.value?.clearSelection()
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '任务交接失败'))
  } finally {
    submittingHandover.value = false
  }
}

const returnDelegation = async (row) => {
  if (!row.delegation_id) return
  try {
    await ElMessageBox.confirm(
      `确认将任务“${row.sub_project_name || row.project_name || row.order_no}”归还给${row.original_assignee_name || '原负责人'}吗？`,
      '归还临时代办任务',
      { type: 'warning', confirmButtonText: '确认归还', cancelButtonText: '取消' }
    )
    await returnDelegatedTasksAPI([row.delegation_id])
    ElMessage.success('任务已归还原负责人')
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getLocalizedErrorMessage(error, '归还任务失败'))
    }
  }
}

const claimSelectedRolePoolTasks = async () => {
  const tasks = [...rolePoolSelectedTasks.value]
  if (!tasks.length) return
  const manuscriptCount = tasks.filter(
    task => task.task_kind === 'manuscript_responsibility'
  ).length
  const workflowCount = tasks.length - manuscriptCount
  const claimDescription = [
    workflowCount ? `${workflowCount} 项工作流任务将由你直接负责` : '',
    manuscriptCount ? `${manuscriptCount} 个项目将绑定你为固定项目助理` : ''
  ].filter(Boolean).join('；')
  try {
    await ElMessageBox.confirm(
      `确认认领所选的 ${tasks.length} 项角色池任务吗？${claimDescription}。`,
      '认领角色池任务',
      { type: 'warning', confirmButtonText: '确认认领', cancelButtonText: '取消' }
    )
    claimingRolePool.value = true
    await claimRolePoolTasksAPI(tasks)
    ElMessage.success(`已认领 ${tasks.length} 项角色池任务`)
    selectedTasks.value = []
    taskTableRef.value?.clearSelection()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getLocalizedErrorMessage(error, '认领任务失败'))
    }
  } finally {
    claimingRolePool.value = false
  }
}

const loadTransferableTasks = async () => {
  claimController?.abort()
  claimController = new AbortController()
  const requestId = ++claimRequestId
  claimLoading.value = true
  claimSelectedTasks.value = []
  try {
    const rows = await getTransferableTasksAPI({
      owner_user_id: claimFilters.ownerUserId || undefined,
      keyword: claimFilters.keyword.trim() || undefined
    }, { signal: claimController.signal })
    if (requestId !== claimRequestId) return
    transferableTasks.value = Array.isArray(rows) ? rows : []
  } catch (error) {
    if (requestId !== claimRequestId || error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError') return
    ElMessage.error(getLocalizedErrorMessage(error, '网络异常，可继承任务列表未刷新'))
  } finally {
    if (requestId === claimRequestId) claimLoading.value = false
  }
}

const onClaimKeywordInput = (value) => {
  clearTimeout(claimSearchTimer)
  claimSearchTimer = null
  if (!String(value || '').trim()) {
    loadTransferableTasks()
    return
  }
  claimSearchTimer = setTimeout(() => {
    claimSearchTimer = null
    loadTransferableTasks()
  }, SEARCH_DEBOUNCE_MS)
}

const runClaimSearch = () => {
  clearTimeout(claimSearchTimer)
  claimSearchTimer = null
  loadTransferableTasks()
}

const openClaimDialog = () => {
  claimFilters.ownerUserId = ''
  claimFilters.keyword = ''
  claimNote.value = emptyNote()
  claimVisible.value = true
  loadTransferableTasks()
}

const submitClaim = async () => {
  if (!claimSelectedTasks.value.length) return
  submittingClaim.value = true
  try {
    await claimWorkflowTasksAPI({
      items: claimSelectedTasks.value,
      expected_assignee_ids: Object.fromEntries(
        claimSelectedTasks.value.map(task => [task.project_responsibility_id || task.workflow_instance_id, task.current_assignee_id])
      ),
      content: claimNote.value.content,
      content_json: claimNote.value.contentJson,
      attachment_ids: claimNote.value.attachments.map(item => item.id)
    })
    ElMessage.success(`已继承 ${claimSelectedTasks.value.length} 项任务`)
    claimVisible.value = false
    claimSelectedTasks.value = []
    emit('refresh')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '任务继承失败'))
  } finally {
    submittingClaim.value = false
  }
}

onBeforeUnmount(() => {
  clearTimeout(claimSearchTimer)
  claimController?.abort()
})
</script>

<style scoped>
.section-block { margin-bottom: 10px; }
.data-table { margin-bottom: 12px; }
.data-table :deep(.task-expand-column) { padding: 0 !important; border-right: 0 !important; }
.data-table :deep(.task-expand-column .cell) { display: none; padding: 0; }

.translator-execution-panel {
  padding: 12px 16px 16px;
  background: var(--el-fill-color-extra-light);
}

.translator-execution-panel__header,
.translator-execution-panel__summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.translator-execution-panel__header {
  justify-content: space-between;
  margin-bottom: 10px;
}

.execution-order-cell,
.execution-translator-list,
.execution-completion-list {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.execution-order-cell > div,
.execution-translator-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.execution-order-cell__name,
.muted-text,
.translator-return-summary__extra {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.execution-translator-item__name {
  width: 76px;
  overflow: hidden;
  padding-top: 2px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.translator-return-summary {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.translator-return-summary__name {
  max-width: 100%;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.completion-summary {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
}

.completion-summary__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.completion-summary__count {
  flex: none;
  padding: 0 5px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
}

.completion-summary-tooltip {
  max-width: min(520px, calc(100vw - 48px));
  white-space: normal;
}

.completion-summary-tooltip > div + div {
  margin-top: 4px;
}

/* 多页切换时预留一页表格的展示空间，避免末页行数较少导致下方区域明显跳动。 */
.section-block.is-multi-page {
  min-height: 590px;
}

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.project-type-filter-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 12px;
}

.project-type-filter-group :deep(.el-checkbox) {
  margin-right: 0;
}

.project-status-filter-group,
.assignee-filter-group,
.assignment-scope-filter-group {
  display: grid;
  gap: 4px;
}

.project-status-filter-group :deep(.el-checkbox),
.assignee-filter-group :deep(.el-checkbox),
.assignment-scope-filter-group :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
  white-space: normal;
}

.column-filter-empty {
  padding: 8px 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-align: center;
}

.task-toolbar__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.task-pagination {
  display: flex;
  justify-content: flex-end;
  margin: 0 0 12px;
}

.empty-tip {
  padding: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.table-filter-empty {
  padding: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.dialog-alert {
  margin-bottom: 18px;
}

.handover-type-field {
  display: grid;
  gap: 10px;
  width: 100%;
}

.handover-type-field :deep(.el-radio-group) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}

.delegation-end-field {
  display: grid;
  gap: 6px;
  width: 100%;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.assignee-cell {
  display: grid;
  justify-items: start;
  gap: 1px;
}

.previous-assignee {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  line-height: 1.2;
}

.claim-search {
  margin: 16px 0 2px;
}

.claim-note {
  margin-top: 18px;
}

.claim-note__label {
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

:deep(.overdue-row),
:deep(.overdue-row td) {
  background-color: var(--el-color-danger-light-9) !important;
}
:deep(.overdue-row:hover),
:deep(.overdue-row:hover td) {
  background-color: var(--el-color-danger-light-8) !important;
}

:deep(.urgent-row),
:deep(.urgent-row td) {
  background-color: var(--el-color-warning-light-9) !important;
}

:deep(.urgent-row:hover),
:deep(.urgent-row:hover td) {
  background-color: var(--el-color-warning-light-8) !important;
}

:deep(.delegation-overdue-row),
:deep(.delegation-overdue-row td) {
  background-color: var(--el-color-warning-light-9) !important;
}

@media (max-width: 720px) {
  .section-block.is-multi-page {
    min-height: 0;
  }

  .task-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .task-toolbar__actions {
    margin-left: 0;
    flex-wrap: wrap;
  }
}
</style>
