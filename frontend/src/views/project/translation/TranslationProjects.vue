<template>
  <!--
    流程说明：
    - 完整流程：客户专员 → 项目经理 → 项目专员 → 项目助理 → 译审 → 专检 → 排版 → 完成
    - 难度由客户专员在接稿时初步判断，决定是否跳过环节：
      · 简单：跳过 项目经理、项目专员、译审
      · 普通：跳过 译审
      · 复杂：全流程
    - 支持打回上一环节/上两环节，打回原因与时间线、操作日志均保留
  -->
  <el-card class="translation-projects-page">
    <template #header>
      <div class="card-header">
        <span class="page-title">笔译项目流程</span>
        <div class="card-header__actions">
          <el-select
            v-model="currentEntityKey"
            placeholder="搜索母订单或子订单号/名称"
            filterable
            remote
            reserve-keyword
            clearable
            :loading="projectOptionsLoading"
            :remote-method="searchMixedOptions"
            style="width: 420px"
            @change="onEntityKeyChange"
          >
            <el-option-group label="母订单">
              <el-option
                v-for="p in mixedEntityList.filter(e => e._type === 'project')"
                :key="`project:${p.id}`"
                :label="`[母] ${p.orderNo} · ${p.projectName}`"
                :value="`project:${p.id}`"
              />
            </el-option-group>
            <el-option-group label="子订单">
              <el-option
                v-for="s in mixedEntityList.filter(e => e._type === 'suborder')"
                :key="`suborder:${s.id}`"
                :label="`[子] ${s.subOrderNo || s.sub_order_no} · ${s.subProjectName || s.sub_project_name || ''}`"
                :value="`suborder:${s.id}`"
              />
            </el-option-group>
          </el-select>
          <el-button
            v-if="canOpenProjectChat"
            class="chat-entry-button"
            type="primary"
            plain
            @click="openProjectChatDrawer"
          >
            项目沟通
          </el-button>
        </div>
      </div>
    </template>

    <!-- 流程步骤条（按难度只显示有效环节） -->
    <el-steps :active="currentStepIndexInFlow" finish-status="success" process-status="process" align-center class="workflow-steps">
      <el-step
        v-for="(step, index) in effectiveSteps"
        :key="step.key"
        :title="step.title"
        :description="step.role"
        :class="{ 'is-current-stage': step.key === workflowState.currentStageKey }"
      />
    </el-steps>

    <!-- 当前阶段操作区（客户专员在此设定难度并指定下一环节负责人） -->
    <el-card v-if="currentProject" ref="stageCardRef" class="stage-card" shadow="never">
      <template #header>
        <div class="stage-card-header">
          <span class="stage-name">
            当前阶段：{{ currentStage?.title }}
            <el-tag v-if="currentEntityType === 'suborder'" type="warning" size="small" style="margin-left:6px">[子订单] {{ currentSubOrder?.subOrderNo || currentSubOrder?.sub_order_no }}</el-tag>
          </span>
          <el-tag type="primary" effect="plain">{{ currentStage?.role }}</el-tag>
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

      <!-- 接稿且未设定难度：先选难度 -->
      <div v-if="isAtReception && !workflowState.difficulty" class="stage-difficulty">
        <div class="section-label">来稿难度评级（客户专员初步判断）</div>
        <p class="handover-hint">请根据来稿情况选择难度，将决定后续流程是否经过「项目经理」「译审」环节。</p>
        <el-radio-group v-model="pendingDifficulty" class="difficulty-radio">
          <el-radio label="simple">简单（直接指派HR）</el-radio>
          <el-radio label="normal">普通（跳过译审）</el-radio>
          <el-radio label="complex">复杂（全流程）</el-radio>
        </el-radio-group>
        <div class="section-label">文件是否可编辑</div>
        <p class="handover-hint">不可编辑文件将自动增加「预处理」阶段（由排版专员承接）。</p>
        <el-radio-group v-model="pendingFileEditable" class="difficulty-radio">
          <el-radio :label="true">无需预处理</el-radio>
          <el-radio :label="false">需要预处理</el-radio>
        </el-radio-group>
        <div v-if="currentStageEditableFields.length" class="stage-progress">
          <div class="section-label">本阶段进度填写</div>
          <p class="handover-hint">请填写接稿阶段的关键进度信息，提交后将传递给下一阶段查看。</p>
          <el-form :disabled="!canOperateCurrentStage" label-width="130px" size="small" class="stage-form">
            <template v-for="field in currentStageEditableFields" :key="field.key">
              <el-form-item :label="field.label">
                <el-date-picker
                  v-if="field.type === 'date'"
                  v-model="stageFormData[field.key]"
                  type="datetime"
                  placeholder="请选择日期时间"
                  format="YYYY-MM-DD HH:mm:ss"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  style="width: 100%"
                />
                <el-select
                  v-else-if="field.type === 'select'"
                  v-model="stageFormData[field.key]"
                  placeholder="请选择"
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="opt in field.options"
                    :key="typeof opt === 'object' ? opt.value : opt"
                    :label="typeof opt === 'object' ? opt.label : opt"
                    :value="typeof opt === 'object' ? opt.value : opt"
                  />
                </el-select>
                <el-input
                  v-else
                  v-model="stageFormData[field.key]"
                  placeholder="请输入"
                />
              </el-form-item>
            </template>
          </el-form>
          <div class="stage-actions">
            <el-button type="info" plain :disabled="!canOperateCurrentStage" @click="saveCurrentStageProgress">
              更新本阶段进度
            </el-button>
          </div>
        </div>
        <div class="section-label">处理备注 / 交接留言</div>
        <p class="handover-hint">向下一阶段负责人传递关键信息，提交后将推进流程并锁定本阶段备注。</p>
        <el-input
          v-model="handoverNote"
          type="textarea"
          :rows="4"
          placeholder="请输入本阶段处理说明、注意事项或交接给下一阶段的留言..."
          maxlength="500"
          show-word-limit
        />
        <template v-if="nextStageAfterReception">
          <div class="section-label">下一环节负责人</div>
          <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageAfterReception.title }}」，或选择同组指派给整个角色组。</p>
          <el-radio-group v-model="assignMode" class="assign-mode-radio" style="margin-bottom: 12px">
            <el-radio-button label="personal">指定个人</el-radio-button>
            <el-radio-button label="group">同组指派</el-radio-button>
          </el-radio-group>
          <template v-if="assignMode === 'personal'">
            <el-select
              v-model="nextAssigneeUserId"
              placeholder="请选择下一环节负责人"
              filterable
              clearable
              style="width: 100%; margin-bottom: 12px"
              :loading="nextStageUsersLoading"
            >
              <el-option
                v-for="u in nextStageUsers"
                :key="u.id"
                :label="u.full_name || u.username || u.id"
                :value="u.id"
              />
            </el-select>
          </template>
          <template v-else>
            <el-select
              v-model="groupAssignRole"
              placeholder="请选择要指派的角色组"
              style="width: 100%; margin-bottom: 12px"
            >
              <el-option
                v-for="r in nextStageRoleOptions"
                :key="r"
                :label="r"
                :value="r"
              />
            </el-select>
            <el-alert
              v-if="groupAssignRole"
              type="info"
              :closable="false"
              style="margin-bottom: 12px"
            >
              <template #title>将指派给所有「{{ groupAssignRole }}」角色的成员，该组所有成员均可在「待我处理」中看到此任务</template>
            </el-alert>
          </template>
        </template>
        <div v-if="!canOperateCurrentStage" class="stage-permission-hint">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>仅客户专员或项目经理可设定难度</template>
          </el-alert>
        </div>
        <div v-else class="stage-actions">
          <p v-if="!pendingDifficulty || pendingFileEditable === null || !receptionAssignReady" class="action-hint">
            请先选择难度与文件是否可编辑，再选择下一环节负责人后即可点击下方按钮提交。
          </p>
          <el-button type="primary" :disabled="!pendingDifficulty || pendingFileEditable === null || !receptionAssignReady" @click="confirmDifficulty">
            确认难度并进入下一环节
          </el-button>
        </div>
      </div>

      <template v-else>
        <!-- 本阶段进度填写（可编辑） -->
        <div v-if="currentStageEditableFields.length && !isCurrentStageDone" class="stage-progress">
          <div class="section-label">本阶段进度填写</div>
          <p class="handover-hint">请填写本阶段的关键进度信息，提交后将传递给下一阶段查看。</p>
          <el-form :disabled="!canOperateCurrentStage" label-width="130px" size="small" class="stage-form">
            <template v-for="field in currentStageEditableFields" :key="field.key">
              <el-form-item :label="field.label">
                <el-date-picker
                  v-if="field.type === 'date'"
                  v-model="stageFormData[field.key]"
                  type="datetime"
                  placeholder="请选择日期时间"
                  format="YYYY-MM-DD HH:mm:ss"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  style="width: 100%"
                />
                <el-select
                  v-else-if="field.type === 'select'"
                  v-model="stageFormData[field.key]"
                  placeholder="请选择"
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="opt in field.options"
                    :key="typeof opt === 'object' ? opt.value : opt"
                    :label="typeof opt === 'object' ? opt.label : opt"
                    :value="typeof opt === 'object' ? opt.value : opt"
                  />
                </el-select>
                <el-input
                  v-else
                  v-model="stageFormData[field.key]"
                  placeholder="请输入"
                />
              </el-form-item>
            </template>
          </el-form>
          <div class="stage-actions">
            <el-button type="info" plain :disabled="!canOperateCurrentStage" @click="saveCurrentStageProgress">
              更新本阶段进度
            </el-button>
          </div>
        </div>

        <!-- 已完成阶段查看本阶段已填写的进度数据 -->
        <div v-if="currentStageEditableFields.length && isCurrentStageDone" class="stage-progress">
          <div class="section-label">本阶段已填写的进度信息</div>
          <el-descriptions :column="2" border size="small">
            <template v-for="item in currentStageEditableFields" :key="item.key">
              <el-descriptions-item :label="item.label">
                <span class="readonly-value">{{ resolveFieldValue(item.key) }}</span>
              </el-descriptions-item>
            </template>
          </el-descriptions>
        </div>

        <!-- 未完成：处理备注 / 交接留言 + 下一环节负责人 + 完成并提交 -->
        <div v-if="!isCurrentStageDone" class="stage-handover">
          <div class="section-label">处理备注 / 交接留言</div>
          <p class="handover-hint">向下一阶段负责人传递关键信息，提交后将推进流程并锁定本阶段备注。</p>
          <el-input
            v-model="handoverNote"
            type="textarea"
            :rows="4"
            placeholder="请输入本阶段处理说明、注意事项或交接给下一阶段的留言..."
            maxlength="500"
            show-word-limit
          />
          <template v-if="nextStageForAssignee">
            <div class="section-label">下一环节负责人</div>
            <p class="handover-hint">指定由哪位同事处理下一环节「{{ nextStageForAssignee.title }}」，或选择同组指派给整个角色组。</p>
            <el-radio-group v-model="assignMode" class="assign-mode-radio" style="margin-bottom: 12px">
              <el-radio-button label="personal">指定个人</el-radio-button>
              <el-radio-button label="group">同组指派</el-radio-button>
            </el-radio-group>
            <template v-if="assignMode === 'personal'">
              <el-select
                v-model="nextAssigneeUserId"
                placeholder="请选择下一环节负责人"
                filterable
                clearable
                style="width: 100%; margin-bottom: 12px"
                :loading="nextStageUsersLoading"
              >
                <el-option
                  v-for="u in nextStageUsers"
                  :key="u.id"
                  :label="u.full_name || u.username || u.id"
                  :value="u.id"
                />
              </el-select>
            </template>
            <template v-else>
              <el-select
                v-model="groupAssignRole"
                placeholder="请选择要指派的角色组"
                style="width: 100%; margin-bottom: 12px"
              >
                <el-option
                  v-for="r in nextStageRoleOptions"
                  :key="r"
                  :label="r"
                  :value="r"
                />
              </el-select>
              <el-alert
                v-if="groupAssignRole"
                type="info"
                :closable="false"
                style="margin-bottom: 12px"
              >
                <template #title>将指派给所有「{{ groupAssignRole }}」角色的成员，该组所有成员均可在「待我处理」中看到此任务</template>
              </el-alert>
            </template>
          </template>
          <div v-if="!canOperateCurrentStage" class="stage-permission-hint">
            <el-alert type="warning" :closable="false" show-icon>
              <template #title>您不是当前阶段的负责人，无法执行操作</template>
            </el-alert>
          </div>
          <div v-else class="stage-actions stage-actions-multi">
            <el-button type="primary" :disabled="!!nextStageForAssignee && !transitionAssignReady" @click="completeCurrentStage">
              完成本阶段并提交
            </el-button>
            <el-button
              v-if="canRollbackOne"
              type="warning"
              plain
              @click="openRollbackDialog(1)"
            >
              打回上一环节
            </el-button>
            <el-button
              v-if="canRollbackTwo"
              type="warning"
              plain
              @click="openRollbackDialog(2)"
            >
              打回上两环节
            </el-button>
            <el-button
              v-if="canRollbackToStart"
              type="danger"
              plain
              @click="openRollbackDialog(0, true)"
            >
              打回初始节点
            </el-button>
          </div>
        </div>

        <!-- 已完成：该阶段交接留言只读 -->
        <div v-else class="stage-handover-readonly">
          <div class="section-label">本阶段交接留言</div>
          <div class="readonly-note">{{ stageNoteForCurrentStage || '（无）' }}</div>
          <div v-if="canRollbackOne || canRollbackTwo || canRollbackToStart" class="stage-actions" style="margin-top: 12px">
            <el-button v-if="canRollbackOne" type="warning" plain @click="openRollbackDialog(1)">
              打回上一环节
            </el-button>
            <el-button v-if="canRollbackTwo" type="warning" plain @click="openRollbackDialog(2)">
              打回上两环节
            </el-button>
            <el-button v-if="canRollbackToStart" type="danger" plain @click="openRollbackDialog(0, true)">
              打回初始节点
            </el-button>
          </div>
        </div>
      </template>
    </el-card>

    <el-empty v-else class="empty-stage">
      <template #description>
        <p>请在上方下拉框<strong>选择项目</strong>，或从下方「待我处理」Tab 中点「进入」。</p>
        <p class="empty-hint">若项目当前阶段为「客户专员」且尚未设定难度，选择后将显示<strong>难度评级</strong>与下一环节负责人。</p>
      </template>
    </el-empty>

    <!-- 打回原因弹窗 -->
    <el-dialog
      v-model="rollbackDialogVisible"
      :title="rollbackDialogTitle"
      width="480px"
      @close="handleRollbackDialogClose"
    >
      <p class="rollback-hint">请填写打回原因，便于上一环节负责人知悉并重新处理。该记录将保留在操作日志中。</p>
      <el-input
        v-model="rollbackNote"
        type="textarea"
        :rows="4"
        placeholder="请输入打回原因（必填）..."
        maxlength="300"
        show-word-limit
      />
      <template #footer>
        <el-button @click="rollbackDialogVisible = false">取消</el-button>
        <el-button type="warning" :disabled="!rollbackNote.trim()" @click="confirmRollback">
          确认打回
        </el-button>
      </template>
    </el-dialog>

    <!-- 下方 Tabs -->
    <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
      <el-tab-pane label="待我处理" name="my_tasks">
        <div class="section-label">当前登录用户「{{ currentUserName }}」待处理的笔译项目</div>
        <el-table :data="myTaskProjectsList" border size="small" highlight-current-row @current-change="onMyTaskRowClick">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column label="类型" width="70">
            <template #default="{ row }">
              <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
                {{ row.entity_type === 'suborder' ? '子订单' : '母订单' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="订单号" width="160">
            <template #default="{ row }">
              {{ row.entity_type === 'suborder' ? (row.sub_order_no || row.order_no) : row.order_no }}
            </template>
          </el-table-column>
          <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="client_short_name" label="客户简称" width="120" />
          <el-table-column label="当前阶段" width="180">
            <template #default="{ row }">
              <span v-if="row.current_stage_key">
                {{ stageByKey[row.current_stage_key]?.title || row.current_stage_key }}
                <el-tag v-if="row.current_stage_key === 'reception' && !row.difficulty" type="warning" size="small" style="margin-left: 6px">待设定难度</el-tag>
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="onMyTaskRowClick(row)">进入</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!myTaskProjectsList.length" description="暂无待您处理的项目" />
      </el-tab-pane>

      <el-tab-pane label="项目概览" name="overview">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="订单号">{{ currentProject.orderNo }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ currentProject.projectName }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ currentProject.clientShortName }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ currentProject.clientCode }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">
            <el-tag :type="getStatusType(workflowState.projectStatus || currentProject.projectStatus)" size="small">
              {{ getStatusLabel(workflowState.projectStatus || currentProject.projectStatus) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="难度评级">
            {{ workflowState.difficulty ? difficultyLabel(workflowState.difficulty) : '未设定' }}
          </el-descriptions-item>
          <el-descriptions-item label="客户交稿时间">{{ currentProject.customerDeadlineTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ currentProject.createdAt || '-' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ currentProject.updatedAt || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>

      <el-tab-pane label="项目文件" name="files">
        <el-table :data="fileList" v-loading="fileListLoading" border size="small" style="width: 100%">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="name" label="文件名" min-width="160" show-overflow-tooltip />
          <el-table-column label="原文路径" min-width="220">
            <template #default="{ row }">
              <template v-if="row.storage_path">
                <a :href="toOpenPathHref(row.storage_path)" style="word-break:break-all;color:#409eff;text-decoration:none;font-size:12px;">{{ row.storage_path }}</a>
                <el-button link type="primary" size="small" style="margin-left:4px" @click.prevent="copyFilePath(row.storage_path)">复制</el-button>
              </template>
              <span v-else style="color:#c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="派稿文路径" min-width="220">
            <template #default="{ row }">
              <template v-if="row.dispatch_path">
                <a :href="toOpenPathHref(row.dispatch_path)" style="word-break:break-all;color:#409eff;text-decoration:none;font-size:12px;">{{ row.dispatch_path }}</a>
                <el-button link type="primary" size="small" style="margin-left:4px" @click.prevent="copyFilePath(row.dispatch_path)">复制</el-button>
              </template>
              <span v-else style="color:#c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="发客户路径" min-width="220">
            <template #default="{ row }">
              <template v-if="row.client_delivery_path">
                <a :href="toOpenPathHref(row.client_delivery_path)" style="word-break:break-all;color:#409eff;text-decoration:none;font-size:12px;">{{ row.client_delivery_path }}</a>
                <el-button link type="primary" size="small" style="margin-left:4px" @click.prevent="copyFilePath(row.client_delivery_path)">复制</el-button>
              </template>
              <span v-else style="color:#c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="updatedAt" label="创建时间" width="170" />
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" size="small" link @click="handleFileEdit(row)">编辑</el-button>
              <el-button type="danger" size="small" link @click="handleFileDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!fileListLoading && !fileList.length" description="该项目暂无文件记录" />
      </el-tab-pane>

      <el-tab-pane label="翻译/审核进度" name="progress">
        <el-descriptions v-if="currentProject" :column="2" border>
          <el-descriptions-item label="译员安排">{{ currentProject.translatorAssignee || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员安排时间">{{ currentProject.translatorAssignmentTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="译员交稿进度">{{ currentProject.translatorDeliveryProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核1进度">{{ currentProject.review1Progress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核前专检进度">{{ currentProject.preReviewQcProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="排版进度">{{ currentProject.layoutProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="整理进度">{{ currentProject.consolidationProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发客户时间">{{ currentProject.sentToClientTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核后专检进度">{{ currentProject.postReviewQcProgress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核2进度">{{ currentProject.review2Progress || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="请先选择项目" />
      </el-tab-pane>
<el-tab-pane label="&#x65E5;&#x5FD7;&#x8BB0;&#x5F55;" name="logs">
        <el-form :inline="true" :model="logFilters" size="small" class="log-filter-bar">
          <el-form-item label="类型">
            <el-select v-model="logFilters.direction" clearable placeholder="全部" style="width: 120px">
              <el-option label="推进" value="forward" />
              <el-option label="回退" value="rollback" />
            </el-select>
          </el-form-item>
          <el-form-item label="环节">
            <el-select v-model="logFilters.stage" clearable placeholder="全部" style="width: 180px">
              <el-option v-for="item in logStageOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="操作人">
            <el-select v-model="logFilters.operator" clearable placeholder="全部" style="width: 180px">
              <el-option v-for="item in logOperatorOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="logFilters.dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
        </el-form>
        <el-timeline v-if="filteredTransitionLog.length" reverse>
          <el-timeline-item
            v-for="(entry, i) in filteredTransitionLog"
            :key="i"
            :timestamp="entry.at"
            placement="top"
            :type="entry.direction === 'rollback' ? 'danger' : undefined"
          >
            <el-card shadow="never" :class="{ 'log-rollback': entry.direction === 'rollback' }">
              <p class="log-action">
                <el-tag v-if="entry.direction === 'rollback'" type="danger" size="small">回退</el-tag>
                <el-tag v-else type="success" size="small">推进</el-tag>
                {{ entry.description }}
              </p>
              <p v-if="entry.note" class="log-note">{{ entry.note }}</p>
              <p v-if="entry.nextAssigneeUserName" class="log-operator">下一负责人：{{ entry.nextAssigneeUserName }}</p>
              <p v-if="entry.operator" class="log-operator">操作人：{{ entry.operator }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无符合条件的日志记录" />
      </el-tab-pane>
    </el-tabs>

    <el-drawer
      v-model="chatDrawerVisible"
      class="project-chat-drawer"
      direction="rtl"
      size="560px"
      :modal="false"
      :lock-scroll="false"
      @close="handleChatDrawerClose"
    >
      <template #header>
        <div class="project-chat-drawer__header">
          <div class="project-chat-drawer__title">项目沟通</div>
          <div class="project-chat-drawer__subtitle">
            {{ currentProject?.orderNo || '-' }} · {{ currentProject?.projectName || '未选择母订单' }}
          </div>
        </div>
      </template>
      <ProjectChatPanel
        :project-id="currentProjectId"
        :active="chatDrawerVisible && currentEntityType === 'project'"
        :drawer-mode="true"
      />
    </el-drawer>

  <!-- 项目文件编辑对话框 -->
  <el-dialog v-model="fileEditDialogVisible" title="编辑项目文件" width="560px" @close="resetFileEditForm">
    <el-form ref="fileEditFormRef" :model="fileEditForm" :rules="fileEditRules" label-width="110px">
      <el-form-item label="文件名" prop="file_name">
        <el-input v-model="fileEditForm.file_name" placeholder="请输入文件名" />
      </el-form-item>
      <el-form-item label="原文路径" prop="storage_path">
        <el-input v-model="fileEditForm.storage_path" placeholder="如 \\win-server\原文" />
      </el-form-item>
      <el-form-item label="派稿文路径">
        <el-input v-model="fileEditForm.dispatch_path" placeholder="如 \\win-server\派稿" />
      </el-form-item>
      <el-form-item label="译文路径">
        <el-input v-model="fileEditForm.translation_path" placeholder="如 \\win-server\译文" />
      </el-form-item>
      <el-form-item label="发客户路径">
        <el-input v-model="fileEditForm.client_delivery_path" placeholder="如 \\win-server\发客户" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="fileEditDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="fileEditSaving" @click="handleFileEditSubmit">保存</el-button>
    </template>
  </el-dialog>
  </el-card>
</template>

<script setup>
/**
 * 流程状态与交接字段设计（便于与后端对齐）
 * ----------------------------------------
 * workflowState 单项目流程状态：
 *   - difficulty: 'simple'|'normal'|'complex'
 *   - currentStageKey: 当前环节 key（reception / project_manager / ... / completed）
 *   - currentAssigneeUserId: 当前环节负责人 user_id（UUID 或字符串）
 *   - currentAssigneeUserName: 当前环节负责人显示名（full_name 或 username）
 *   - stageNotes: { [stageKey]: string } 各环节交接留言
 *   - transitionLog: 操作日志数组，每项：
 *       at, fromStage, toStage, toTitle, direction('forward'|'rollback'),
 *       description, note?, operator?,
 *       nextAssigneeUserId?, nextAssigneeUserName?  // 推进时下一环节指定用户
 *
 * 完成并提交时：必填「下一环节负责人」nextAssigneeUserId，提交后写入 state 与 log。
 * 待我处理：筛选 currentAssigneeUserName === 当前登录用户 且 currentStageKey !== 'completed'。
 */
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProject, getProjects } from '@/api/projects'
import { getProjectFilesByProject, updateProjectFile, deleteProjectFile } from '@/api/projectFiles'
import {
  getUsersByRoleName,
  getMyTasksAPI, getWorkflowStateAPI, initWorkflowAPI, setDifficultyAPI, transitionWorkflowAPI, rollbackWorkflowAPI, updateStageDataAPI,
  getSubOrderWorkflowStateAPI, initSubOrderWorkflowAPI, setSubOrderDifficultyAPI, transitionSubOrderWorkflowAPI, rollbackSubOrderWorkflowAPI, updateSubOrderStageDataAPI,
} from '@/api/workflow'
import { getSubOrdersByProject, getSubOrders } from '@/api/subOrders'
import { getOnLeaveUsers } from '@/api/leave'
import { getStoredRoles } from '@/utils/permission'
import ProjectChatPanel from '@/components/ProjectChatPanel.vue'

const route = useRoute()
const router = useRouter()

// ---------- 全流程阶段定义（顺序固定） ----------
const ALL_STAGES = [
  { key: 'reception', title: '客户专员', role: '客户专员' },
  { key: 'layout_assign', title: '预处理', role: '排版专员', assignRoles: ['排版专员'] },
  { key: 'project_manager', title: '项目经理', role: '项目经理' },
  { key: 'project_specialist', title: '项目专员', role: '项目专员' },
  { key: 'project_assistant', title: '项目助理', role: '项目助理' },
  { key: 'review', title: '译审', role: '译审' },
  { key: 'special_qc', title: '专检', role: '项目专员 / 客户专员', assignRoles: ['项目专员', '客户专员'] },
  { key: 'layout', title: '排版', role: '排版专员', assignRoles: ['排版专员'] },
  { key: 'completed', title: '完成', role: '-' }
]

const STAGE_KEYS = ALL_STAGES.map((s) => s.key)
const stageByKey = Object.fromEntries(ALL_STAGES.map((s) => [s.key, s]))

/** 根据难度返回本单实际经过的环节（有序），用于步骤条与推进逻辑 */
function getEffectiveStages(difficulty, fileEditable = true) {
  if (!difficulty) return [ALL_STAGES[0]]
  const shouldInsertLayoutAssign = fileEditable === false || fileEditable === 'no'
  let steps = [...ALL_STAGES]
  if (!shouldInsertLayoutAssign) {
    steps = steps.filter((s) => s.key !== 'layout_assign')
  }
  if (difficulty === 'simple') {
    // 简单：跳过 项目经理、项目专员、译审；专检/排版仍保留
    return steps.filter((s) => !['project_manager', 'project_specialist', 'review'].includes(s.key))
  }
  if (difficulty === 'normal') {
    // 普通：跳过 译审；专检/排版仍保留
    return steps.filter((s) => s.key !== 'review')
  }
  return steps
}

/**
 * 各阶段的进度字段配置
 * - editable: 本阶段负责人需要手动填写的字段（可编辑）
 * - readonly: 从上一阶段继承的只读字段（供本阶段查看参考）
 * 每个字段: { key, label, type? }  type 可选 'input'(默认) | 'select' | 'date'
 */
/**
 * 各阶段通用的项目状态选项
 * - 进入阶段时自动设为"进行中"，用户可手动切为"已暂停"
 * - 完成并提交时自动设为下一阶段的"进行中"
 * - value 使用英文枚举，对应后端数据库存储值
 */
const PROJECT_STATUS_OPTIONS = [
  { label: '进行中', value: 'in_progress' },
  { label: '已暂停', value: 'paused' },
  { label: '已终止', value: 'terminated' }
]

const stageProgressMap = {
  reception: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'customerReceptionTime', label: '客户来稿时间', type: 'date' },
      { key: 'customerDeadlineTime', label: '交稿客户时间', type: 'date' },
      { key: 'fileTypeSecondary', label: '文本类型' },
      { key: 'languagePair', label: '翻译方向' },
      { key: 'wordCount', label: '字数统计' }
    ],
    readonly: [
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  layout_assign: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'layoutAssignNote', label: '预处理说明' }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  project_manager: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'priority', label: '优先级', type: 'select', options: ['低', '中', '高', '紧急'] },
      { key: 'wordCount', label: '预估字数' }
    ],
    readonly: [
      { key: 'customerReceptionTime', label: '客户接待时间' },
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'clientShortName', label: '客户简称' }
    ]
  },
  project_specialist: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'languagePair', label: '语言方向' },
      { key: 'fileTypeSecondary', label: '文本类型' }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'priority', label: '优先级' },
      { key: 'wordCount', label: '预估字数' }
    ]
  },
  project_assistant: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'translatorAssignee', label: '译员安排' },
      { key: 'translatorAssignmentTime', label: '译员安排时间', type: 'date' },
      { key: 'estimatedTime', label: '译员预计处理耗时', type: 'text' },
      { key: 'actualTime', label: '译员实际处理耗时' },
      { key: 'translatorDeliveryProgress', label: '译员交稿进度', type: 'select', options: ['未开始', '进行中', '已完成', '待审核', '已审核'] }
    ],
    readonly: [
      { key: 'customerDeadlineTime', label: '客户交稿时间' },
      { key: 'languagePair', label: '翻译方向' },
      { key: 'priority', label: '优先级' }
    ]
  },
  review: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'review1Progress', label: '审核进度', type: 'select', options: ['未开始', '进行中', '已完成'] },
      { key: 'postReviewQcProgress', label: '审核后专检进度', type: 'select', options: ['未开始', '进行中', '已完成'] }
    ],
    readonly: [
      { key: 'translatorAssignee', label: '译员' },
      { key: 'translatorDeliveryProgress', label: '译员交稿进度' }
    ]
  },
  special_qc: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'specialQcResult', label: '专检结果', type: 'select', options: ['通过', '需修改', '驳回'] },
      { key: 'specialQcNote', label: '专检说明' }
    ],
    readonly: [
      { key: 'review1Progress', label: '审核进度' },
      { key: 'postReviewQcProgress', label: '审核后专检进度' },
      { key: 'translatorAssignee', label: '译员' }
    ]
  },
  layout: {
    editable: [
      { key: 'projectStatus', label: '项目状态', type: 'select', options: PROJECT_STATUS_OPTIONS },
      { key: 'estimatedTime', label: '预计处理耗时' },
      { key: 'actualTime', label: '实际处理耗时' },
      { key: 'layoutProgress', label: '排版进度', type: 'select', options: ['未开始', '进行中', '已完成'] },
      { key: 'layoutNote', label: '排版备注' }
    ],
    readonly: [
      { key: 'specialQcResult', label: '专检结果' },
      { key: 'specialQcNote', label: '专检说明' }
    ]
  },
  completed: {
    editable: [],
    readonly: [
      { key: 'specialQcResult', label: '专检结果' },
      { key: 'layoutProgress', label: '排版进度' },
      { key: 'review1Progress', label: '审核进度' },
      { key: 'translatorAssignee', label: '译员' }
    ]
  }
}

