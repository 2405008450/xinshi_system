<template>
  <div class="manuscript-page">
    <div class="page-header">
      <div>
        <h1>稿件安排</h1>
      </div>
      <div class="header-actions">
        <el-tooltip :content="mailStatus.detail || '正在读取邮件配置'" placement="bottom">
          <el-tag :type="mailStatusTagType" effect="plain">{{ mailStatusLabel }}</el-tag>
        </el-tooltip>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <div class="legacy-workbench">
      <div class="legacy-workbench__left">
        <el-card class="legacy-project-panel" shadow="never">
          <template #header>
            <div class="panel-header">
              <div>
                <h2>稿件 / 项目列表</h2>
                <span>选择需要安排译员的母订单或子订单</span>
              </div>
              <div class="panel-tools">
                <el-input
                  v-model="projectKeyword"
                  clearable
                  placeholder="订单号、项目或客户"
                  @keyup.enter="loadContext"
                  @clear="loadContext"
                />
                <el-button type="primary" :loading="contextLoading" @click="loadContext">查询</el-button>
              </div>
            </div>
          </template>

          <el-table
            v-loading="contextLoading"
            :data="activeProjects"
            height="100%"
            size="small"
            border
            highlight-current-row
            :row-class-name="projectRowClassName"
            @current-change="selectProject"
            @row-dblclick="selectProject"
          >
            <el-table-column type="index" label="" width="48" align="center" />
            <el-table-column prop="order_no" label="订单号" width="170" show-overflow-tooltip />
            <el-table-column label="稿件 / 项目名称" min-width="230" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="strong-text">{{ row.sub_project_name || row.project_name }}</div>
                <small>{{ row.client_short_name || '未填写客户' }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="language_pair" label="语种" width="105" show-overflow-tooltip />
            <el-table-column label="字数摘要" width="180">
              <template #default="{ row }">{{ projectWordSummary(row) }}</template>
            </el-table-column>
            <el-table-column label="客户交稿时间" width="155">
              <template #default="{ row }">
                <span :class="{ 'deadline-overdue': isOverdue(row.customer_deadline_time) }">
                  {{ formatDateTime(row.customer_deadline_time) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="projectStatusType(row.project_status)" size="small">
                  {{ projectStatusLabel(row.project_status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="legacy-translator-panel" shadow="never">
          <template #header>
            <div class="panel-header translator-header">
              <div>
                <h2>译员列表</h2>
                <span>可勾选多位译员，右侧逐位填写合作信息</span>
              </div>
              <div class="translator-header__tools">
                <el-input v-model="translatorKeyword" clearable placeholder="姓名、编号或语种" />
                <el-button
                  :type="showTranslatorCode ? 'primary' : 'default'"
                  :plain="!showTranslatorCode"
                  @click="showTranslatorCode = !showTranslatorCode"
                >
                  {{ showTranslatorCode ? '收起编号' : '展开编号' }}
                </el-button>
              </div>
            </div>
          </template>

          <el-tabs v-model="translatorTab" class="translator-tabs">
            <el-tab-pane :label="`兼取译员 ${translatorCounts.total}`" name="all" />
            <el-tab-pane :label="`全职 ${translatorCounts.fullTime}`" name="full_time" />
            <el-tab-pane :label="`兼职 ${translatorCounts.partTime}`" name="part_time" />
            <el-tab-pane :label="`其他 ${translatorCounts.other}`" name="other" />
          </el-tabs>

          <div class="translator-table-wrap">
            <el-table
              ref="workspaceTranslatorTableRef"
              :data="filteredTranslators"
              row-key="id"
              height="100%"
              size="small"
              border
              highlight-current-row
              @selection-change="handleWorkspaceTranslatorSelection"
              @row-click="activateTranslatorRow"
            >
              <el-table-column type="selection" width="44" :reserve-selection="true" />
              <el-table-column type="index" label="" width="42" align="center" />
              <el-table-column
                v-if="showTranslatorCode"
                prop="translator_code"
                label="译员编号"
                width="105"
                show-overflow-tooltip
              />
              <el-table-column prop="translator_name" label="译员姓名" width="110" show-overflow-tooltip />
              <el-table-column label="译员合作形式" width="115">
                <template #default="{ row }">{{ cooperationLabel(row) }}</template>
              </el-table-column>
              <el-table-column label="译员确认" width="145">
                <template #default="{ row }">{{ row.available_time_slot || '-' }}</template>
              </el-table-column>
              <el-table-column label="语种 / 能力" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <div>{{ row.languages || row.direction || '-' }}</div>
                  <small>{{ formatDomains(row.domain_skills) }}</small>
                </template>
              </el-table-column>
              <el-table-column label="备注" min-width="170" show-overflow-tooltip>
                <template #default="{ row }">{{ row.remarks || '-' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </div>

      <el-card class="legacy-assignment-panel" shadow="never">
        <template #header>
          <div class="legacy-assignment-panel__header">
            <div>
              <h2>译员派稿信息</h2>
              <span v-if="selectedProject">
                {{ selectedProject.order_no }} · {{ selectedProject.sub_project_name || selectedProject.project_name }}
              </span>
              <span v-else>请先从左上方选择稿件</span>
            </div>
            <el-tag
              v-if="selectedProjectDispatch"
              :type="dispatchStatusMeta(selectedProjectDispatch.status).type"
              size="small"
            >
              {{ dispatchStatusMeta(selectedProjectDispatch.status).label }}
            </el-tag>
          </div>
        </template>

        <el-empty v-if="!selectedProject" description="选择稿件后在此填写译员合作信息" :image-size="72" />
        <div v-else class="legacy-assignment-body">
          <div class="legacy-project-meta">
            <span>项目字数：{{ projectWordSummary(selectedProject) }}</span>
            <span>客户交稿：{{ formatDateTime(selectedProject.customer_deadline_time) }}</span>
          </div>

          <el-alert
            v-if="!dispatchForm.arrangements.length"
            title="请从左下方勾选至少一位译员"
            type="info"
            :closable="false"
            show-icon
          />
          <template v-else>
            <el-alert
              v-if="!selectedProjectDispatch && selectedProjectCancelledDispatch"
              title="已载入最近取消的安排参数，可修改后重新保存或确认"
              type="warning"
              :closable="false"
              show-icon
            />
            <el-tabs v-model="activeArrangementTranslatorId" class="assignment-tabs">
              <el-tab-pane
                v-for="assignment in dispatchForm.arrangements"
                :key="assignment.translator_id"
                :label="translatorById(assignment.translator_id)?.translator_name || '译员'"
                :name="assignment.translator_id"
              />
            </el-tabs>

            <div v-if="activeWorkbenchAssignment" class="legacy-field-grid">
              <label>译员合作形式</label>
              <div class="legacy-readonly-value">
                {{ cooperationLabel(activeWorkbenchTranslator || {}) }}
                · {{ activeWorkbenchTranslator?.translator_name || '-' }}
              </div>

              <label>字数与结算</label>
              <div class="legacy-word-count-summary">
                <span>{{ assignmentWordSummary(activeWorkbenchAssignment) }}</span>
                <el-button
                  type="primary"
                  link
                  @click="openWordCountDrawer(activeWorkbenchAssignment, workbenchReadonly)"
                >
                  展开字数详情
                </el-button>
              </div>

              <label>需翻译部分</label>
              <el-input
                v-model="activeWorkbenchAssignment.translation_scope"
                type="textarea"
                :rows="2"
                :disabled="workbenchReadonly"
                placeholder="如：第1-20页、文档A或具体章节范围"
              />

              <template
                v-for="milestone in activeWorkbenchAssignment.milestones"
                :key="`${activeWorkbenchAssignment.translator_id}-${milestone.sequence_no}`"
              >
                <label>{{ legacyMilestoneName(milestone) }}</label>
                <el-date-picker
                  v-model="milestone.planned_at"
                  type="datetime"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  :disabled="workbenchReadonly"
                  placeholder="选择预定时间"
                  style="width: 100%"
                />
              </template>

              <label>译员结账方式</label>
              <el-select
                v-model="activeWorkbenchAssignment.settlement_method"
                clearable
                :disabled="workbenchReadonly"
                style="width: 100%"
              >
                <el-option label="单结" value="single" />
                <el-option label="月结" value="monthly" />
                <el-option label="预付" value="prepaid" />
                <el-option label="其他" value="other" />
              </el-select>

              <template v-if="activeWorkbenchAssignment.settlement_method === 'other'">
                <label>其他结账方式</label>
                <el-input
                  v-model="activeWorkbenchAssignment.custom_settlement_method"
                  :disabled="workbenchReadonly"
                  maxlength="100"
                />
              </template>

              <label>译员单价</label>
              <el-input-number
                v-model="activeWorkbenchAssignment.translator_unit_price"
                :min="0"
                :precision="4"
                controls-position="right"
                :disabled="workbenchReadonly"
                style="width: 100%"
              />

              <label>译员总价</label>
              <el-input-number
                v-model="activeWorkbenchAssignment.translator_total_price"
                :min="0"
                :precision="2"
                controls-position="right"
                :disabled="workbenchReadonly"
                style="width: 100%"
              />

              <label>备注</label>
              <el-input
                v-model="activeWorkbenchAssignment.remarks"
                type="textarea"
                :rows="2"
                :disabled="workbenchReadonly"
                maxlength="5000"
              />
            </div>

            <el-divider />

            <div class="legacy-mail-fields">
              <label>发稿文件路径</label>
              <el-input :model-value="selectedProject.network_file_path || ''" readonly />
              <label>参考文件路径一</label>
              <el-input :model-value="selectedProject.reference_file_path_one || ''" readonly />
              <label>译员邮箱</label>
              <el-input :model-value="preferredEmail(activeWorkbenchTranslator || {})" readonly />
            </div>

            <el-collapse v-if="activeWorkbenchAssignment" class="legacy-mail-editor">
              <el-collapse-item title="邮件标题与正文" name="mail">
                <el-input
                  v-model="activeWorkbenchAssignment.email_subject"
                  :disabled="workbenchReadonly"
                  placeholder="邮件标题"
                />
                <el-input
                  v-model="activeWorkbenchAssignment.email_body"
                  type="textarea"
                  :rows="7"
                  :disabled="workbenchReadonly"
                  placeholder="邮件正文"
                  class="mail-body-input"
                />
              </el-collapse-item>
            </el-collapse>

            <div class="legacy-actions">
              <template v-if="canWrite && !workbenchReadonly">
                <el-button :loading="saving" @click="saveDraft(false)">保存草稿</el-button>
                <el-button type="primary" :loading="saving" @click="saveDraft(true)">确认安排</el-button>
              </template>
              <template v-else-if="canWrite && selectedProjectDispatch">
                <el-button
                  v-if="activeExistingArrangement && ['ready', 'failed'].includes(activeExistingArrangement.status)"
                  type="primary"
                  :loading="sendingId === activeExistingArrangement.id"
                  :disabled="!mailStatus.configured"
                  @click="sendActiveWorkbenchAssignment"
                >
                  发送稿件
                </el-button>
                <el-button
                  v-if="['ready', 'partially_sent'].includes(selectedProjectDispatch.status)"
                  :loading="sendingBatchId === selectedProjectDispatch.id"
                  :disabled="!mailStatus.configured"
                  @click="sendBatch(selectedProjectDispatch)"
                >
                  批量发送
                </el-button>
                <el-tag v-if="activeExistingArrangement?.status === 'sent'" type="success">该译员已发送</el-tag>
              </template>
            </div>
          </template>
        </div>
      </el-card>
    </div>

    <el-card v-if="false && selectedProject" class="panel-card dispatch-overview" shadow="never">
      <template #header>
        <div class="panel-header">
          <div>
            <h2>所选批次概览</h2>
            <span>{{ selectedProject.order_no }} · {{ selectedProject.sub_project_name || selectedProject.project_name }}</span>
          </div>
          <div class="panel-tools">
            <el-tag
              v-if="selectedProjectDispatch"
              :type="dispatchStatusMeta(selectedProjectDispatch.status).type"
              size="small"
            >
              {{ dispatchStatusMeta(selectedProjectDispatch.status).label }}
            </el-tag>
            <el-button
              v-if="canWrite && selectedProjectDispatch?.status === 'draft'"
              type="primary"
              link
              size="small"
              @click="editDraft(selectedProjectDispatch)"
            >
              完整编辑
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!selectedProjectDispatch" class="overview-empty">
        该项目暂无稿件安排批次，可在下方选择订单与译员后新建。
      </div>

      <div v-else>
        <div class="overview-meta">
          <span>创建人：{{ selectedProjectDispatch.created_by_name || '-' }}</span>
          <span>创建时间：{{ formatDateTime(selectedProjectDispatch.created_at) }}</span>
          <span>人数：{{ activeAssignments(selectedProjectDispatch).length }}</span>
          <span>预定结算字数：{{ formatInteger(sumField(selectedProjectDispatch, 'planned_word_count')) }}</span>
          <span>实际结算字数：{{ formatInteger(sumField(selectedProjectDispatch, 'actual_word_count', true)) }}</span>
          <span>译员总价：{{ formatMoney(sumField(selectedProjectDispatch, 'translator_total_price', true)) }}</span>
        </div>

        <el-table :data="inlineSettlement" border size="small" class="overview-table">
          <el-table-column label="译员 / 译员合作形式" width="180">
            <template #default="{ row }">
              <div class="strong-text">{{ row.translator_name_snapshot }}</div>
              <small>{{ cooperationLabel(row) }}</small>
            </template>
          </el-table-column>
          <el-table-column label="字数与口径" width="230">
            <template #default="{ row }">
              <div>{{ assignmentWordSummary(row) }}</div>
              <el-button
                v-if="canWrite"
                type="primary"
                link
                size="small"
                :disabled="row.status === 'cancelled'"
                @click="openWordCountDrawer(row, row.status === 'cancelled')"
              >
                编辑字数详情
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="需翻译部分" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.translation_scope || '-' }}</template>
          </el-table-column>
          <el-table-column label="译员交稿_预定时间" min-width="230">
            <template #default="{ row }">
              <div
                v-for="milestone in row.milestones"
                :key="milestone.id || `${row.id}-${milestone.sequence_no}`"
                class="milestone-line"
              >
                {{ legacyMilestoneName(milestone) }}：{{ formatDateTime(milestone.planned_at) }}
              </div>
            </template>
          </el-table-column>
          <template v-if="canWrite">
            <el-table-column label="译员结账方式" width="140">
              <template #default="{ row }">
                <el-select
                  v-model="row.settlement_method"
                  size="small"
                  clearable
                  style="width: 100%"
                  :disabled="row.status === 'cancelled'"
                >
                  <el-option label="单结" value="single" />
                  <el-option label="月结" value="monthly" />
                  <el-option label="预付" value="prepaid" />
                  <el-option label="其他" value="other" />
                </el-select>
                <el-input
                  v-if="row.settlement_method === 'other'"
                  v-model="row.custom_settlement_method"
                  size="small"
                  maxlength="100"
                  placeholder="自定义结算方式"
                  style="margin-top: 4px"
                />
              </template>
            </el-table-column>
            <el-table-column label="译员单价" width="110">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.translator_unit_price"
                  :min="0"
                  :precision="4"
                  size="small"
                  controls-position="right"
                  style="width: 100%"
                  :disabled="row.status === 'cancelled'"
                />
              </template>
            </el-table-column>
            <el-table-column label="译员总价" width="110">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.translator_total_price"
                  :min="0"
                  :precision="2"
                  size="small"
                  controls-position="right"
                  style="width: 100%"
                  :disabled="row.status === 'cancelled'"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  link
                  size="small"
                  :loading="inlineSavingId === row.id"
                  :disabled="row.status === 'cancelled'"
                  @click="saveInlineSettlement(row)"
                >
                  保存
                </el-button>
              </template>
            </el-table-column>
          </template>
          <template v-else>
            <el-table-column label="译员结账方式" min-width="180">
              <template #default="{ row }">
                <div>{{ settlementLabel(row) }}</div>
                <small>单价 {{ formatMoney(row.translator_unit_price) }} / 总价 {{ formatMoney(row.translator_total_price) }}</small>
              </template>
            </el-table-column>
          </template>
        </el-table>
      </div>
    </el-card>

    <div v-if="false" class="workspace-grid">
      <el-card class="panel-card project-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <div>
              <h2>进行中项目</h2>
              <span>选择需要安排稿件的母订单或子订单</span>
            </div>
            <div class="panel-tools">
              <el-input
                v-model="projectKeyword"
                clearable
                placeholder="订单号、项目、客户或负责人"
                @keyup.enter="loadContext"
                @clear="loadContext"
              />
              <el-button type="primary" :loading="contextLoading" @click="loadContext">查询</el-button>
            </div>
          </div>
        </template>

        <el-table
          v-loading="contextLoading"
          :data="activeProjects"
          height="430"
          size="small"
          border
          highlight-current-row
          :row-class-name="projectRowClassName"
          @current-change="selectProject"
          @row-dblclick="selectProject"
        >
          <el-table-column prop="order_no" label="订单号" width="170" show-overflow-tooltip />
          <el-table-column label="项目" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="strong-text">{{ row.sub_project_name || row.project_name }}</div>
              <small>{{ row.client_short_name || '未填写客户' }}</small>
            </template>
          </el-table-column>
          <el-table-column prop="language_pair" label="语种" width="100" show-overflow-tooltip />
          <el-table-column label="项目字数摘要" width="180">
            <template #default="{ row }">{{ projectWordSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="客户交稿时间" width="155">
            <template #default="{ row }">
              <span :class="{ 'deadline-overdue': isOverdue(row.customer_deadline_time) }">
                {{ formatDateTime(row.customer_deadline_time) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="105">
            <template #default="{ row }">
              <el-tag :type="projectStatusType(row.project_status)" size="small">
                {{ projectStatusLabel(row.project_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="75" fixed="right" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="selectProject(row)">选择</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">当前显示 {{ activeProjects.length }} 条进行中记录</div>
      </el-card>

      <el-card class="panel-card translator-panel" shadow="never">
        <template #header>
          <div class="panel-header translator-header">
            <div>
              <h2>译员资源</h2>
              <span>可直接勾选一位或多位译员</span>
            </div>
            <el-input v-model="translatorKeyword" clearable placeholder="姓名、编号或语种" />
          </div>
        </template>

        <el-tabs v-model="translatorTab" class="translator-tabs">
          <el-tab-pane :label="`全部 ${translatorCounts.total}`" name="all" />
          <el-tab-pane :label="`全职 ${translatorCounts.fullTime}`" name="full_time" />
          <el-tab-pane :label="`兼职 ${translatorCounts.partTime}`" name="part_time" />
          <el-tab-pane :label="`其他 ${translatorCounts.other}`" name="other" />
        </el-tabs>

        <el-table
          ref="workspaceTranslatorTableRef"
          :data="filteredTranslators"
          row-key="id"
          height="365"
          size="small"
          border
          @selection-change="handleWorkspaceTranslatorSelection"
        >
          <el-table-column type="selection" width="44" :reserve-selection="true" />
          <el-table-column label="类型" width="74">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ cooperationLabel(row) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="译员" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="strong-text">{{ row.translator_name }}</div>
              <small>{{ row.translator_code || '暂无编号' }}</small>
            </template>
          </el-table-column>
          <el-table-column label="能力" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <div>{{ row.languages || row.direction || '-' }}</div>
              <small>{{ formatDomains(row.domain_skills) }}</small>
            </template>
          </el-table-column>
          <el-table-column label="邮箱" min-width="145" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="preferredEmail(row)">{{ preferredEmail(row) }}</span>
              <el-tag v-else type="danger" size="small">未填写</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="68">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '活跃' : '备用' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">当前分组 {{ filteredTranslators.length }} 名，已选 {{ workspaceSelectedTranslators.length }} 名</div>
      </el-card>
    </div>

    <el-card v-if="false" class="selection-card" shadow="never">
      <div class="selection-bar">
        <div class="selection-item">
          <span class="selection-label">已选订单</span>
          <strong v-if="selectedProject">
            {{ selectedProject.order_no }} ·
            {{ selectedProject.sub_project_name || selectedProject.project_name }}
          </strong>
          <em v-else>请从左侧选择订单</em>
        </div>
        <div class="selection-divider" />
        <div class="selection-item selection-item--translators">
          <span class="selection-label">已选译员</span>
          <strong v-if="workspaceSelectedTranslators.length">
            {{ workspaceSelectedTranslatorSummary }}
          </strong>
          <em v-else>请从右侧勾选译员</em>
        </div>
        <el-button
          v-if="canWrite"
          type="primary"
          size="large"
          :disabled="!selectedProject || !workspaceSelectedTranslators.length"
          @click="openCreateDialog"
        >
          新建稿件安排
        </el-button>
        <el-tag v-else type="info">当前账号仅可查看</el-tag>
      </div>
    </el-card>

    <el-card class="panel-card records-panel" shadow="never">
      <template #header>
        <div class="panel-header">
          <div>
            <h2>稿件安排记录</h2>
            <span>按派稿批次汇总，展开后查看每位译员的分工与发送结果</span>
          </div>
          <div class="panel-tools">
            <el-input
              v-model="dispatchKeyword"
              clearable
              placeholder="搜索订单、项目、译员或邮箱"
              @keyup.enter="loadDispatches"
              @clear="loadDispatches"
            />
            <el-button :loading="recordsLoading" @click="loadDispatches">查询</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="recordsLoading"
        :data="dispatches"
        row-key="id"
        border
        size="small"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="assignment-detail-wrap">
              <el-table :data="row.arrangements || []" border size="small">
                <el-table-column label="状态" width="92">
                  <template #default="{ row: item }">
                    <el-tag :type="assignmentStatusMeta(item.status).type" size="small">
                      {{ assignmentStatusMeta(item.status).label }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="译员 / 译员合作形式" width="180">
                  <template #default="{ row: item }">
                    <div>{{ item.translator_name_snapshot }}</div>
                    <small>{{ cooperationLabel(item) }}</small>
                  </template>
                </el-table-column>
                <el-table-column prop="translation_scope" label="需翻译部分" min-width="180" show-overflow-tooltip />
                <el-table-column label="译员结算字数" width="220">
                  <template #default="{ row: item }">
                    {{ assignmentWordSummary(item) }}
                  </template>
                </el-table-column>
                <el-table-column label="译员交稿_全稿预定时间" width="205">
                  <template #default="{ row: item }">{{ formatDateTime(item.planned_delivery_at) }}</template>
                </el-table-column>
                <el-table-column label="译员结账方式" width="170">
                  <template #default="{ row: item }">
                    <div>{{ settlementLabel(item) }}</div>
                    <small>单价 {{ formatMoney(item.translator_unit_price) }} / 总价 {{ formatMoney(item.translator_total_price) }}</small>
                  </template>
                </el-table-column>
                <el-table-column label="译员交稿_预定时间" min-width="230">
                  <template #default="{ row: item }">
                    <div
                      v-for="milestone in item.milestones || []"
                      :key="milestone.id || `${item.id}-${milestone.sequence_no}`"
                      class="milestone-line"
                    >
                      {{ legacyMilestoneName(milestone) }}：{{ formatDateTime(milestone.planned_at) }}
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="邮件投递" min-width="180" show-overflow-tooltip>
                  <template #default="{ row: item }">
                    <span v-if="item.status === 'sent'">
                      {{ item.delivery_mode === 'test' ? '测试收件箱' : '译员邮箱' }}
                      · {{ item.delivery_recipient }}
                    </span>
                    <span v-else-if="item.status === 'failed'" class="delivery-error">
                      {{ item.send_error || '发送失败' }}
                    </span>
                    <span v-else>{{ item.recipient_email || '缺少邮箱' }}</span>
                  </template>
                </el-table-column>
                <el-table-column v-if="canWrite" label="操作" width="150" fixed="right">
                  <template #default="{ row: item }">
                    <el-button
                      v-if="['ready', 'failed'].includes(item.status)"
                      type="primary"
                      link
                      size="small"
                      :disabled="!mailStatus.configured"
                      :loading="sendingId === item.id"
                      @click="sendAssignment(row, item)"
                    >
                      {{ item.status === 'failed' ? '重试' : '发送' }}
                    </el-button>
                    <el-button
                      v-if="item.status !== 'cancelled'"
                      type="primary"
                      link
                      size="small"
                      @click="openSettlementDialog(row, item)"
                    >
                      结算
                    </el-button>
                    <el-button
                      v-if="row.status === 'cancelled' && item.status === 'cancelled'"
                      type="primary"
                      link
                      size="small"
                      @click="reEditCancelled(row, item.translator_id)"
                    >
                      重新编辑
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="批次状态" width="105">
          <template #default="{ row }">
            <el-tag :type="dispatchStatusMeta(row.status).type" size="small">
              {{ dispatchStatusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="order_no_snapshot" label="订单号" width="180" show-overflow-tooltip />
        <el-table-column prop="project_name_snapshot" label="项目" min-width="180" show-overflow-tooltip />
        <el-table-column label="译员" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ translatorSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="人数" width="70" align="center">
          <template #default="{ row }">{{ activeAssignments(row).length }}</template>
        </el-table-column>
        <el-table-column label="译员结算字数" width="200">
          <template #default="{ row }">
            {{ formatInteger(sumField(row, 'planned_word_count')) }} /
            {{ formatInteger(sumField(row, 'actual_word_count', true)) }}
          </template>
        </el-table-column>
        <el-table-column label="译员总价" width="110" align="right">
          <template #default="{ row }">{{ formatMoney(sumField(row, 'translator_total_price', true)) }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="安排人" width="110" show-overflow-tooltip />
        <el-table-column label="创建时间" width="165">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" type="primary" link size="small" @click="editDraft(row)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" type="success" link size="small" @click="confirmExisting(row)">确认</el-button>
            <el-button
              v-if="row.status === 'cancelled'"
              type="primary"
              link
              size="small"
              @click="reEditCancelled(row)"
            >
              重新编辑
            </el-button>
            <el-button
              v-if="['ready', 'partially_sent'].includes(row.status)"
              type="primary"
              link
              size="small"
              :disabled="!mailStatus.configured"
              :loading="sendingBatchId === row.id"
              @click="sendBatch(row)"
            >
              批量发送
            </el-button>
            <el-button
              v-if="['draft', 'ready'].includes(row.status)"
              type="danger"
              link
              size="small"
              @click="cancelBatch(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dispatchDialogVisible"
      :title="dispatchForm.id ? '编辑稿件安排草稿' : '新建稿件安排'"
      width="1120px"
      top="3vh"
      destroy-on-close
    >
      <el-descriptions v-if="selectedProject" :column="4" border class="dialog-summary">
        <el-descriptions-item label="订单号">{{ selectedProject.order_no }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ selectedProject.sub_project_name || selectedProject.project_name }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ selectedProject.client_short_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="语种">{{ selectedProject.language_pair || '-' }}</el-descriptions-item>
        <el-descriptions-item label="文本类型">{{ selectedProject.file_type_secondary || '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ selectedProject.priority || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目字数">{{ projectWordSummary(selectedProject) }}</el-descriptions-item>
        <el-descriptions-item label="客户交稿">{{ formatDateTime(selectedProject.customer_deadline_time) }}</el-descriptions-item>
        <el-descriptions-item label="预计统计方式">{{ selectedProject.expected_translator_stats_method || '-' }}</el-descriptions-item>
        <el-descriptions-item label="网络文件路径" :span="3">{{ selectedProject.network_file_path || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-form label-width="155px" class="dispatch-form">
        <el-form-item label="选择译员" required>
          <el-select
            v-model="selectedTranslatorIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="可同时选择多位译员"
            style="width: 100%"
            @change="syncSelectedTranslators"
          >
            <el-option
              v-for="translator in translators"
              :key="translator.id"
              :label="`${translator.translator_name} · ${cooperationLabel(translator)} · ${translator.languages || '语种未填'}`"
              :value="translator.id"
            />
          </el-select>
        </el-form-item>

        <el-alert
          v-if="dispatchForm.arrangements.length"
          :title="wordDifferenceMessage"
          :type="wordDifferenceType"
          :closable="false"
          show-icon
          class="word-alert"
        />

        <div
          v-for="(assignment, assignmentIndex) in dispatchForm.arrangements"
          :key="assignment.translator_id"
          class="assignment-card"
        >
          <div class="assignment-card__header">
            <div>
              <strong>{{ translatorById(assignment.translator_id)?.translator_name }}</strong>
              <span class="muted-text">译员合作形式：</span>
              <el-tag size="small" effect="plain">{{ cooperationLabel(translatorById(assignment.translator_id) || {}) }}</el-tag>
              <span class="muted-text">{{ preferredEmail(translatorById(assignment.translator_id) || {}) || '缺少邮箱' }}</span>
            </div>
            <el-button type="danger" link @click="removeAssignment(assignment.translator_id)">移除</el-button>
          </div>

          <el-row :gutter="16">
            <el-col :span="16">
              <el-form-item label="字数与结算">
                <div class="dialog-word-count-summary">
                  <span>{{ assignmentWordSummary(assignment) }}</span>
                  <el-button type="primary" link @click="openWordCountDrawer(assignment, false)">展开字数详情</el-button>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="译员结账方式">
                <el-select v-model="assignment.settlement_method" clearable style="width: 100%">
                  <el-option label="单结" value="single" />
                  <el-option label="月结" value="monthly" />
                  <el-option label="预付" value="prepaid" />
                  <el-option label="其他" value="other" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="译员单价">
                <el-input-number v-model="assignment.translator_unit_price" :min="0" :precision="4" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="译员总价">
                <el-input-number v-model="assignment.translator_total_price" :min="0" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col v-if="assignment.settlement_method === 'other'" :span="8">
              <el-form-item label="其他结算方式" required>
                <el-input v-model="assignment.custom_settlement_method" maxlength="100" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="需翻译部分" :required="dispatchForm.arrangements.length > 1">
            <el-input
              v-model="assignment.translation_scope"
              type="textarea"
              :rows="2"
              maxlength="5000"
              placeholder="如：第1-20页、文档A，或具体章节范围"
            />
          </el-form-item>

          <div class="milestone-editor">
            <div class="subsection-header">
              <strong>译员交稿_预定时间</strong>
              <el-button type="primary" link @click="addMilestone(assignment)">增加阶段节点</el-button>
            </div>
            <el-row
              v-for="(milestone, milestoneIndex) in assignment.milestones"
              :key="`${assignment.translator_id}-${milestoneIndex}`"
              :gutter="12"
              class="milestone-row"
            >
              <el-col :span="5">
                <el-select v-model="milestone.milestone_type" :disabled="milestone.milestone_type === 'final'" style="width: 100%">
                  <el-option label="阶段" value="phase" />
                  <el-option label="全稿" value="final" />
                </el-select>
              </el-col>
              <el-col :span="6">
                <el-input v-model="milestone.name" maxlength="100" placeholder="节点名称" />
              </el-col>
              <el-col :span="11">
                <el-date-picker
                  v-model="milestone.planned_at"
                  type="datetime"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  placeholder="选择预定时间"
                  style="width: 100%"
                />
              </el-col>
              <el-col :span="2">
                <el-button
                  v-if="milestone.milestone_type !== 'final'"
                  type="danger"
                  link
                  @click="removeMilestone(assignment, milestoneIndex)"
                >
                  删除
                </el-button>
              </el-col>
            </el-row>
            <el-alert
              v-if="assignmentDeadlineWarning(assignment)"
              title="全稿预定时间晚于客户交稿时间，请确认排期是否合理。"
              type="warning"
              :closable="false"
              show-icon
            />
          </div>

          <el-collapse class="mail-editor">
            <el-collapse-item title="邮件与备注" :name="assignmentIndex">
              <el-form-item label="邮件标题">
                <el-input v-model="assignment.email_subject" maxlength="500" />
              </el-form-item>
              <el-form-item label="邮件正文">
                <el-input v-model="assignment.email_body" type="textarea" :rows="7" maxlength="20000" show-word-limit />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="assignment.remarks" type="textarea" :rows="2" maxlength="5000" />
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </div>

        <el-form-item label="批次备注">
          <el-input v-model="dispatchForm.remarks" type="textarea" :rows="2" maxlength="5000" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dispatchDialogVisible = false">取消</el-button>
        <el-button :loading="saving" @click="saveDraft(false)">保存草稿</el-button>
        <el-button type="primary" :loading="saving" @click="saveDraft(true)">确认安排</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="settlementDialogVisible" title="补录实际译员字数与结账信息" width="560px">
      <el-form :model="settlementForm" label-width="155px">
        <el-form-item label="译员">
          <el-input :model-value="settlementForm.translator_name" disabled />
        </el-form-item>
        <el-form-item label="实际译员结算字数">
          <el-input-number v-model="settlementForm.actual_word_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="字数计量口径">
          <el-select v-model="settlementForm.word_count_type" clearable placeholder="请选择计量口径" style="width: 100%">
            <el-option v-for="item in wordCountTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="译员结账方式">
          <el-select v-model="settlementForm.settlement_method" clearable style="width: 100%">
            <el-option label="单结" value="single" />
            <el-option label="月结" value="monthly" />
            <el-option label="预付" value="prepaid" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="settlementForm.settlement_method === 'other'" label="其他结算方式" required>
          <el-input v-model="settlementForm.custom_settlement_method" maxlength="100" />
        </el-form-item>
        <el-form-item label="译员单价">
          <el-input-number v-model="settlementForm.translator_unit_price" :min="0" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="译员总价">
          <el-input-number v-model="settlementForm.translator_total_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="settlementForm.remarks" type="textarea" :rows="3" maxlength="5000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="settlementDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="settlementSaving" @click="saveSettlement">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="wordCountDrawerVisible"
      title="字数与结算详情"
      size="780px"
      append-to-body
      @closed="wordCountDrawerAssignments = []"
    >
      <template v-if="wordCountDrawerAssignments.length">
        <el-alert
          title="项目统计用于对照；译员预定字数和实际字数用于派稿及结算，不会覆盖客户或公司内部统计。"
          type="info"
          :closable="false"
          show-icon
          class="word-count-drawer__alert"
        />

        <div class="word-count-sheet-section">
          <div class="word-count-sheet-section__header">
            <strong>项目字数参考</strong>
            <span>当前比较基准：{{ projectWordSummary(selectedProject) }}</span>
          </div>
          <div class="excel-word-grid excel-word-grid--readonly">
            <table>
              <colgroup>
                <col class="excel-word-grid__source" />
                <col class="excel-word-grid__count" />
                <col class="excel-word-grid__method" />
                <col class="excel-word-grid__usage" />
              </colgroup>
              <thead>
                <tr>
                  <th>统计来源 / 用途</th>
                  <th>字数</th>
                  <th>计量口径 / 统计方式</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>预计译员字数</th>
                  <td class="excel-word-grid__text">{{ formatInteger(selectedProject?.expected_translator_word_count) }}</td>
                  <td class="excel-word-grid__text">{{ selectedProject?.expected_translator_stats_method || '-' }}</td>
                  <td class="excel-word-grid__text">译员分配的优先比较基准</td>
                </tr>
                <tr>
                  <th>公司内部统计</th>
                  <td class="excel-word-grid__text">{{ formatInteger(selectedProject?.internal_word_count) }}</td>
                  <td class="excel-word-grid__text">{{ formatWordCountType(selectedProject?.internal_word_count_type) }}</td>
                  <td class="excel-word-grid__text">预计译员字数为空时回退</td>
                </tr>
                <tr>
                  <th>客户统计</th>
                  <td class="excel-word-grid__text">{{ formatInteger(selectedProject?.customer_word_count) }}</td>
                  <td class="excel-word-grid__text">{{ formatWordCountType(selectedProject?.customer_word_count_type) }}</td>
                  <td class="excel-word-grid__text">内部统计为空时回退</td>
                </tr>
                <tr class="excel-word-grid__compatibility">
                  <th>原项目字数（兼容）</th>
                  <td class="excel-word-grid__text">{{ formatInteger(selectedProject?.word_count) }}</td>
                  <td class="excel-word-grid__text">—</td>
                  <td class="excel-word-grid__text">以上字段均为空时使用</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="word-count-sheet-section">
          <div class="word-count-sheet-section__header">
            <strong>译员安排字数</strong>
            <span>直接在单元格内填写</span>
          </div>
          <div class="excel-word-grid">
            <table>
              <colgroup>
                <col class="excel-word-grid__translator" />
                <col class="excel-word-grid__settlement-count" />
                <col class="excel-word-grid__settlement-count" />
                <col class="excel-word-grid__settlement-method" />
              </colgroup>
              <thead>
                <tr>
                  <th>译员</th>
                  <th>预定译员字数_数量</th>
                  <th>实际译员字数_数量</th>
                  <th>字数计量口径</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="assignment in wordCountDrawerAssignments"
                  :key="assignment.id || assignment.translator_id"
                >
                  <th>{{ wordCountAssignmentTranslatorName(assignment) }}</th>
                  <td class="excel-word-grid__editor">
                    <el-input-number
                      v-model="assignment.planned_word_count"
                      :min="0"
                      :disabled="wordCountDrawerReadonly || wordCountDrawerSettlementOnly || assignment.status === 'cancelled'"
                      controls-position="right"
                    />
                  </td>
                  <td class="excel-word-grid__editor">
                    <el-input-number
                      v-model="assignment.actual_word_count"
                      :min="0"
                      :disabled="wordCountDrawerReadonly || assignment.status === 'cancelled'"
                      controls-position="right"
                    />
                  </td>
                  <td class="excel-word-grid__editor">
                    <el-select
                      v-model="assignment.word_count_type"
                      clearable
                      placeholder="选择计量口径"
                      :disabled="wordCountDrawerReadonly || assignment.status === 'cancelled'"
                    >
                      <el-option v-for="item in wordCountTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <el-alert
          v-if="wordCountDrawerReadonly"
          title="当前安排已确认。如需补录实际结算字数，请在安排概览或记录中的“结算”入口修改。"
          type="warning"
          :closable="false"
        />
        <el-alert
          v-else-if="wordCountDrawerSettlementOnly"
          title="当前批次已确认，预定字数保持只读；可批量补录实际字数和计量口径。"
          type="warning"
          :closable="false"
        />
      </template>
      <template #footer>
        <el-button type="primary" :loading="wordCountDrawerSaving" @click="completeWordCountDrawer">
          {{ wordCountDrawerSettlementOnly ? '保存并完成' : '完成' }}
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelManuscriptDispatch,
  confirmManuscriptDispatch,
  createManuscriptDispatch,
  getManuscriptContext,
  getManuscriptDispatches,
  getManuscriptMailStatus,
  sendManuscriptAssignment,
  sendManuscriptDispatch,
  updateManuscriptDispatch,
  updateManuscriptSettlement
} from '@/api/manuscriptArrangements'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const contextLoading = ref(false)
const recordsLoading = ref(false)
const saving = ref(false)
const settlementSaving = ref(false)
const sendingId = ref('')
const sendingBatchId = ref('')
const activeProjects = ref([])
const translators = ref([])
const dispatches = ref([])
const selectedProject = ref(null)
const projectKeyword = ref('')
const dispatchKeyword = ref('')
const dispatchDialogVisible = ref(false)
const settlementDialogVisible = ref(false)
const wordCountDrawerVisible = ref(false)
const wordCountDrawerAssignments = ref([])
const wordCountDrawerReadonly = ref(false)
const wordCountDrawerSettlementOnly = ref(false)
const wordCountDrawerSaving = ref(false)
const selectedTranslatorIds = ref([])
const activeArrangementTranslatorId = ref('')
const workspaceTranslatorTableRef = ref(null)
const workspaceSelectedTranslators = ref([])
const translatorKeyword = ref('')
const translatorTab = ref('all')
const showTranslatorCode = ref(false)
const canWrite = computed(() => hasPermission('projects:write'))
const wordCountTypeOptions = [
  { label: '字符数（不计空格）', value: 'characters_no_spaces' },
  { label: '字数', value: 'words' },
  { label: '中文字符和朝鲜语单词', value: 'cjk_chars_korean_words' },
  { label: '外文字数（除中日韩）', value: 'foreign_words' }
]

const inlineSettlement = ref([])
const inlineSavingId = ref('')

const selectedProjectDispatch = computed(() => {
  if (!selectedProject.value) return null
  const target = projectIdentity(selectedProject.value)
  return (
    dispatches.value.find(
      (item) => projectIdentity(item) === target && item.status !== 'cancelled'
    ) || null
  )
})

const selectedProjectCancelledDispatch = computed(() => {
  if (!selectedProject.value) return null
  const target = projectIdentity(selectedProject.value)
  return (
    dispatches.value.find(
      (item) => projectIdentity(item) === target && item.status === 'cancelled'
    ) || null
  )
})

const workbenchReadonly = computed(
  () => Boolean(selectedProjectDispatch.value && selectedProjectDispatch.value.status !== 'draft')
)

const activeWorkbenchAssignment = computed(() => {
  const activeId = activeArrangementTranslatorId.value
  return (
    dispatchForm.arrangements.find((item) => item.translator_id === activeId) ||
    dispatchForm.arrangements[0] ||
    null
  )
})

const activeWorkbenchTranslator = computed(() =>
  translatorById(activeWorkbenchAssignment.value?.translator_id)
)

const activeExistingArrangement = computed(() => {
  const translatorId = activeWorkbenchAssignment.value?.translator_id
  if (!translatorId || !selectedProjectDispatch.value) return null
  return (
    selectedProjectDispatch.value.arrangements?.find(
      (item) => item.translator_id === translatorId
    ) || null
  )
})

function buildInlineSettlement(dispatch) {
  if (!dispatch) return []
  return (dispatch.arrangements || []).map((item) => ({
    id: item.id,
    status: item.status,
    translator_name_snapshot: item.translator_name_snapshot,
    cooperation_type_snapshot: item.cooperation_type_snapshot,
    planned_word_count: item.planned_word_count,
    actual_word_count: item.actual_word_count,
    word_count_type: item.word_count_type || null,
    translation_scope: item.translation_scope,
    milestones: item.milestones || [],
    settlement_method: item.settlement_method || null,
    custom_settlement_method: item.custom_settlement_method || '',
    translator_unit_price:
      item.translator_unit_price === null ? null : Number(item.translator_unit_price),
    translator_total_price:
      item.translator_total_price === null ? null : Number(item.translator_total_price)
  }))
}

watch(
  selectedProjectDispatch,
  (dispatch) => {
    inlineSettlement.value = buildInlineSettlement(dispatch)
  },
  { immediate: true }
)

async function saveInlineSettlement(row) {
  if (row.settlement_method === 'other' && !row.custom_settlement_method.trim()) {
    ElMessage.warning('请填写其他结算方式')
    return
  }
  const dispatch = selectedProjectDispatch.value
  if (!dispatch) return
  inlineSavingId.value = row.id
  try {
    await updateManuscriptSettlement(dispatch.id, row.id, {
      actual_word_count: row.actual_word_count,
      word_count_type: row.word_count_type || null,
      settlement_method: row.settlement_method || null,
      custom_settlement_method:
        row.settlement_method === 'other' ? row.custom_settlement_method || null : null,
      translator_unit_price: row.translator_unit_price,
      translator_total_price: row.translator_total_price
    })
    ElMessage.success('结算信息已保存')
    await loadDispatches()
  } catch (error) {
    ElMessage.error(error.detail || '保存结算信息失败')
  } finally {
    inlineSavingId.value = ''
  }
}

const mailStatus = reactive({
  mode: 'disabled',
  configured: false,
  detail: '正在读取邮件配置',
  test_recipient_masked: null
})

const dispatchForm = reactive({
  id: '',
  remarks: '',
  arrangements: []
})

const settlementForm = reactive({
  dispatch_id: '',
  arrangement_id: '',
  translator_name: '',
  actual_word_count: null,
  word_count_type: null,
  settlement_method: null,
  custom_settlement_method: '',
  translator_unit_price: null,
  translator_total_price: null,
  remarks: ''
})

const PROJECT_STATUS_LABELS = {
  pending_confirmation: '待确认',
  confirmed: '已确认',
  organized: '已整理',
  translator_assigned: '已排译员',
  sent_to_translator: '已发译员',
  translator_returned: '译员发回',
  special_checked: '已专检',
  typeset: '已排版',
  special_checked_typeset: '已专检排版',
  reviewed: '已审核',
  sent_to_client: '已发客户',
  client_feedback: '客户反馈',
  feedback_sent_to_client: '反馈后发客户',
  cancelled: '已取消',
  partially_cancelled: '已部分取消',
  paused: '已暂停',
  pending: '待确认',
  in_progress: '已确认',
  completed: '已发客户',
  terminated: '已取消'
}

const mailStatusTagType = computed(() => {
  if (!mailStatus.configured) return 'danger'
  return mailStatus.mode === 'test' ? 'warning' : 'success'
})

const mailStatusLabel = computed(() => {
  if (!mailStatus.configured) return '邮件未配置'
  return mailStatus.mode === 'test' ? '邮件测试模式' : '邮件正式发送'
})

const translatorCounts = computed(() => {
  const counts = {
    total: translators.value.length,
    fullTime: 0,
    partTime: 0,
    other: 0
  }
  for (const row of translators.value) {
    const group = cooperationGroup(row)
    if (group === 'full_time') counts.fullTime += 1
    else if (group === 'part_time') counts.partTime += 1
    else counts.other += 1
  }
  return counts
})

const filteredTranslators = computed(() => {
  const keyword = translatorKeyword.value.trim().toLowerCase()
  return translators.value.filter((row) => {
    if (translatorTab.value !== 'all' && cooperationGroup(row) !== translatorTab.value) {
      return false
    }
    if (!keyword) return true
    return [
      row.translator_name,
      row.translator_code,
      row.languages,
      row.direction,
      row.translation_type
    ].some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})

const workspaceSelectedTranslatorSummary = computed(() =>
  workspaceSelectedTranslators.value
    .map((item) => `${item.translator_name}（${cooperationLabel(item)}）`)
    .join('、')
)

const plannedWordTotal = computed(() =>
  dispatchForm.arrangements.reduce(
    (total, item) => total + Number(item.planned_word_count || 0),
    0
  )
)

const selectedProjectWordBasis = computed(() => projectWordBasis(selectedProject.value))

const wordDifference = computed(
  () => plannedWordTotal.value - Number(selectedProjectWordBasis.value || 0)
)

const wordDifferenceMessage = computed(() => {
  const basis = Number(selectedProjectWordBasis.value || 0)
  if (!basis) return `当前已分配 ${formatInteger(plannedWordTotal.value)} 字，项目未填写可比较字数。`
  if (wordDifference.value === 0) return `已分配 ${formatInteger(plannedWordTotal.value)} 字，与项目字数一致。`
  if (wordDifference.value < 0) {
    return `已分配 ${formatInteger(plannedWordTotal.value)} 字，尚有 ${formatInteger(Math.abs(wordDifference.value))} 字未分配。`
  }
  return `已分配 ${formatInteger(plannedWordTotal.value)} 字，超出项目字数 ${formatInteger(wordDifference.value)} 字；如包含重叠审校可继续保存。`
})

const wordDifferenceType = computed(() => {
  if (!selectedProjectWordBasis.value) return 'info'
  return wordDifference.value === 0 ? 'success' : 'warning'
})

function preferredEmail(row) {
  return String(row?.email1 || row?.email2 || row?.recipient_email || '').trim()
}

function cooperationValue(row) {
  return String(row?.cooperation_type ?? row?.cooperation_type_snapshot ?? '').trim()
}

function cooperationLabel(row) {
  const value = cooperationValue(row).toLowerCase()
  if (['全职', '全职译员', 'full_time', 'full-time', 'full time'].includes(value)) return '全职'
  if (['兼职', '兼职译员', 'part_time', 'part-time', 'part time'].includes(value)) return '兼职'
  return cooperationValue(row) || '未分类'
}

function cooperationGroup(row) {
  const value = cooperationValue(row).toLowerCase()
  if (['全职', '全职译员', 'full_time', 'full-time', 'full time'].includes(value)) {
    return 'full_time'
  }
  if (['兼职', '兼职译员', 'part_time', 'part-time', 'part time'].includes(value)) {
    return 'part_time'
  }
  return 'other'
}

function formatDomains(skills) {
  if (!Array.isArray(skills) || !skills.length) return '暂无领域标签'
  return skills
    .map((item) => (typeof item === 'string' ? item : item?.domain))
    .filter(Boolean)
    .slice(0, 3)
    .join('、') || '暂无领域标签'
}

function handleWorkspaceTranslatorSelection(selection) {
  workspaceSelectedTranslators.value = selection
  if (!selectedProject.value || workbenchReadonly.value) return
  selectedTranslatorIds.value = selection.map((item) => item.id)
  syncSelectedTranslators(selectedTranslatorIds.value)
  if (
    !dispatchForm.arrangements.some(
      (item) => item.translator_id === activeArrangementTranslatorId.value
    )
  ) {
    activeArrangementTranslatorId.value =
      dispatchForm.arrangements[0]?.translator_id || ''
  }
}

function activateTranslatorRow(row) {
  if (
    dispatchForm.arrangements.some((item) => item.translator_id === row?.id)
  ) {
    activeArrangementTranslatorId.value = row.id
  }
}

function settlementLabel(row) {
  const labels = {
    single: '单结',
    monthly: '月结',
    prepaid: '预付',
    other: row.custom_settlement_method || '其他'
  }
  return labels[row.settlement_method] || '未填写'
}

function dispatchStatusMeta(status) {
  const map = {
    draft: { label: '草稿', type: 'info' },
    ready: { label: '已确认', type: 'warning' },
    partially_sent: { label: '部分发送', type: 'primary' },
    sent: { label: '已发送', type: 'success' },
    cancelled: { label: '已取消', type: 'info' }
  }
  return map[status] || { label: status || '未知', type: 'info' }
}

function assignmentStatusMeta(status) {
  const map = {
    draft: { label: '草稿', type: 'info' },
    ready: { label: '待发送', type: 'warning' },
    sent: { label: '已发送', type: 'success' },
    failed: { label: '发送失败', type: 'danger' },
    cancelled: { label: '已取消', type: 'info' }
  }
  return map[status] || { label: status || '未知', type: 'info' }
}

function projectStatusLabel(status) {
  return PROJECT_STATUS_LABELS[status] || status || '-'
}

function projectStatusType(status) {
  if (['cancelled', 'partially_cancelled', 'terminated'].includes(status)) return 'danger'
  if (['translator_assigned', 'sent_to_translator', 'paused'].includes(status)) return 'warning'
  if (['reviewed', 'sent_to_client', 'client_feedback', 'feedback_sent_to_client', 'completed'].includes(status)) return 'success'
  if (['confirmed', 'organized', 'translator_returned', 'special_checked', 'typeset', 'special_checked_typeset', 'in_progress'].includes(status)) return 'primary'
  return 'info'
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

function formatInteger(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function hasWordCount(value) {
  return value !== null && value !== undefined && value !== ''
}

function normalizeWordCountType(value) {
  const normalized = String(value || '').trim()
  if (!normalized) return null
  return wordCountTypeOptions.find(
    (item) => item.value === normalized || item.label === normalized
  )?.value || null
}

function formatWordCountType(value) {
  return wordCountTypeOptions.find((item) => item.value === value)?.label || value || '未选口径'
}

function projectWordCountType(row) {
  if (!row) return null
  if (hasWordCount(row.expected_translator_word_count)) {
    const expectedType = normalizeWordCountType(row.expected_translator_stats_method)
    if (expectedType) return expectedType
  }
  if (hasWordCount(row.internal_word_count)) return row.internal_word_count_type || null
  if (hasWordCount(row.customer_word_count)) return row.customer_word_count_type || null
  return normalizeWordCountType(row.expected_translator_stats_method)
}

function formatProjectWordDimension(row, source) {
  if (!row) return '未填写'
  const value = row[`${source}_word_count`]
  const type = row[`${source}_word_count_type`]
  if (!hasWordCount(value)) return '未填写'
  return `${formatInteger(value)} · ${formatWordCountType(type)}`
}

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function isOverdue(value) {
  if (!value) return false
  const time = new Date(value).getTime()
  return Number.isFinite(time) && time < Date.now()
}

function projectWordBasis(row) {
  if (!row) return 0
  return row.expected_translator_word_count
    ?? row.internal_word_count
    ?? row.customer_word_count
    ?? row.word_count
    ?? 0
}

function projectWordSummary(row) {
  if (!row) return '未填写'
  if (hasWordCount(row.expected_translator_word_count)) {
    return `预计译员字数 ${formatInteger(row.expected_translator_word_count)} · ${formatWordCountType(normalizeWordCountType(row.expected_translator_stats_method) || row.expected_translator_stats_method)}`
  }
  if (hasWordCount(row.internal_word_count)) {
    return `内部 ${formatProjectWordDimension(row, 'internal')}`
  }
  if (hasWordCount(row.customer_word_count)) {
    return `客户 ${formatProjectWordDimension(row, 'customer')}`
  }
  if (hasWordCount(row.word_count)) return `历史 ${formatInteger(row.word_count)}`
  return '未填写'
}

function assignmentWordSummary(assignment) {
  if (!assignment) return '未填写'
  return `预定 ${formatInteger(assignment.planned_word_count)} / 实际 ${formatInteger(assignment.actual_word_count)} · ${formatWordCountType(assignment.word_count_type)}`
}

function wordCountAssignmentTranslatorName(assignment) {
  return assignment?.translator_name_snapshot
    || translatorById(assignment?.translator_id)?.translator_name
    || '当前译员'
}

function openWordCountDrawer(assignment, readonly = false) {
  if (!assignment) return
  wordCountDrawerSettlementOnly.value = false
  if (dispatchForm.arrangements.includes(assignment)) {
    wordCountDrawerAssignments.value = dispatchForm.arrangements
  } else if (inlineSettlement.value.includes(assignment)) {
    wordCountDrawerAssignments.value = inlineSettlement.value
    wordCountDrawerSettlementOnly.value = true
  } else {
    wordCountDrawerAssignments.value = [assignment]
  }
  wordCountDrawerReadonly.value = Boolean(readonly)
  wordCountDrawerVisible.value = true
}

async function completeWordCountDrawer() {
  if (!wordCountDrawerSettlementOnly.value) {
    wordCountDrawerVisible.value = false
    return
  }
  const dispatch = selectedProjectDispatch.value
  if (!dispatch) {
    ElMessage.warning('未找到当前稿件安排批次')
    return
  }
  wordCountDrawerSaving.value = true
  try {
    const editableRows = wordCountDrawerAssignments.value.filter(
      (item) => item.status !== 'cancelled'
    )
    await Promise.all(
      editableRows.map((item) =>
        updateManuscriptSettlement(dispatch.id, item.id, {
          actual_word_count: item.actual_word_count,
          word_count_type: item.word_count_type || null
        })
      )
    )
    wordCountDrawerVisible.value = false
    ElMessage.success('译员实际字数与计量口径已保存')
    await loadDispatches()
  } catch (error) {
    ElMessage.error(error.detail || '保存字数详情失败')
  } finally {
    wordCountDrawerSaving.value = false
  }
}

function projectIdentity(row) {
  return row?.entity_type === 'suborder'
    ? `suborder:${row.sub_order_id}`
    : `project:${row.translation_project_id}`
}

function projectRowClassName({ row }) {
  const classes = []
  if (row.entity_type === 'suborder') classes.push('child-order-row')
  if (selectedProject.value && projectIdentity(row) === projectIdentity(selectedProject.value)) {
    classes.push('selected-row')
  }
  return classes.join(' ')
}

function selectProject(row) {
  if (!row) return
  selectedProject.value = row
  prepareWorkbenchForProject()
}

function translatorById(id) {
  return translators.value.find((item) => item.id === id)
}

function legacyMilestoneName(milestone) {
  const name = milestone?.name?.trim()
  if (milestone?.milestone_type === 'final' && (!name || name === '全稿')) {
    return '译员交稿_全稿预定时间'
  }
  const legacyPhase = name?.match(/^阶段(\d+)$/)
  if (legacyPhase) return `译员交稿_预定时间${legacyPhase[1]}`
  if (!name) {
    return milestone?.milestone_type === 'final'
      ? '译员交稿_全稿预定时间'
      : `译员交稿_预定时间${milestone?.sequence_no || 1}`
  }
  return name
}

function defaultMilestones() {
  return [
    { milestone_type: 'phase', name: '译员交稿_预定时间1', sequence_no: 1, planned_at: null },
    { milestone_type: 'phase', name: '译员交稿_预定时间2', sequence_no: 2, planned_at: null },
    { milestone_type: 'phase', name: '译员交稿_预定时间3', sequence_no: 3, planned_at: null },
    { milestone_type: 'final', name: '译员交稿_全稿预定时间', sequence_no: 4, planned_at: null }
  ]
}

function defaultSubject() {
  if (!selectedProject.value) return ''
  const projectName = selectedProject.value.sub_project_name || selectedProject.value.project_name
  return `稿件安排｜${selectedProject.value.order_no}｜${projectName}`
}

function defaultBody(translator) {
  if (!selectedProject.value || !translator) return ''
  const projectName = selectedProject.value.sub_project_name || selectedProject.value.project_name
  return `${translator.translator_name}您好：

现安排您处理以下稿件：
订单号：${selectedProject.value.order_no}
项目名称：${projectName}
语种：${selectedProject.value.language_pair || '待确认'}
需翻译部分：待填写
预定译员结算字数：待确认
译员交稿_全稿预定时间：待确认
发稿文件路径：${selectedProject.value.network_file_path || '待填写'}
参考文件路径一：${selectedProject.value.reference_file_path_one || '无'}

请以项目经理提供的稿件文件和最终要求为准。`
}

function createAssignment(translator) {
  return {
    translator_id: translator.id,
    planned_word_count: null,
    actual_word_count: null,
    word_count_type: projectWordCountType(selectedProject.value),
    translation_scope: '',
    settlement_method: null,
    custom_settlement_method: '',
    translator_unit_price: null,
    translator_total_price: null,
    email_subject: defaultSubject(),
    email_body: defaultBody(translator),
    remarks: '',
    milestones: defaultMilestones()
  }
}

function syncSelectedTranslators(ids) {
  const existing = new Map(
    dispatchForm.arrangements.map((item) => [item.translator_id, item])
  )
  dispatchForm.arrangements = ids
    .map((id) => {
      if (existing.has(id)) return existing.get(id)
      const translator = translatorById(id)
      return translator ? createAssignment(translator) : null
    })
    .filter(Boolean)
}

function removeAssignment(translatorId) {
  selectedTranslatorIds.value = selectedTranslatorIds.value.filter((id) => id !== translatorId)
  syncSelectedTranslators(selectedTranslatorIds.value)
}

function addMilestone(assignment) {
  const finalIndex = assignment.milestones.findIndex((item) => item.milestone_type === 'final')
  const insertAt = finalIndex >= 0 ? finalIndex : assignment.milestones.length
  assignment.milestones.splice(insertAt, 0, {
    milestone_type: 'phase',
    name: `译员交稿_预定时间${insertAt + 1}`,
    sequence_no: insertAt + 1,
    planned_at: null
  })
  resequenceMilestones(assignment)
}

function removeMilestone(assignment, index) {
  assignment.milestones.splice(index, 1)
  resequenceMilestones(assignment)
}

function resequenceMilestones(assignment) {
  assignment.milestones.forEach((item, index) => {
    item.sequence_no = index + 1
  })
}

function assignmentDeadlineWarning(assignment) {
  if (!selectedProject.value?.customer_deadline_time) return false
  const final = assignment.milestones.find((item) => item.milestone_type === 'final')
  if (!final?.planned_at) return false
  return new Date(final.planned_at).getTime() > new Date(selectedProject.value.customer_deadline_time).getTime()
}

function activeAssignments(dispatch) {
  return (dispatch.arrangements || []).filter((item) => item.status !== 'cancelled')
}

function translatorSummary(dispatch) {
  const names = activeAssignments(dispatch).map((item) => item.translator_name_snapshot)
  return names.length ? names.join('、') : '-'
}

function sumField(dispatch, field, nullWhenEmpty = false) {
  const values = activeAssignments(dispatch)
    .map((item) => item[field])
    .filter((value) => value !== null && value !== undefined && value !== '')
  if (!values.length && nullWhenEmpty) return null
  return values.reduce((total, value) => total + Number(value || 0), 0)
}

function resetDispatchForm() {
  Object.assign(dispatchForm, { id: '', remarks: '', arrangements: [] })
  selectedTranslatorIds.value = []
  activeArrangementTranslatorId.value = ''
}

function hydrateDispatchForm(row, { asNew = false } = {}) {
  dispatchForm.id = asNew ? '' : row.id
  dispatchForm.remarks = row.remarks || ''
  dispatchForm.arrangements = (row.arrangements || []).map((item) => ({
    translator_id: item.translator_id,
    planned_word_count: item.planned_word_count,
    actual_word_count: item.actual_word_count,
    word_count_type: item.word_count_type || projectWordCountType(selectedProject.value),
    translation_scope: item.translation_scope || '',
    settlement_method: item.settlement_method || null,
    custom_settlement_method: item.custom_settlement_method || '',
    translator_unit_price:
      item.translator_unit_price === null ? null : Number(item.translator_unit_price),
    translator_total_price:
      item.translator_total_price === null ? null : Number(item.translator_total_price),
    email_subject: item.email_subject || '',
    email_body: item.email_body || '',
    remarks: item.remarks || '',
    milestones: item.milestones?.length
      ? item.milestones.map((milestone) => ({
          milestone_type: milestone.milestone_type,
          name: legacyMilestoneName(milestone),
          sequence_no: milestone.sequence_no,
          planned_at: milestone.planned_at
        }))
      : defaultMilestones()
  }))
  selectedTranslatorIds.value = dispatchForm.arrangements.map(
    (item) => item.translator_id
  )
  activeArrangementTranslatorId.value =
    dispatchForm.arrangements[0]?.translator_id || ''
}

function prepareWorkbenchForProject() {
  const existing = selectedProjectDispatch.value
  if (existing) {
    hydrateDispatchForm(existing)
    return
  }
  const cancelled = selectedProjectCancelledDispatch.value
  if (cancelled) {
    hydrateDispatchForm(cancelled, { asNew: true })
    return
  }
  resetDispatchForm()
  selectedTranslatorIds.value = workspaceSelectedTranslators.value.map(
    (item) => item.id
  )
  syncSelectedTranslators(selectedTranslatorIds.value)
  activeArrangementTranslatorId.value =
    dispatchForm.arrangements[0]?.translator_id || ''
}

function openCreateDialog() {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择订单')
    return
  }
  resetDispatchForm()
  selectedTranslatorIds.value = workspaceSelectedTranslators.value.map((item) => item.id)
  syncSelectedTranslators(selectedTranslatorIds.value)
  activeArrangementTranslatorId.value =
    dispatchForm.arrangements[0]?.translator_id || ''
  dispatchDialogVisible.value = true
}

function editDraft(row) {
  const matchedProject = activeProjects.value.find(
    (item) => projectIdentity(item) === projectIdentity(row)
  )
  selectedProject.value = matchedProject || {
    entity_type: row.entity_type,
    translation_project_id: row.translation_project_id,
    sub_order_id: row.sub_order_id,
    order_no: row.order_no_snapshot,
    project_name: row.project_name_snapshot
  }
  hydrateDispatchForm(row)
  dispatchDialogVisible.value = true
}

function reEditCancelled(row, translatorId = '') {
  const matchedProject = activeProjects.value.find(
    (item) => projectIdentity(item) === projectIdentity(row)
  )
  selectedProject.value = matchedProject || {
    entity_type: row.entity_type,
    translation_project_id: row.translation_project_id,
    sub_order_id: row.sub_order_id,
    order_no: row.order_no_snapshot,
    project_name: row.project_name_snapshot
  }
  // 取消记录保留用于审计；这里只复制参数，新保存时会创建独立草稿。
  hydrateDispatchForm(row, { asNew: true })
  if (
    translatorId &&
    dispatchForm.arrangements.some((item) => item.translator_id === translatorId)
  ) {
    activeArrangementTranslatorId.value = translatorId
  }
  dispatchDialogVisible.value = true
}

function validateDispatchForm() {
  if (!selectedProject.value) return '请选择订单'
  if (!dispatchForm.arrangements.length) return '请至少选择一位译员'
  if (
    dispatchForm.arrangements.length > 1 &&
    dispatchForm.arrangements.some((item) => !item.translation_scope.trim())
  ) {
    return '多人派稿时，每位译员都必须填写需翻译部分'
  }
  for (const assignment of dispatchForm.arrangements) {
    if (assignment.settlement_method === 'other' && !assignment.custom_settlement_method.trim()) {
      return `${translatorById(assignment.translator_id)?.translator_name || '译员'}：请填写其他结算方式`
    }
    const dated = assignment.milestones
      .filter((item) => item.planned_at)
      .sort((a, b) => a.sequence_no - b.sequence_no)
    for (let index = 1; index < dated.length; index += 1) {
      if (new Date(dated[index - 1].planned_at) > new Date(dated[index].planned_at)) {
        return `${translatorById(assignment.translator_id)?.translator_name || '译员'}：交稿节点时间必须按顺序递增`
      }
    }
  }
  return ''
}

function buildDispatchPayload() {
  return {
    entity_type: selectedProject.value.entity_type,
    translation_project_id: selectedProject.value.translation_project_id,
    sub_order_id:
      selectedProject.value.entity_type === 'suborder'
        ? selectedProject.value.sub_order_id
        : null,
    remarks: dispatchForm.remarks || null,
    arrangements: dispatchForm.arrangements.map((item) => ({
      translator_id: item.translator_id,
      planned_word_count: item.planned_word_count,
      actual_word_count: item.actual_word_count,
      word_count_type: item.word_count_type || null,
      translation_scope: item.translation_scope || null,
      settlement_method: item.settlement_method || null,
      custom_settlement_method:
        item.settlement_method === 'other'
          ? item.custom_settlement_method || null
          : null,
      translator_unit_price: item.translator_unit_price,
      translator_total_price: item.translator_total_price,
      email_subject: item.email_subject || null,
      email_body: item.email_body || null,
      remarks: item.remarks || null,
      milestones: item.milestones.map((milestone, index) => ({
        milestone_type: milestone.milestone_type,
        name:
          milestone.name ||
          (milestone.milestone_type === 'final'
            ? '译员交稿_全稿预定时间'
            : `译员交稿_预定时间${index + 1}`),
        sequence_no: index + 1,
        planned_at: milestone.planned_at || null
      }))
    }))
  }
}

async function saveDraft(shouldConfirm) {
  const errorMessage = validateDispatchForm()
  if (errorMessage) {
    ElMessage.warning(errorMessage)
    return
  }
  saving.value = true
  try {
    const payload = buildDispatchPayload()
    const saved = dispatchForm.id
      ? await updateManuscriptDispatch(dispatchForm.id, payload)
      : await createManuscriptDispatch(payload)
    dispatchForm.id = saved.id
    if (shouldConfirm) {
      await confirmManuscriptDispatch(saved.id)
      ElMessage.success('派稿批次已确认，订单状态已更新为“已排译员”')
    } else {
      ElMessage.success('派稿草稿已保存')
    }
    dispatchDialogVisible.value = false
    await Promise.all([loadContext(), loadDispatches()])
  } catch (error) {
    ElMessage.error(error.detail || '保存稿件安排失败')
  } finally {
    saving.value = false
  }
}

async function sendActiveWorkbenchAssignment() {
  if (!selectedProjectDispatch.value || !activeExistingArrangement.value) return
  await sendAssignment(
    selectedProjectDispatch.value,
    activeExistingArrangement.value
  )
}

async function confirmExisting(row) {
  try {
    await ElMessageBox.confirm(
      `确认 ${row.order_no_snapshot} 的派稿批次吗？确认后订单状态将更新为“已排译员”。`,
      '确认派稿',
      { type: 'warning' }
    )
    await confirmManuscriptDispatch(row.id)
    ElMessage.success('派稿批次已确认，订单状态已更新为“已排译员”')
    await Promise.all([loadContext(), loadDispatches()])
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.detail || '确认派稿失败')
  }
}

async function sendBatch(row) {
  if (!mailStatus.configured) {
    ElMessage.error(mailStatus.detail || '邮件服务尚未配置')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认向 ${activeAssignments(row).filter((item) => item.status !== 'sent').length} 位待发送译员批量发送邮件吗？各译员将独立记录发送结果。`,
      '批量发送稿件',
      { type: 'warning', confirmButtonText: '确认发送' }
    )
    sendingBatchId.value = row.id
    const result = await sendManuscriptDispatch(row.id)
    if (result.failed_count) {
      ElMessage.warning(`发送完成：成功 ${result.sent_count}，失败 ${result.failed_count}，跳过 ${result.skipped_count}`)
    } else {
      ElMessage.success(`发送完成：成功 ${result.sent_count}，跳过 ${result.skipped_count}`)
    }
    await Promise.all([loadContext(), loadDispatches()])
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.detail || '批量发送失败')
  } finally {
    sendingBatchId.value = ''
  }
}

async function sendAssignment(dispatch, assignment) {
  if (!mailStatus.configured) {
    ElMessage.error(mailStatus.detail || '邮件服务尚未配置')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认向 ${assignment.translator_name_snapshot} 发送 ${dispatch.order_no_snapshot} 的稿件邮件吗？`,
      '发送稿件',
      { type: 'warning', confirmButtonText: '确认发送' }
    )
    sendingId.value = assignment.id
    await sendManuscriptAssignment(dispatch.id, assignment.id)
    ElMessage.success('邮件发送成功')
    await Promise.all([loadContext(), loadDispatches()])
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.detail || '邮件发送失败')
    await loadDispatches()
  } finally {
    sendingId.value = ''
  }
}

async function cancelBatch(row) {
  const isConfirmedBatch = row.status === 'ready'
  try {
    await ElMessageBox.confirm(
      isConfirmedBatch
        ? `确定取消 ${row.order_no_snapshot} 的本次派稿批次吗？取消后订单状态将根据剩余有效安排自动回退。`
        : `确定取消 ${row.order_no_snapshot} 的派稿草稿吗？`,
      '取消派稿',
      { type: 'warning' }
    )
    await cancelManuscriptDispatch(row.id)
    ElMessage.success(
      isConfirmedBatch
        ? '派稿批次已取消，订单状态已回退；可点击“重新编辑”修改参数'
        : '派稿草稿已取消'
    )
    await Promise.all([loadContext(), loadDispatches()])
    if (
      selectedProject.value &&
      projectIdentity(selectedProject.value) === projectIdentity(row)
    ) {
      prepareWorkbenchForProject()
    }
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.detail || '取消派稿失败')
  }
}

function openSettlementDialog(dispatch, assignment) {
  Object.assign(settlementForm, {
    dispatch_id: dispatch.id,
    arrangement_id: assignment.id,
    translator_name: assignment.translator_name_snapshot,
    actual_word_count: assignment.actual_word_count,
    word_count_type: assignment.word_count_type || null,
    settlement_method: assignment.settlement_method || null,
    custom_settlement_method: assignment.custom_settlement_method || '',
    translator_unit_price:
      assignment.translator_unit_price === null ? null : Number(assignment.translator_unit_price),
    translator_total_price:
      assignment.translator_total_price === null ? null : Number(assignment.translator_total_price),
    remarks: assignment.remarks || ''
  })
  settlementDialogVisible.value = true
}

async function saveSettlement() {
  if (
    settlementForm.settlement_method === 'other' &&
    !settlementForm.custom_settlement_method.trim()
  ) {
    ElMessage.warning('请填写其他结算方式')
    return
  }
  settlementSaving.value = true
  try {
    await updateManuscriptSettlement(
      settlementForm.dispatch_id,
      settlementForm.arrangement_id,
      {
        actual_word_count: settlementForm.actual_word_count,
        word_count_type: settlementForm.word_count_type || null,
        settlement_method: settlementForm.settlement_method,
        custom_settlement_method:
          settlementForm.settlement_method === 'other'
            ? settlementForm.custom_settlement_method
            : null,
        translator_unit_price: settlementForm.translator_unit_price,
        translator_total_price: settlementForm.translator_total_price,
        remarks: settlementForm.remarks || null
      }
    )
    settlementDialogVisible.value = false
    ElMessage.success('实际字数与结算信息已保存')
    await loadDispatches()
  } catch (error) {
    ElMessage.error(error.detail || '保存结算信息失败')
  } finally {
    settlementSaving.value = false
  }
}

async function loadContext() {
  contextLoading.value = true
  try {
    const response = await getManuscriptContext({
      keyword: projectKeyword.value.trim() || undefined,
      project_limit: 100
    })
    activeProjects.value = Array.isArray(response?.active_projects?.items)
      ? response.active_projects.items
      : []
    translators.value = Array.isArray(response?.translators) ? response.translators : []
    if (
      selectedProject.value &&
      !activeProjects.value.some(
        (item) => projectIdentity(item) === projectIdentity(selectedProject.value)
      )
    ) {
      selectedProject.value = null
    }
  } catch (error) {
    ElMessage.error(error.detail || '加载项目和译员信息失败')
  } finally {
    contextLoading.value = false
  }
}

async function loadDispatches() {
  recordsLoading.value = true
  try {
    const response = await getManuscriptDispatches({
      limit: 500,
      keyword: dispatchKeyword.value.trim() || undefined
    })
    dispatches.value = Array.isArray(response) ? response : []
  } catch (error) {
    ElMessage.error(error.detail || '加载稿件安排记录失败')
  } finally {
    recordsLoading.value = false
  }
}

async function loadMailStatus() {
  try {
    const response = await getManuscriptMailStatus()
    Object.assign(mailStatus, response || {})
  } catch (error) {
    Object.assign(mailStatus, {
      mode: 'disabled',
      configured: false,
      detail: error.detail || '读取邮件配置失败'
    })
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadContext(), loadDispatches(), loadMailStatus()])
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.manuscript-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 1120px;
}

.page-header,
.panel-header,
.header-actions,
.panel-tools,
.selection-bar,
.assignment-card__header,
.subsection-header {
  display: flex;
  align-items: center;
}

.page-header,
.panel-header,
.selection-bar,
.assignment-card__header,
.subsection-header {
  justify-content: space-between;
}

.page-header h1,
.panel-header h2 {
  margin: 0;
}

.page-header p,
.panel-header span {
  margin: 5px 0 0;
  color: var(--el-text-color-secondary);
}

.header-actions,
.panel-tools {
  gap: 10px;
}

.legacy-workbench {
  display: grid;
  grid-template-columns: minmax(680px, 2.15fr) minmax(390px, 1fr);
  height: calc(100vh - 200px);
  min-height: 480px;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
}

.legacy-workbench__left {
  display: grid;
  grid-template-rows: 1fr 1fr;
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--el-border-color);
}

.legacy-project-panel,
.legacy-translator-panel,
.legacy-assignment-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 0;
  border-radius: 0;
}

.legacy-project-panel {
  border-bottom: 1px solid var(--el-border-color);
}

.legacy-project-panel :deep(.el-card__header),
.legacy-translator-panel :deep(.el-card__header),
.legacy-assignment-panel :deep(.el-card__header) {
  padding: 10px 12px;
  background: var(--el-fill-color-light);
}

.legacy-project-panel :deep(.el-card__body),
.legacy-translator-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px 10px;
}

.legacy-project-panel :deep(.el-table),
.legacy-translator-panel :deep(.el-table) {
  flex: 1;
  min-height: 0;
}

.translator-table-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.legacy-assignment-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
  overflow-y: auto;
}

.legacy-assignment-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.legacy-assignment-panel__header h2 {
  margin: 0;
  color: var(--el-color-primary);
  font-size: 16px;
}

.legacy-assignment-panel__header span {
  display: block;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.legacy-assignment-body {
  padding: 12px;
}

.legacy-project-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.assignment-tabs {
  margin-bottom: 8px;
}

.legacy-field-grid,
.legacy-mail-fields {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  border-top: 1px solid var(--el-border-color);
  border-left: 1px solid var(--el-border-color);
}

.legacy-field-grid > label,
.legacy-mail-fields > label {
  display: flex;
  min-height: 39px;
  align-items: center;
  padding: 7px 8px;
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-color-primary-light-9);
  color: var(--el-text-color-regular);
  font-size: 13px;
  word-break: break-all;
}

.legacy-field-grid > :not(label),
.legacy-mail-fields > :not(label) {
  min-height: 39px;
  padding: 4px 6px;
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
}

.legacy-readonly-value {
  display: flex;
  align-items: center;
  color: var(--el-text-color-regular);
}

.legacy-word-count-summary,
.dialog-word-count-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  color: var(--el-text-color-regular);
}

.word-count-drawer__alert {
  margin-bottom: 16px;
}

.word-count-sheet-section {
  margin-bottom: 20px;
}

.word-count-sheet-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.word-count-sheet-section__header span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.excel-word-grid {
  overflow-x: auto;
  border-top: 1px solid var(--el-border-color);
  border-left: 1px solid var(--el-border-color);
}

.excel-word-grid table {
  width: 100%;
  min-width: 700px;
  table-layout: fixed;
  border-collapse: collapse;
}

.excel-word-grid__source {
  width: 155px;
}

.excel-word-grid__count {
  width: 135px;
}

.excel-word-grid__method {
  width: 220px;
}

.excel-word-grid__usage {
  width: auto;
}

.excel-word-grid__translator {
  width: 155px;
}

.excel-word-grid__settlement-count {
  width: 170px;
}

.excel-word-grid__settlement-method {
  width: auto;
}

.excel-word-grid th,
.excel-word-grid td {
  height: 46px;
  padding: 0;
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
  vertical-align: middle;
}

.excel-word-grid thead th {
  padding: 10px 12px;
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-primary);
  text-align: left;
  font-size: 13px;
  font-weight: 600;
}

.excel-word-grid tbody th {
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  text-align: left;
  font-weight: 500;
}

.excel-word-grid__text {
  padding: 8px 12px !important;
  color: var(--el-text-color-regular);
  font-size: 12px;
  line-height: 1.4;
}

.excel-word-grid--readonly tbody td {
  background: var(--el-fill-color-lighter);
}

.excel-word-grid__compatibility th,
.excel-word-grid__compatibility td {
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-secondary);
}

.excel-word-grid__editor :deep(.el-input-number),
.excel-word-grid__editor :deep(.el-select),
.excel-word-grid__editor :deep(.el-input) {
  width: 100%;
  height: 45px;
}

.excel-word-grid__editor :deep(.el-input__wrapper),
.excel-word-grid__editor :deep(.el-select__wrapper) {
  min-height: 45px;
  border-radius: 0;
  box-shadow: none;
}

.excel-word-grid__editor :deep(.el-input-number .el-input__wrapper) {
  padding-left: 12px;
}

.excel-word-grid__editor :deep(.el-input-number__increase),
.excel-word-grid__editor :deep(.el-input-number__decrease) {
  border-radius: 0;
}

.excel-word-grid__editor:focus-within {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.legacy-mail-editor {
  margin-top: 12px;
}

.mail-body-input {
  margin-top: 8px;
}

.legacy-actions {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
}

.panel-tools .el-input {
  width: 290px;
}

.dispatch-overview {
  border-top: 3px solid var(--el-color-primary);
}

.overview-empty {
  padding: 10px 2px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.overview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-bottom: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.overview-table .milestone-line {
  line-height: 1.6;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(440px, 2fr);
  gap: 16px;
}

.workspace-grid .panel-card {
  min-width: 0;
}

.translator-header__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.translator-header__tools .el-input {
  width: 190px;
}

.translator-tabs {
  margin-top: -8px;
}

.table-footer {
  padding-top: 9px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-align: right;
}

.selection-bar {
  min-height: 56px;
  gap: 18px;
}

.selection-item {
  min-width: 0;
}

.selection-item--translators {
  flex: 1;
}

.selection-item strong {
  display: inline-block;
  max-width: calc(100% - 92px);
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}

.selection-divider {
  width: 1px;
  height: 34px;
  background: var(--el-border-color);
}

.selection-label {
  margin-right: 12px;
  color: var(--el-text-color-secondary);
}

.selection-bar em {
  color: var(--el-text-color-placeholder);
  font-style: normal;
}

.strong-text {
  font-weight: 600;
}

.muted-text,
small {
  color: var(--el-text-color-secondary);
}

.deadline-overdue,
.delivery-error {
  color: var(--el-color-danger);
}

.assignment-detail-wrap {
  padding: 10px 18px;
  background: var(--el-fill-color-lighter);
}

.milestone-line {
  line-height: 1.6;
}

.dialog-summary {
  margin-bottom: 18px;
}

.dispatch-form {
  max-height: 62vh;
  padding-right: 8px;
  overflow-y: auto;
}

.word-alert {
  margin-bottom: 14px;
}

.assignment-card {
  margin-bottom: 16px;
  padding: 16px 16px 4px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.assignment-card__header {
  margin-bottom: 14px;
}

.assignment-card__header > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.milestone-editor {
  margin: 4px 0 14px 105px;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}

.subsection-header {
  margin-bottom: 10px;
}

.milestone-row {
  margin-bottom: 8px;
}

.mail-editor {
  margin: 0 0 14px 105px;
}

:deep(.selected-row > td.el-table__cell) {
  background: var(--el-color-primary-light-9) !important;
}

:deep(.child-order-row > td:first-child) {
  border-left: 3px solid var(--el-color-primary-light-5);
}

@media (max-width: 1200px) {
  .manuscript-page {
    min-width: 1020px;
  }

  .legacy-workbench {
    grid-template-columns: minmax(620px, 1.75fr) minmax(380px, 1fr);
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1fr) 420px;
  }
}
</style>