const workflowStateByProject = reactive({})

function getWorkflowState(projectId) {
  if (projectId === undefined || projectId === null || projectId === '') return null
  const key = String(projectId)
  return workflowStateByProject[key] || null
}

function setWorkflowState(projectId, payload) {
  const key = String(projectId)
  if (!workflowStateByProject[key]) {
    workflowStateByProject[key] = reactive({})
  }
  const state = workflowStateByProject[key]
  
  state.difficulty = payload.difficulty
  state.fileEditable = payload.file_editable
  state.currentStageKey = payload.current_stage_key
  state.currentAssigneeUserId = payload.current_assignee_id
  state.currentAssigneeUserName = payload.current_assignee_name
  state.groupAssignRole = payload.group_assign_role || null
  state.projectStatus = payload.project_status
  state.stageNotes = payload.stage_notes || {}
  state.stageData = payload.stage_data || {}
  state.transitionLog = (payload.logs || []).map(log => ({
    at: log.created_at ? log.created_at.replace('T', ' ').substring(0, 19) : '',
    fromStage: log.from_stage,
    toStage: log.to_stage,
    direction: log.direction,
    description: log.description,
    operator: log.operator_name,
    note: log.note,
    nextAssigneeUserName: log.next_assignee_name
  }))
}

const myTaskProjectsList = ref([])

const currentProjectId = ref('')
// 'project' = 母订单, 'suborder' = 子订单
const currentEntityType = ref('project')
// 当前选中的子订单对象（entityType === 'suborder' 时有值）
const currentSubOrder = ref(null)
const projectList = ref([])
// 统一下拉列表（母订单 + 子订单混合），每项含 _type 字段区分
const mixedEntityList = ref([])
// 当前下拉选中的值（格式：`${type}:${id}`）
const currentEntityKey = ref('')
const handoverNote = ref('')
const activeTab = ref('my_tasks')
const chatDrawerVisible = ref(false)
const canOpenProjectChat = computed(() => currentEntityType.value === 'project' && !!currentProjectId.value)
const fileList = ref([])
const projectOptionsLoading = ref(false)
const fileListLoading = ref(false)

const rollbackDialogVisible = ref(false)
const rollbackSteps = ref(1)
const rollbackToStart = ref(false)
const rollbackNote = ref('')

const nextAssigneeUserId = ref('')
const assignMode = ref('personal')   // 'personal' | 'group'
const groupAssignRole = ref('')       // 同组指派时选择的角色名
const pendingDifficulty = ref(null)
const pendingFileEditable = ref(null)
const nextStageUsers = ref([])
const nextStageUsersLoading = ref(false)
const stageCardRef = ref(null)

const normalizeProjectFile = (file) => ({
  ...file,
  name: file?.file_name || '-',
  type: file?.file_type || file?.file_ext || '-',
  updatedAt: file?.created_at ? String(file.created_at).replace('T', ' ').substring(0, 19) : '-'
})

function toOpenPathHref(path) {
  if (!path) return '#'
  const stripped = path.replace(/^\\\\/,'')
  return 'openpath://' + encodeURIComponent(stripped).replace(/%5C/gi, '\\').replace(/%2F/gi, '/')
}

async function copyFilePath(path) {
  if (!path) return
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// ---- 项目文件编辑 ----
const fileEditDialogVisible = ref(false)
const fileEditSaving = ref(false)
const fileEditFormRef = ref(null)
const fileEditForm = reactive({
  id: null,
  file_name: '',
  storage_path: '',
  dispatch_path: '',
  translation_path: '',
  client_delivery_path: ''
})
const fileEditRules = {
  file_name: [{ required: true, message: '请输入文件名', trigger: 'blur' }],
  storage_path: [{ required: true, message: '请输入原文路径', trigger: 'blur' }]
}

function handleFileEdit(row) {
  Object.assign(fileEditForm, {
    id: row.id,
    file_name: row.file_name || '',
    storage_path: row.storage_path || '',
    dispatch_path: row.dispatch_path || '',
    translation_path: row.translation_path || '',
    client_delivery_path: row.client_delivery_path || ''
  })
  fileEditDialogVisible.value = true
}

async function handleFileDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该文件记录？', '提示', { type: 'warning' })
    await deleteProjectFile(row.id)
    ElMessage.success('删除成功')
    loadProjectFiles()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err?.detail || '删除失败')
  }
}

async function handleFileEditSubmit() {
  if (!fileEditFormRef.value) return
  await fileEditFormRef.value.validate(async (valid) => {
    if (!valid) return
    fileEditSaving.value = true
    try {
      const payload = { ...fileEditForm }
      delete payload.id
      ;['dispatch_path', 'translation_path', 'client_delivery_path'].forEach(k => {
        if (!payload[k]) payload[k] = null
      })
      await updateProjectFile(fileEditForm.id, payload)
      ElMessage.success('更新成功')
      fileEditDialogVisible.value = false
      loadProjectFiles()
    } catch (err) {
      ElMessage.error(err?.detail || '保存失败')
    } finally {
      fileEditSaving.value = false
    }
  })
}

function resetFileEditForm() {
  Object.assign(fileEditForm, {
    id: null, file_name: '', storage_path: '',
    dispatch_path: '', translation_path: '', client_delivery_path: ''
  })
  fileEditFormRef.value?.resetFields()
}

function mergeProjectOptions(list) {
  const merged = Array.isArray(list) ? [...list] : []
  const current = selectedProjectRow.value || projectList.value.find((item) => String(item.id) === String(currentProjectId.value))
  if (current && !merged.some((item) => String(item.id) === String(current.id))) {
    merged.unshift(current)
  }
  return merged
}

async function loadProjectOptions(query = '') {
  projectOptionsLoading.value = true
  try {
    const params = { skip: 0, limit: 100 }
    if (query) {
      if (/^TP[-\w]/i.test(query)) {
        params.order_no = query
      } else {
        params.project_name = query
      }
    }
    const res = await getProjects(params)
    projectList.value = mergeProjectOptions(Array.isArray(res) ? res : [])
  } catch (e) {
    console.error('Failed to load project options', e)
    projectList.value = mergeProjectOptions([])
  } finally {
    projectOptionsLoading.value = false
  }
}

function searchProjectOptions(query) {
  loadProjectOptions((query || '').trim())
}

/** 混合搜索：母订单 + 子订单，合并到 mixedEntityList */
async function loadMixedOptions(query = '') {
  projectOptionsLoading.value = true
  try {
    const projectParams = { skip: 0, limit: 50 }
    const subOrderParams = { skip: 0, limit: 50 }
    if (query) {
      if (/^TP[-\w]/i.test(query)) {
        projectParams.order_no = query
      } else {
        projectParams.project_name = query
      }
      if (/^SO[-\w]/i.test(query) || /^子/i.test(query)) {
        subOrderParams.sub_order_no = query
      } else {
        subOrderParams.project_name = query
      }
    }

    const [projectsRes, subOrdersRes] = await Promise.allSettled([
      getProjects(projectParams),
      getSubOrders(subOrderParams)
    ])

    // 解析订单号各段用于排序（格式：TP-260228-0016 → [260228, 16]）
    const parseOrderNo = (no) => {
      const m = String(no || '').match(/^[A-Z]+-(\d{6})-(\d+)$/i)
      return m ? [parseInt(m[1], 10), parseInt(m[2], 10)] : [0, 0]
    }
    const orderNoComparator = (getNo) => (a, b) => {
      const [dateA, seqA] = parseOrderNo(getNo(a))
      const [dateB, seqB] = parseOrderNo(getNo(b))
      return dateA !== dateB ? dateA - dateB : seqA - seqB
    }

    const projects = (projectsRes.status === 'fulfilled' ? (Array.isArray(projectsRes.value) ? projectsRes.value : []) : [])
      .map(p => ({ ...p, _type: 'project' }))
      .sort(orderNoComparator(p => p.orderNo || p.order_no))

    const subOrders = (subOrdersRes.status === 'fulfilled' ? (Array.isArray(subOrdersRes.value) ? subOrdersRes.value : []) : [])
      .map(s => ({ ...s, _type: 'suborder' }))
      .sort(orderNoComparator(s => s.subOrderNo || s.sub_order_no))

    projectList.value = mergeProjectOptions(projects.map(p => ({ ...p })))

    // 保留当前选中项
    const merged = [...projects, ...subOrders]
    if (currentEntityType.value === 'suborder' && currentSubOrder.value) {
      if (!merged.some(e => e._type === 'suborder' && String(e.id) === String(currentSubOrder.value.id))) {
        merged.unshift({ ...currentSubOrder.value, _type: 'suborder', subOrderNo: currentSubOrder.value.subOrderNo || currentSubOrder.value.sub_order_no })
      }
    } else if (currentEntityType.value === 'project' && currentProjectId.value) {
      if (!merged.some(e => e._type === 'project' && String(e.id) === String(currentProjectId.value))) {
        const cur = selectedProjectRow.value || projectList.value.find(p => String(p.id) === String(currentProjectId.value))
        if (cur) merged.unshift({ ...cur, _type: 'project' })
      }
    }
    mixedEntityList.value = merged
  } catch (e) {
    console.error('Failed to load mixed options', e)
  } finally {
    projectOptionsLoading.value = false
  }
}

function searchMixedOptions(query) {
  loadMixedOptions((query || '').trim())
}

/** 下拉选中某项 */
function onEntityKeyChange(val) {
  if (!val) {
    // 清空
    currentEntityType.value = 'project'
    currentProjectId.value = ''
    currentSubOrder.value = null
    selectedProjectRow.value = null
    onProjectChange()
    return
  }
  const [type, id] = val.split(':')
  if (type === 'project') {
    currentEntityType.value = 'project'
    currentSubOrder.value = null
    currentProjectId.value = id
    selectedProjectRow.value = projectList.value.find(p => String(p.id) === id) || null
    onProjectChange()
  } else if (type === 'suborder') {
    const so = mixedEntityList.value.find(e => e._type === 'suborder' && String(e.id) === id)
    currentEntityType.value = 'suborder'
    currentSubOrder.value = so || { id }
    currentProjectId.value = id  // 复用 currentProjectId 存放当前 id，工作流 API 按 entityType 分支
    selectedProjectRow.value = null
    onProjectChange()
  }
}

async function loadProjectFiles() {
  if (!currentProjectId.value) {
    fileList.value = []
    return
  }

  fileListLoading.value = true
  try {
    const res = await getProjectFilesByProject(currentProjectId.value, { skip: 0, limit: 100 })
    fileList.value = (Array.isArray(res) ? res : []).map(normalizeProjectFile)
  } catch (e) {
    console.error('Failed to load project files', e)
    fileList.value = []
  } finally {
    fileListLoading.value = false
  }
}
/** 从「待我处理」点「进入」时保存的行对象，保证阶段卡片一定能显示（避免 id 匹配不到） */
const selectedProjectRow = ref(null)

const currentProject = computed(() => {
  if (currentEntityType.value === 'suborder') {
    // 子订单模式：只要有子订单和工作流状态就显示阶段卡片
    return currentSubOrder.value || (currentProjectId.value ? { id: currentProjectId.value } : undefined)
  }
  if (selectedProjectRow.value) return selectedProjectRow.value
  const id = currentProjectId.value
  if (id === undefined || id === null || id === '') return undefined
  return projectList.value.find((p) => String(p.id) === String(id))
})

const workflowState = computed(() => getWorkflowState(currentProjectId.value) || {})

const effectiveSteps = computed(() => getEffectiveStages(workflowState.value.difficulty, workflowState.value.fileEditable))

const currentStage = computed(() => stageByKey[workflowState.value.currentStageKey] ?? null)

const currentStepIndexInFlow = computed(() => {
  const key = workflowState.value.currentStageKey
  const idx = effectiveSteps.value.findIndex((s) => s.key === key)
  return idx >= 0 ? idx : 0
})

const isAtReception = computed(() => workflowState.value.currentStageKey === 'reception')

const isCurrentStageDone = computed(() => {
  const note = workflowState.value.stageNotes?.[workflowState.value.currentStageKey]
  return note !== undefined && note !== ''
})

const stageNoteForCurrentStage = computed(
  () => workflowState.value.stageNotes?.[workflowState.value.currentStageKey] ?? ''
)

const currentStageConfig = computed(
  () => stageProgressMap[workflowState.value.currentStageKey] || { editable: [], readonly: [] }
)

/** 本阶段可编辑字段 */
const currentStageEditableFields = computed(() => currentStageConfig.value.editable || [])

const transitionLog = computed(() => workflowState.value.transitionLog || [])
const logFilters = reactive({ direction: '', stage: '', operator: '', dateRange: [] })
const logStageOptions = computed(() => {
  const seen = new Set()
  return transitionLog.value
    .flatMap(entry => [entry.fromStage, entry.toStage])
    .filter(stage => stage && !seen.has(stage) && seen.add(stage))
    .map(stage => ({ value: stage, label: stageByKey[stage]?.title || stage }))
})
const logOperatorOptions = computed(() => {
  const seen = new Set()
  return transitionLog.value
    .map(entry => entry.operator)
    .filter(name => name && !seen.has(name) && seen.add(name))
})
const filteredTransitionLog = computed(() => transitionLog.value.filter((entry) => {
  if (logFilters.direction && entry.direction !== logFilters.direction) return false
  if (logFilters.stage && entry.fromStage !== logFilters.stage && entry.toStage !== logFilters.stage) return false
  if (logFilters.operator && entry.operator !== logFilters.operator) return false
  if (Array.isArray(logFilters.dateRange) && logFilters.dateRange.length === 2) {
    const [start, end] = logFilters.dateRange
    const entryDate = entry.at ? entry.at.slice(0, 10) : ''
    if (entryDate && (entryDate < start || entryDate > end)) return false
  }
  return true
}))

const canRollbackOne = computed(() => {
  const steps = effectiveSteps.value
  const idx = steps.findIndex((s) => s.key === workflowState.value.currentStageKey)
  return idx > 0
})

const canRollbackTwo = computed(() => {
  const steps = effectiveSteps.value
  const idx = steps.findIndex((s) => s.key === workflowState.value.currentStageKey)
  return idx >= 2
})

const canRollbackToStart = computed(() => {
  const steps = effectiveSteps.value
  const idx = steps.findIndex((s) => s.key === workflowState.value.currentStageKey)
  // 只有 idx >= 2 时才显示"打回初始节点"，避免和"打回上一环节"重复
  return idx >= 2
})

const rollbackDialogTitle = computed(() => (
  rollbackToStart.value ? '打回初始节点' : `打回${rollbackSteps.value}环节`
))

const currentUserName = computed(() => {
  try {
    return (localStorage.getItem('user_name') || '').trim() || '当前用户'
  } catch {
    return '当前用户'
  }
})

const currentUserId = computed(() => {
  try {
    return localStorage.getItem('user_id') || ''
  } catch {
    return ''
  }
})



/** 当前用户是否有权操作当前阶段（是负责人或拥有该阶段对应角色，或是超级管理员/项目经理） */
const canOperateCurrentStage = computed(() => {
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return false
  const name = currentUserName.value
  const roles = getStoredRoles()
  // 超级管理员始终可操作
  if (roles.includes('admin') || roles.includes('超级管理员')) return true
  // 接稿阶段（难度设定）：客户专员 和 项目经理 均可操作，无需指派匹配
  if (state.currentStageKey === 'reception') {
    return roles.includes('客户专员') || roles.includes('项目经理')
  }
  // 项目经理对其他阶段也可操作
  if (roles.includes('项目经理')) return true
  // 同组指派时：当前用户拥有该角色即可操作
  if (state.groupAssignRole && !state.currentAssigneeUserId) {
    return roles.includes(state.groupAssignRole)
  }
  // 已指定负责人时，只有负责人本人可操作
  if (state.currentAssigneeUserId) {
    return state.currentAssigneeUserId === currentUserId.value
  } else if (state.currentAssigneeUserName) {
    return state.currentAssigneeUserName === name
  }
  // 未指定负责人，检查角色匹配
  const stage = stageByKey[state.currentStageKey]
  if (!stage) return false
  if (stage.assignRoles && stage.assignRoles.length) {
    return stage.assignRoles.some((r) => roles.includes(r))
  }
  return roles.includes(stage.role)
})

const nextStageAfterReception = computed(() => {
  if (workflowState.value.currentStageKey !== 'reception' || !pendingDifficulty.value || pendingFileEditable.value === null) return null
  const steps = getEffectiveStages(pendingDifficulty.value, pendingFileEditable.value)
  return steps[1] || null
})

const nextStageForAssignee = computed(() => {
  const state = getWorkflowState(currentProjectId.value)
  if (!state || state.currentStageKey === 'completed') return null
  const steps = getEffectiveStages(state.difficulty, state.fileEditable)
  const idx = steps.findIndex((s) => s.key === state.currentStageKey)
  if (idx < 0 || idx >= steps.length - 1) return null
  const next = steps[idx + 1]
  // 如果下一步是"完成"，不需要指定负责人
  if (next && next.key === 'completed') return null
  return next || null
})



/** 当前阶段可编辑字段的表单数据 */
const stageFormData = reactive({})

/** 从所有已完成阶段的 stageData 中查找某字段最新值（后填写的覆盖先填写的） */
function resolveFieldValue(fieldKey) {
  const state = getWorkflowState(currentProjectId.value)
  if (!state || !state.stageData) return '-'
  const steps = getEffectiveStages(state.difficulty, state.fileEditable)
  const curIdx = steps.findIndex((s) => s.key === state.currentStageKey)
  // 从当前阶段往前找，取最近一次填写的值
  for (let i = curIdx; i >= 0; i--) {
    const data = state.stageData[steps[i].key]
    if (data && data[fieldKey] !== undefined && data[fieldKey] !== '') return data[fieldKey]
  }
  // 兜底：从项目原始数据中取
  const p = currentProject.value
  return p?.[fieldKey] ?? '-'
}

/** 初始化当前阶段的表单数据（切换项目或推进阶段时调用） */
function initStageFormData() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  const config = stageProgressMap[state.currentStageKey]
  if (!config) return
  // 清空旧数据
  Object.keys(stageFormData).forEach((k) => delete stageFormData[k])
  // 如果该阶段已有保存的数据（打回后重新进入），恢复之
  const saved = state.stageData?.[state.currentStageKey]
  for (const field of config.editable) {
    stageFormData[field.key] = saved?.[field.key] ?? ''
  }
  // 进入非首阶段、非完成阶段时，自动将项目状态设为"进行中"
  if (state.currentStageKey !== 'reception' && state.currentStageKey !== 'completed') {
    if (stageFormData.projectStatus !== undefined) {
      stageFormData.projectStatus = stageFormData.projectStatus || 'in_progress'
    }
    state.projectStatus = 'in_progress'
  }
}

// 当用户在表单中切换项目状态时，同步到全局 workflowState（直接使用英文值）
watch(() => stageFormData.projectStatus, (val) => {
  if (!val) return
  const state = getWorkflowState(currentProjectId.value)
  if (!state || state.currentStageKey === 'completed') return
  // 直接将表单值（英文枚举）同步到全局状态
  state.projectStatus = val
})

const nextStageToAssign = computed(() => nextStageAfterReception.value || nextStageForAssignee.value)

/** 下一阶段可供同组指派的角色选项列表 */
const nextStageRoleOptions = computed(() => {
  const stage = nextStageToAssign.value
  if (!stage) return []
  if (Array.isArray(stage.assignRoles) && stage.assignRoles.length) return stage.assignRoles
  if (stage.role && stage.role !== '-') return [stage.role]
  return []
})

/** 接稿阶段指派是否就绪 */
const receptionAssignReady = computed(() => {
  if (assignMode.value === 'personal') return !!nextAssigneeUserId.value
  return !!groupAssignRole.value
})

/** 普通推进阶段指派是否就绪 */
const transitionAssignReady = computed(() => {
  if (assignMode.value === 'personal') return !!nextAssigneeUserId.value
  return !!groupAssignRole.value
})

// 切换指派模式时清空另一侧的值
watch(assignMode, (mode) => {
  if (mode === 'personal') {
    groupAssignRole.value = ''
  } else {
    nextAssigneeUserId.value = ''
    // 默认预填下一阶段的第一个角色
    const opts = nextStageRoleOptions.value
    if (opts.length && !groupAssignRole.value) groupAssignRole.value = opts[0]
  }
})

let _nextStageLoadVersion = 0

const stopNextStageWatch = watch(nextStageToAssign, async (stage) => {
  const version = ++_nextStageLoadVersion
  nextAssigneeUserId.value = ''
  groupAssignRole.value = ''
  assignMode.value = 'personal'
  if (!stage || (!stage.role && !stage.assignRoles) || stage.role === '-') {
    nextStageUsers.value = []
    return
  }
  nextStageUsersLoading.value = true
  try {
    let list = []
    // 支持单角色或多角色（如专检可由项目专员/客户专员承接）
    if (Array.isArray(stage.assignRoles) && stage.assignRoles.length) {
      const roleLists = await Promise.all(stage.assignRoles.map((r) => getUsersByRoleName(r)))
      if (version !== _nextStageLoadVersion) return
      const merged = roleLists.flat().filter(Boolean)
      const seen = new Set()
      list = merged.filter((u) => {
        const id = String(u.id)
        if (seen.has(id)) return false
        seen.add(id)
        return true
      })
    } else if (stage.role && stage.role !== '-') {
      list = await getUsersByRoleName(stage.role)
      if (version !== _nextStageLoadVersion) return
    }
    // 如果精确匹配角色名查不到用户，尝试加载全部用户作为候选（兜底）
    if (!list || list.length === 0) {
      const roleDesc = Array.isArray(stage.assignRoles) && stage.assignRoles.length
        ? stage.assignRoles.join(' / ')
        : stage.role
      console.warn(`未找到角色「${roleDesc}」对应的用户，将加载全部用户作为候选`)
      const { getUsers } = await import('@/api/users')
      const allUsers = await getUsers({ limit: 500 })
      if (version !== _nextStageLoadVersion) return
      list = Array.isArray(allUsers) ? allUsers : []
    }
    // 获取当前处于请假时段的员工，直接从候选名单中屏蔽
    try {
      const leaveList = await getOnLeaveUsers()
      if (version !== _nextStageLoadVersion) return
      const onLeaveIds = new Set((Array.isArray(leaveList) ? leaveList : []).map((r) => String(r.employee_id)))
      list = list.filter((u) => !onLeaveIds.has(String(u.id)))
    } catch {
      // 请假接口失败不阻塞选人
    }
    if (version !== _nextStageLoadVersion) return
    nextStageUsers.value = list
  } catch (e) {
    if (version !== _nextStageLoadVersion) return
    console.error(e)
    // 出错时也尝试加载全部用户
    try {
      const { getUsers } = await import('@/api/users')
      const allUsers = await getUsers({ limit: 500 })
      if (version !== _nextStageLoadVersion) return
      nextStageUsers.value = Array.isArray(allUsers) ? allUsers : []
    } catch {
      nextStageUsers.value = []
    }
  } finally {
    if (version === _nextStageLoadVersion) nextStageUsersLoading.value = false
  }
}, { immediate: true })

onUnmounted(() => {
  stopNextStageWatch()
  _nextStageLoadVersion++
})

const projectProgress = computed(() => {
  const p = currentProject.value
  if (!p) return {}
  return {
    orderNo: p.orderNo,
    projectName: p.projectName,
    clientShortName: p.clientShortName,
    clientCode: p.clientCode,
    customerReceptionTime: p.customerReceptionTime,
    customerDeadlineTime: p.customerDeadlineTime,
    languagePair: p.languagePair,
    priority: p.priority,
    wordCount: p.wordCount,
    translatorCooperationType: p.translatorCooperationType,
    translatorAssignee: p.translatorAssignee,
    translatorAssignmentTime: p.translatorAssignmentTime,
    translatorDeliveryProgress: p.translatorDeliveryProgress,
    review1Progress: p.review1Progress,
    preReviewQcProgress: p.preReviewQcProgress,
    layoutProgress: p.layoutProgress,
    consolidationProgress: p.consolidationProgress,
    sentToClientTime: p.sentToClientTime,
    clientFeedback: p.clientFeedback,
    postReviewQcProgress: p.postReviewQcProgress,
    review2Progress: p.review2Progress
  }
})

function formatDateTime(d) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function difficultyLabel(d) {
  const map = { simple: '简单', normal: '普通', complex: '复杂' }
  return map[d] || d
}

function getStatusLabel(status) {
  const map = { pending: '待启动', in_progress: '进行中', completed: '已完成', paused: '已暂停', terminated: '已终止' }
  return map[status] || status || '待启动'
}

function getStatusType(status) {
  const map = { pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger', terminated: 'info' }
  return map[status] || 'info'
}


async function confirmDifficulty() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state || !pendingDifficulty.value || pendingFileEditable.value === null) return
  if (!receptionAssignReady.value) return
  if (!canOperateCurrentStage.value) return

  if (assignMode.value === 'personal') {
    const selectedUser = nextStageUsers.value.find(u => u.id === nextAssigneeUserId.value)
    if (selectedUser && selectedUser.onLeave) {
      ElMessage.error('该负责人处于请假状态，无法被指派')
      return
    }
  }

  const note = handoverNote.value?.trim() || '（无备注）'
  const payload = {
    difficulty: pendingDifficulty.value,
    file_editable: pendingFileEditable.value,
    note: note,
    stage_data: { ...stageFormData }
  }
  if (assignMode.value === 'personal') {
    payload.next_assignee_id = nextAssigneeUserId.value
  } else {
    payload.group_assign_role = groupAssignRole.value
  }

  try {
    const isGroupAssign = assignMode.value === 'group'
    const assignedRole = payload.group_assign_role
    const apiFn = currentEntityType.value === 'suborder' ? setSubOrderDifficultyAPI : setDifficultyAPI
    const res = await apiFn(currentProjectId.value, payload)
    setWorkflowState(currentProjectId.value, res)
    handoverNote.value = ''
    nextAssigneeUserId.value = ''
    groupAssignRole.value = ''
    assignMode.value = 'personal'
    pendingDifficulty.value = null
    pendingFileEditable.value = null
    initStageFormData()
    ElMessage.success(
      isGroupAssign
        ? `难度已确认，已同组指派给「${assignedRole}」，流程已推进`
        : '难度已确认，已指定下一环节负责人，流程已推进'
    )
    loadProjects()
  } catch (e) {
    console.error('设定难度失败', e)
    ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
  }
}

async function saveCurrentStageProgress() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  if (!canOperateCurrentStage.value) return
  try {
    const apiFn = currentEntityType.value === 'suborder' ? updateSubOrderStageDataAPI : updateStageDataAPI
    const res = await apiFn(currentProjectId.value, {
      stage_data: { ...stageFormData }
    })
    setWorkflowState(currentProjectId.value, res)
    ElMessage.success('本阶段进度已更新（暂存）')
  } catch (e) {
    console.error('暂存数据失败', e)
    ElMessage.error('暂存数据失败：' + (e.response?.data?.detail || e.message))
  }
}

async function completeCurrentStage() {
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  if (!canOperateCurrentStage.value) return

  const steps = getEffectiveStages(state.difficulty, state.fileEditable)
  const idx = steps.findIndex((s) => s.key === state.currentStageKey)
  if (idx < 0) return
  const nextIdx = idx + 1
  const next = nextIdx < steps.length ? steps[nextIdx] : null

  // 需要指派且未就绪则阻止
  if (next && next.key !== 'completed' && !transitionAssignReady.value) return

  if (assignMode.value === 'personal' && nextAssigneeUserId.value) {
    const selectedUser = nextStageUsers.value.find(u => u.id === nextAssigneeUserId.value)
    if (selectedUser && selectedUser.onLeave) {
      ElMessage.error('该负责人处于请假状态，无法被指派')
      return
    }
  }

  const note = handoverNote.value?.trim() || '（无备注）'
  const currentStageData = { ...stageFormData }
  if (currentStageData.actualTime === undefined || currentStageData.actualTime === '') {
    currentStageData.actualTime = formatDateTime(new Date())
  }

  const payload = { note, stage_data: currentStageData }
  if (next && next.key !== 'completed') {
    if (assignMode.value === 'personal') {
      payload.next_assignee_id = nextAssigneeUserId.value
    } else {
      payload.group_assign_role = groupAssignRole.value
    }
  }

  try {
    const isGroupAssign = assignMode.value === 'group'
    const assignedRole = payload.group_assign_role
    const transitionApiFn = currentEntityType.value === 'suborder' ? transitionSubOrderWorkflowAPI : transitionWorkflowAPI
    const res = await transitionApiFn(currentProjectId.value, payload)
    setWorkflowState(currentProjectId.value, res)
    handoverNote.value = ''
    nextAssigneeUserId.value = ''
    groupAssignRole.value = ''
    assignMode.value = 'personal'
    initStageFormData()
    let successMsg = '本阶段已完成'
    if (next && next.key !== 'completed') {
      successMsg = isGroupAssign
        ? `本阶段已完成，已同组指派给「${assignedRole}」，流程已推进`
        : '本阶段已完成，已指定下一环节负责人，流程已推进'
    }
    ElMessage.success(successMsg)
    loadProjects()
  } catch (e) {
    console.error('流转推进失败', e)
    ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
  }
}

function openRollbackDialog(steps, toStart = false) {
  rollbackSteps.value = steps
  rollbackToStart.value = !!toStart
  rollbackNote.value = ''
  rollbackDialogVisible.value = true
}

function handleRollbackDialogClose() {
  rollbackNote.value = ''
  rollbackSteps.value = 1
  rollbackToStart.value = false
}

async function confirmRollback() {
  const note = rollbackNote.value?.trim()
  if (!note) return
  const state = getWorkflowState(currentProjectId.value)
  if (!state) return
  
  try {
    const rollbackApiFn = currentEntityType.value === 'suborder' ? rollbackSubOrderWorkflowAPI : rollbackWorkflowAPI
    const res = await rollbackApiFn(currentProjectId.value, {
      steps: rollbackSteps.value,
      to_start: rollbackToStart.value,
      note: note
    })
    setWorkflowState(currentProjectId.value, res)
    rollbackDialogVisible.value = false
    handleRollbackDialogClose()
    handoverNote.value = ''
    initStageFormData()
    ElMessage.success(currentEntityType.value === 'suborder' ? '已成功打回子订单' : '已成功打回项目')
    loadProjects()
  } catch (e) {
    console.error('打回失败', e)
    ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
  }
}

async function loadProjects() {
  try {
    const tasks = await getMyTasksAPI()
    myTaskProjectsList.value = Array.isArray(tasks) ? tasks : []
  } catch (e) {
    console.error('获取待我处理任务失败', e)
    myTaskProjectsList.value = []
  }

  try {
    await loadMixedOptions()
    if (currentProjectId.value) {
      if (currentEntityType.value === 'project') {
        await ensureProjectLoaded(currentProjectId.value)
      }
    } else if (projectList.value.length) {
      currentEntityType.value = 'project'
      currentProjectId.value = projectList.value[0].id
      currentEntityKey.value = `project:${projectList.value[0].id}`
      await fetchWorkflowState()
    }
  } catch (e) {
    console.error(e)
    projectList.value = []
  }
}

function getRouteProjectId() {
  const value = route.query.projectId
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}


function getRouteTab() {
  const value = route.query.tab
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function openProjectChatDrawer() {
  if (!canOpenProjectChat.value) return
  chatDrawerVisible.value = true
}

function clearChatTabFromRoute() {
  if (getRouteTab() !== 'chat') return
  const nextQuery = { ...route.query }
  delete nextQuery.tab
  router.replace({ path: route.path, query: nextQuery }).catch(() => {})
}

function handleChatDrawerClose() {
  chatDrawerVisible.value = false
  clearChatTabFromRoute()
}

async function ensureProjectLoaded(projectId) {
  if (!projectId) return
  const projectIdText = String(projectId)
  const exists = projectList.value.some((project) => String(project.id) === projectIdText)
  if (exists) {
    selectedProjectRow.value = null
    return
  }

  try {
    const project = await getProject(projectIdText)
    if (!project?.id) return
    selectedProjectRow.value = project
    projectList.value = [
      project,
      ...projectList.value.filter((item) => String(item.id) !== projectIdText)
    ]
  } catch (e) {
    console.error('Failed to load selected project', e)
  }
}

async function fetchWorkflowState() {
  if (!currentProjectId.value) return
  try {
    if (currentEntityType.value === 'suborder') {
      let state
      try {
        state = await getSubOrderWorkflowStateAPI(currentProjectId.value)
      } catch (err) {
        // 工作流未初始化（404），自动初始化
        if (err?.response?.status === 404 || err?.status === 404) {
          state = await initSubOrderWorkflowAPI(currentProjectId.value)
        } else {
          throw err
        }
      }
      setWorkflowState(currentProjectId.value, state)
      initStageFormData()
    } else {
      await ensureProjectLoaded(currentProjectId.value)
      let state
      try {
        state = await getWorkflowStateAPI(currentProjectId.value)
      } catch (err) {
        if (err?.response?.status === 404 || err?.status === 404) {
          state = await initWorkflowAPI(currentProjectId.value)
        } else {
          throw err
        }
      }
      setWorkflowState(currentProjectId.value, state)
      initStageFormData()
    }
  } catch (e) {
    console.error('获取流程状态失败', e)
  }
}

function onProjectChange() {
  selectedProjectRow.value = null
  handoverNote.value = ''
  nextAssigneeUserId.value = ''
  groupAssignRole.value = ''
  assignMode.value = 'personal'
  pendingDifficulty.value = null
  pendingFileEditable.value = null
  if (currentEntityType.value === 'suborder') chatDrawerVisible.value = false
  fetchWorkflowState()
}

function selectProject(projectIdOrRow) {
  const isRow = projectIdOrRow != null && typeof projectIdOrRow === 'object' && 'id' in projectIdOrRow
  if (isRow) {
    currentProjectId.value = projectIdOrRow.id
    selectedProjectRow.value = projectIdOrRow
  } else {
    currentProjectId.value = projectIdOrRow
    selectedProjectRow.value = null
  }
  handoverNote.value = ''
  nextAssigneeUserId.value = ''
  groupAssignRole.value = ''
  assignMode.value = 'personal'
  pendingDifficulty.value = null
  pendingFileEditable.value = null
  fetchWorkflowState()
  activeTab.value = 'overview'
  nextTick(() => {
    const el = stageCardRef.value?.$el ?? stageCardRef.value
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function onMyTaskRowClick(row) {
  if (!row) return
  if (row.entity_type === 'suborder' && row.sub_order_id) {
    // 子订单任务
    currentEntityType.value = 'suborder'
    currentSubOrder.value = { id: row.sub_order_id, subOrderNo: row.sub_order_no || row.subOrderNo || row.orderNo || '' }
    currentProjectId.value = row.sub_order_id
    currentEntityKey.value = `suborder:${row.sub_order_id}`
    selectedProjectRow.value = null
    handoverNote.value = ''
    nextAssigneeUserId.value = ''
    groupAssignRole.value = ''
    assignMode.value = 'personal'
    pendingDifficulty.value = null
    chatDrawerVisible.value = false
    pendingFileEditable.value = null
    fetchWorkflowState()
    activeTab.value = 'overview'
  } else {
    // 母订单任务
    const projectId = row.translation_project_id || row.id
    currentEntityType.value = 'project'
    currentSubOrder.value = null
    currentEntityKey.value = `project:${projectId}`
    selectProject(projectId)
  }
}

watch(
  () => [activeTab.value, currentProjectId.value],
  ([tab, projectId]) => {
    if (tab === 'files' && projectId) {
      loadProjectFiles()
    }
    if (tab === 'files' && !projectId) {
      fileList.value = []
    }
  }
)

watch(
  () => [route.query.projectId, route.query.tab],
  async () => {
    const routeProjectId = getRouteProjectId()
    const routeTab = getRouteTab()
    chatDrawerVisible.value = routeTab === 'chat'
    if (!routeProjectId) return

    const projectChanged = currentEntityType.value !== 'project' || String(currentProjectId.value || '') !== String(routeProjectId)
    if (!projectChanged) return

    selectedProjectRow.value = null
    handoverNote.value = ''
    nextAssigneeUserId.value = ''
    groupAssignRole.value = ''
    assignMode.value = 'personal'
    pendingDifficulty.value = null
    pendingFileEditable.value = null
    currentEntityType.value = 'project'
    currentSubOrder.value = null
    currentProjectId.value = routeProjectId
    currentEntityKey.value = `project:${routeProjectId}`
    activeTab.value = 'overview'
    await fetchWorkflowState()
  },
  { immediate: true }
)

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.translation-projects-page {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}

.card-header__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-left: auto;
}

.chat-entry-button {
  flex-shrink: 0;
}

.workflow-steps {
  margin-bottom: 24px;
}

/* 正在进行中的阶段使用高对比橙色高亮，和已完成绿色区分 */
.workflow-steps :deep(.el-step.is-current-stage .el-step__head .el-step__icon) {
  background: var(--el-color-warning-light-7);
  border-color: var(--el-color-warning);
  color: var(--el-color-warning-dark-2);
}

.workflow-steps :deep(.el-step.is-current-stage .el-step__title) {
  color: var(--el-color-warning-dark-2);
  font-weight: 700;
}

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

.empty-stage {
  margin: 40px 0;
}

.empty-stage .empty-hint {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.rollback-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.detail-tabs {
  margin-top: 8px;
}

.project-chat-drawer :deep(.el-drawer__header) {
  margin-bottom: 8px;
}

.project-chat-drawer :deep(.el-drawer__body) {
  padding-top: 0;
}

.project-chat-drawer__title {
  font-size: 16px;
  font-weight: 600;
}

.project-chat-drawer__subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.log-filter-bar {
  margin-bottom: 12px;
}

.log-action {
  margin: 0 0 4px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-note {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 6px 0 0 0;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
}

.log-operator {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}

.log-rollback {
  border-left: 3px solid var(--el-color-danger);
}
</style>





