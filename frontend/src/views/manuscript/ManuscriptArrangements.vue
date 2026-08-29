<template>
  <div class="manuscript-page">
    <div class="legacy-workbench">
      <div
        class="legacy-workbench__left"
        :class="{ 'is-project-collapsed': projectPanelCollapsed }"
      >
        <el-card
          class="legacy-project-panel"
          :class="{ 'is-collapsed': projectPanelCollapsed }"
          shadow="never"
        >
          <template #header>
            <div
              class="panel-header project-panel-header"
              @click="toggleProjectPanel"
            >
              <div
                role="button"
                tabindex="0"
                :aria-expanded="!projectPanelCollapsed"
                :aria-label="projectPanelCollapsed ? '展开稿件项目' : '收起稿件项目'"
                @keydown.enter.prevent="toggleProjectPanel"
                @keydown.space.prevent="toggleProjectPanel"
              >
                <h2>稿件项目</h2>
                <span>{{ projectPanelSubtitle }}</span>
              </div>
              <div class="project-panel-header__right">
                <div
                  class="panel-tools project-panel-tools"
                  @click.stop
                  @keydown.stop
                >
                  <template v-if="!projectPanelCollapsed">
                    <el-input
                      v-model="projectKeyword"
                      size="small"
                      clearable
                      placeholder="订单号、项目或客户"
                      @input="onProjectKeywordInput"
                      @keyup.enter="runProjectSearch"
                      @clear="runProjectSearch"
                    />
                    <el-button size="small" type="primary" :loading="contextLoading" @click="runProjectSearch">查询</el-button>
                    <span class="panel-tools__divider" />
                  </template>
                  <el-tooltip :content="mailStatus.detail || '正在读取邮件配置'" placement="bottom">
                    <el-tag :type="mailStatusTagType" effect="plain" size="small">{{ mailStatusLabel }}</el-tag>
                  </el-tooltip>
                  <el-button size="small" :loading="loading" @click="loadAll">刷新</el-button>
                </div>
                <span
                  class="project-panel-chevron"
                  :class="{ 'is-collapsed': projectPanelCollapsed }"
                  aria-hidden="true"
                />
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
            <el-table-column type="index" label="序号" width="52" align="center" />
            <el-table-column prop="order_no" label="订单号" min-width="130" show-overflow-tooltip />
            <el-table-column label="项目" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="strong-text">{{ row.sub_project_name || row.project_name }}</div>
                <small>{{ row.client_short_name || '未填写客户' }}</small>
              </template>
            </el-table-column>
            <el-table-column label="项目助理" width="116">
              <template #default="{ row }">
                <el-tooltip :content="row.manuscript_access_reason || '项目助理责任信息'" placement="top">
                  <div class="project-assistant-cell">
                    <el-tag
                      :type="row.project_assistant_id ? 'success' : 'info'"
                      size="small"
                      effect="plain"
                    >
                      {{ row.project_assistant_name || '角色池' }}
                    </el-tag>
                    <small
                      v-if="row.current_stage_role_code === 'project_assistant' && row.current_assignee_name && row.current_assignee_id !== row.project_assistant_id"
                    >当前：{{ row.current_assignee_name }}</small>
                  </div>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="language_pair" label="语种" min-width="80" show-overflow-tooltip />
            <el-table-column label="字数统计" width="126" min-width="116" header-align="left">
              <template #default="{ row }">
                <div class="legacy-word-count-summary legacy-word-count-summary--compact">
                  <WordCountMatrixPopover
                    :model-value="row.word_count_matrix"
                    :entity-type="matrixEntityType(row)"
                    :entity-id="matrixEntityId(row)"
                    :dispatch-id="activeDispatchFor(row)?.id"
                    title="项目与译员字数统计"
                    @saved="handleWordCountMatrixSaved"
                  >
                    <template #reference>
                      <el-button
                        type="primary"
                        link
                        class="compact-table-link"
                        :title="projectWordListSummary(row).title"
                      >
                        <span class="compact-table-value">
                          <span class="compact-table-value__primary">{{ projectWordListSummary(row).primary }}</span>
                          <span
                            v-if="projectWordListSummary(row).extraCount"
                            class="compact-table-value__count"
                          >+{{ projectWordListSummary(row).extraCount }}</span>
                        </span>
                      </el-button>
                    </template>
                  </WordCountMatrixPopover>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="客户交稿时间" width="138" min-width="128">
              <template #default="{ row }">
                <span
                  class="compact-deadline"
                  :class="{ 'deadline-overdue': isOverdue(row.customer_deadline_time) }"
                  :title="formatDateTime(row.customer_deadline_time)"
                >
                  {{ formatDateTime(row.customer_deadline_time) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="80">
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
                <span>点击译员所在行即可选择，支持多选</span>
              </div>
              <div class="translator-header__tools">
                <el-input v-model="translatorKeyword" size="small" clearable placeholder="姓名、编号或语种" />
                <el-button
                  size="small"
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
            <el-tab-pane :label="`全部 ${translatorCounts.total}`" name="all" />
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
              @row-click="handleTranslatorRowClick"
            >
              <el-table-column type="selection" width="44" :reserve-selection="true" />
              <el-table-column
                v-if="showTranslatorCode"
                prop="translator_code"
                label="编号"
                width="100"
                show-overflow-tooltip
              />
              <el-table-column prop="translator_name" label="译员" width="100" show-overflow-tooltip />
              <el-table-column label="合作形式" width="92">
                <template #default="{ row }">{{ cooperationLabel(row) }}</template>
              </el-table-column>
              <el-table-column label="可用时间" width="130" show-overflow-tooltip>
                <template #default="{ row }">{{ row.available_time_slot || '-' }}</template>
              </el-table-column>
              <el-table-column label="语种 / 能力" min-width="165" show-overflow-tooltip>
                <template #default="{ row }">
                  <div>{{ row.languages || row.direction || '-' }}</div>
                  <small>{{ formatDomains(row.domain_skills) }}</small>
                </template>
              </el-table-column>
              <el-table-column label="备注" min-width="140" show-overflow-tooltip>
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
            <div class="legacy-assignment-panel__actions">
              <el-tag
                v-if="selectedProjectDispatch"
                :type="dispatchStatusMeta(selectedProjectDispatch.status).type"
                size="small"
              >
                {{ dispatchStatusMeta(selectedProjectDispatch.status).label }}
              </el-tag>
              <el-button
                v-if="canWrite && canManageSelectedProject && selectedProjectDispatch && selectedProjectDispatch.status !== 'draft'"
                type="primary"
                link
                size="small"
                @click="startNewBatch"
              >
                新建下一批次
              </el-button>
            </div>
          </div>
        </template>

        <el-empty v-if="!selectedProject" description="选择稿件后在此填写译员合作信息" :image-size="72" />
        <div v-else class="legacy-assignment-body">
          <div class="legacy-project-meta">
            <span>项目字数：{{ projectWordSummary(selectedProject) }}</span>
            <span>客户交稿时间：{{ formatDateTime(selectedProject.customer_deadline_time) }}</span>
            <span>项目助理：{{ selectedProject.project_assistant_name || '角色池' }}</span>
          </div>

          <el-alert
            v-if="canWrite && !canManageSelectedProject"
            :title="selectedProject.manuscript_access_reason || '当前账号不能操作该项目的稿件安排'"
            type="warning"
            :closable="false"
            show-icon
          />

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
            <el-tabs v-model="workbenchStage" class="assignment-tabs">
              <el-tab-pane label="安排" name="arrange">
                <div class="assignment-stage-content">
                  <el-tabs v-model="activeArrangementTranslatorId" class="assignment-translator-tabs">
                    <el-tab-pane
                      v-for="assignment in dispatchForm.arrangements"
                      :key="`arrange-${assignment.translator_id}`"
                      :label="translatorById(assignment.translator_id)?.translator_name || '译员'"
                      :name="assignment.translator_id"
                    />
                  </el-tabs>

                  <div v-if="activeWorkbenchAssignment" class="legacy-field-grid">
                    <label>字数与结算</label>
                    <div class="legacy-word-count-summary">
                      <span>{{ assignmentWordSummary(activeWorkbenchAssignment) }}</span>
                      <WordCountMatrixPopover
                        :model-value="selectedProject.word_count_matrix"
                        :entity-type="matrixEntityType(selectedProject)"
                        :entity-id="matrixEntityId(selectedProject)"
                        :dispatch-id="selectedProjectDispatch?.id"
                        :local="!selectedProjectDispatch"
                        :translators="dispatchForm.arrangements"
                        title="项目与译员字数统计"
                        @update:translators="dispatchForm.arrangements = $event"
                        @saved="handleWordCountMatrixSaved"
                      >
                        <template #reference><el-button type="primary" link>展开字数统计</el-button></template>
                      </WordCountMatrixPopover>
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
                      <label>{{ workbenchMilestoneLabel(milestone) }}</label>
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
                    <el-input
                      v-model="activeWorkbenchAssignment.settlement_method"
                      clearable
                      :disabled="workbenchReadonly"
                      maxlength="100"
                      placeholder="请输入结账方式，如：单结、月结"
                    />

                    <label>单价</label>
                    <el-input-number
                      v-model="activeWorkbenchAssignment.translator_unit_price"
                      :min="0"
                      :precision="4"
                      :controls="false"
                      :disabled="workbenchReadonly"
                      style="width: 100%"
                    />

                    <label>总价</label>
                    <el-input-number
                      v-model="activeWorkbenchAssignment.translator_total_price"
                      :min="0"
                      :precision="2"
                      :controls="false"
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

                  <div v-if="canManageSelectedProject && !workbenchReadonly" class="legacy-actions">
                    <el-button :loading="saving" @click="saveDraft(false)">保存草稿</el-button>
                    <el-button type="primary" :loading="saving" @click="saveDraft(true)">确认安排</el-button>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="发送" name="send">
                <div class="assignment-stage-content">
                  <template v-if="mailStageVisible">
                    <el-tabs v-model="activeArrangementTranslatorId" class="assignment-translator-tabs">
                      <el-tab-pane
                        v-for="assignment in dispatchForm.arrangements"
                        :key="`send-${assignment.translator_id}`"
                        :label="translatorById(assignment.translator_id)?.translator_name || '译员'"
                        :name="assignment.translator_id"
                      />
                    </el-tabs>

                    <div v-loading="mailPreviewLoading" class="mail-stage">
                      <el-alert
                        title="派稿文路径直接关联项目详情中的项目文件记录；参考文件路径一关联母项目；译员邮箱关联译员资料。"
                        type="info"
                        :closable="false"
                        show-icon
                      />
                      <el-alert
                        v-if="mailPreviewError"
                        :title="mailPreviewError"
                        type="error"
                        :closable="false"
                        show-icon
                      />
                      <el-alert
                        v-else-if="mailPathsDirty || !mailPathForm.dispatch_path || !mailPreview.recipient_email"
                        :title="mailPathsDirty
                          ? '发送路径已修改，请先保存路径后再发送稿件'
                          : (!mailPathForm.dispatch_path
                            ? '请先填写派稿文路径，再发送稿件'
                            : '请先在译员资料中填写邮箱，再发送稿件')"
                        type="warning"
                        :closable="false"
                        show-icon
                      />

                      <div class="legacy-mail-fields">
                        <label>派稿文路径</label>
                        <el-input
                          v-model="mailPathForm.dispatch_path"
                          type="textarea"
                          :rows="2"
                          :disabled="!canManageSelectedProject || mailPathsSaving"
                          maxlength="5000"
                          placeholder="请输入项目文件的派稿文路径"
                          @input="mailPathsDirty = true"
                        />
                        <label>参考文件路径一</label>
                        <el-input
                          v-model="mailPathForm.reference_file_path_one"
                          type="textarea"
                          :rows="2"
                          :disabled="!canManageSelectedProject || mailPathsSaving"
                          maxlength="500"
                          placeholder="请输入参考文件路径一"
                          @input="mailPathsDirty = true"
                        />
                        <label>译员邮箱</label>
                        <el-input :model-value="mailPreview.recipient_email || ''" readonly />
                      </div>

                      <div v-if="canManageSelectedProject" class="mail-path-actions">
                        <el-button
                          type="primary"
                          :loading="mailPathsSaving"
                          :disabled="!mailPathsDirty"
                          @click="saveMailPaths"
                        >
                          保存发送路径
                        </el-button>
                      </div>

                      <el-collapse class="legacy-mail-editor">
                        <el-collapse-item title="邮件预览" name="mail">
                          <el-input :model-value="mailPreview.subject" readonly placeholder="邮件标题" />
                          <el-input
                            :model-value="mailPreview.body"
                            type="textarea"
                            :rows="10"
                            readonly
                            placeholder="邮件正文"
                            class="mail-body-input"
                          />
                        </el-collapse-item>
                      </el-collapse>
                    </div>

                    <div v-if="canManageSelectedProject && selectedProjectDispatch" class="legacy-actions">
                      <el-button
                        v-if="activeExistingArrangement && ['ready', 'failed'].includes(activeExistingArrangement.status)"
                        type="primary"
                        :loading="sendingId === activeExistingArrangement.id"
                        :disabled="!mailStatus.configured || mailPreviewLoading || mailPathsDirty || !mailPathForm.dispatch_path || !mailPreview.recipient_email"
                        @click="sendActiveWorkbenchAssignment"
                      >
                        发送稿件
                      </el-button>
                      <el-button
                        v-if="['ready', 'partially_sent'].includes(selectedProjectDispatch.status)"
                        :loading="sendingBatchId === selectedProjectDispatch.id"
                        :disabled="!mailStatus.configured || mailPreviewLoading || mailPathsDirty || !mailPathForm.dispatch_path"
                        @click="openBatchMailPreviewDialog(selectedProjectDispatch)"
                      >
                        批量发送
                      </el-button>
                      <el-tag v-if="activeExistingArrangement?.status === 'sent'" type="success">该译员已发送</el-tag>
                    </div>
                  </template>
                  <el-empty v-else description="请先在“安排”中确认本次稿件安排" :image-size="72">
                    <el-button type="primary" @click="workbenchStage = 'arrange'">返回安排</el-button>
                  </el-empty>
                </div>
              </el-tab-pane>
            </el-tabs>
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
          <span>预定结算字数：{{ assignmentTotalSummary(selectedProjectDispatch, 'planned') }}</span>
          <span>实际结算字数：{{ assignmentTotalSummary(selectedProjectDispatch, 'actual') }}</span>
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
              <WordCountMatrixPopover
                :model-value="selectedProject.word_count_matrix"
                :entity-type="matrixEntityType(selectedProject)"
                :entity-id="matrixEntityId(selectedProject)"
                :dispatch-id="selectedProjectDispatch.id"
                title="项目与译员字数统计"
                @saved="handleWordCountMatrixSaved"
              >
                <template #reference><el-button type="primary" link size="small">编辑字数统计</el-button></template>
              </WordCountMatrixPopover>
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
                <el-input
                  v-model="row.settlement_method"
                  size="small"
                  clearable
                  maxlength="100"
                  placeholder="请输入结账方式"
                  style="width: 100%"
                  :disabled="row.status === 'cancelled'"
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
                  :controls="false"
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
                  :controls="false"
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

    <el-card class="panel-card records-panel">
      <template #header>
        <div class="panel-header">
          <div>
            <h2>稿件安排记录</h2>
            <span>按派稿批次汇总，展开后查看每位译员的分工与发送结果</span>
          </div>
          <div class="panel-tools">
            <el-input
              v-model="dispatchKeyword"
              size="small"
              clearable
              placeholder="搜索订单、项目、译员或邮箱"
              @input="onDispatchKeywordInput"
              @keyup.enter="runDispatchSearch"
              @clear="runDispatchSearch"
            />
            <el-button size="small" :loading="recordsLoading" @click="runDispatchSearch">查询</el-button>
          </div>
        </div>
      </template>

      <el-table
        ref="dispatchTableRef"
        v-loading="recordsLoading"
        class="dispatch-records-table"
        :data="dispatches"
        row-key="id"
        border
        size="small"
        :expand-row-keys="expandedDispatchRowKeys"
        @expand-change="handleDispatchExpandChange"
      >
        <el-table-column
          type="expand"
          width="1"
          class-name="dispatch-expand-column"
          label-class-name="dispatch-expand-column"
        >
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
                    <template v-if="canManageDispatch(row)">
                      <el-button
                      v-if="['ready', 'failed'].includes(item.status)"
                      type="primary"
                      link
                      size="small"
                      :disabled="!mailStatus.configured"
                      :loading="sendingId === item.id"
                      @click="openMailPreviewDialog(row, item)"
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
                    <span v-else>-</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="订单号" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="dispatch-order-cell">
              <TableExpandButton
                v-if="row.arrangements?.length"
                :expanded="isDispatchExpanded(row)"
                expand-label="展开稿件安排详情"
                collapse-label="收起稿件安排详情"
                @click="toggleDispatchExpansion(row)"
              />
              <span>{{ row.order_no_snapshot || '-' }}</span>
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
        <el-table-column prop="project_name_snapshot" label="项目" min-width="180" show-overflow-tooltip />
        <el-table-column label="译员" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ translatorSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="人数" width="70" align="center">
          <template #default="{ row }">{{ activeAssignments(row).length }}</template>
        </el-table-column>
        <el-table-column label="译员结算字数" width="200">
          <template #default="{ row }">
            <div>{{ assignmentTotalSummary(row, 'planned') }} / {{ assignmentTotalSummary(row, 'actual') }}</div>
            <WordCountMatrixPopover
              :model-value="row.word_count_matrix"
              :entity-type="matrixEntityType(row)"
              :entity-id="matrixEntityId(row)"
              :dispatch-id="row.id"
              title="项目与译员字数统计"
              @saved="handleWordCountMatrixSaved"
            >
              <template #reference><el-button type="primary" link size="small">字数统计</el-button></template>
            </WordCountMatrixPopover>
          </template>
        </el-table-column>
        <el-table-column label="译员总价" width="110" align="right">
          <template #default="{ row }">{{ formatMoney(sumField(row, 'translator_total_price', true)) }}</template>
        </el-table-column>
        <el-table-column label="项目助理" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project_assistant_name || '角色池' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="实际安排人" width="120" show-overflow-tooltip />
        <el-table-column label="创建时间" width="165">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <template v-if="canManageDispatch(row)">
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
              @click="openBatchMailPreviewDialog(row)"
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
            <el-tooltip v-else :content="row.manuscript_access_reason || '当前账号不能操作该项目'" placement="left">
              <span>-</span>
            </el-tooltip>
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
        <el-descriptions-item label="客户交稿时间">{{ formatDateTime(selectedProject.customer_deadline_time) }}</el-descriptions-item>
        <el-descriptions-item label="派稿文路径" :span="3">{{ selectedProject.dispatch_path || '-' }}</el-descriptions-item>
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
                  <WordCountMatrixPopover
                    :model-value="selectedProject.word_count_matrix"
                    :entity-type="matrixEntityType(selectedProject)"
                    :entity-id="matrixEntityId(selectedProject)"
                    :dispatch-id="dispatchForm.id"
                    :local="!dispatchForm.id"
                    :translators="dispatchForm.arrangements"
                    title="项目与译员字数统计"
                    @update:translators="dispatchForm.arrangements = $event"
                    @saved="handleWordCountMatrixSaved"
                  >
                    <template #reference><el-button type="primary" link>展开字数统计</el-button></template>
                  </WordCountMatrixPopover>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="译员结账方式">
                <el-input
                  v-model="assignment.settlement_method"
                  clearable
                  maxlength="100"
                  placeholder="请输入结账方式，如：单结、月结"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="译员单价">
                <el-input-number v-model="assignment.translator_unit_price" :min="0" :precision="4" :controls="false" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="译员总价">
                <el-input-number v-model="assignment.translator_total_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
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

    <el-dialog
      v-model="mailSendPreviewDialogVisible"
      :title="mailSendPreviewMode === 'batch' ? '批量发送邮件预览' : '发送邮件预览'"
      width="min(820px, calc(100vw - 32px))"
      top="5vh"
      class="mail-send-preview-dialog"
      destroy-on-close
      :close-on-click-modal="!mailSendPreviewSending"
      :close-on-press-escape="!mailSendPreviewSending"
      :show-close="!mailSendPreviewSending"
      @closed="clearMailSendPreview"
    >
      <div v-loading="mailSendPreviewLoading" class="mail-send-preview-body">
        <el-alert
          v-if="mailSendPreviewMode === 'batch'"
          :title="`本次将向 ${mailSendPreviewBatchCount} 位待发送译员分别生成并发送邮件；下方展示当前抽样译员的实际邮件内容。`"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-alert
          v-if="mailSendPreviewError"
          :title="mailSendPreviewError"
          type="error"
          :closable="false"
          show-icon
        />

        <div v-if="mailSendPreview.preview.arrangement_id" class="mail-attachment-upload">
          <label>邮件附件（可选）</label>
          <el-upload
            v-model:file-list="mailAttachmentList"
            :auto-upload="false"
            :limit="1"
            :disabled="mailSendPreviewSending"
            :on-change="handleMailAttachmentChange"
            :on-remove="handleMailAttachmentRemove"
            :on-exceed="handleMailAttachmentExceed"
          >
            <el-button :disabled="mailSendPreviewSending">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                单个文件不超过 10MB；文件仅用于本次发送，不依赖局域网共享路径。批量发送时将附到每封邮件中。
              </div>
            </template>
          </el-upload>
        </div>

        <el-descriptions v-if="mailSendPreview.preview.arrangement_id" :column="1" border size="small">
          <el-descriptions-item label="译员">
            {{ mailSendPreview.assignment?.translator_name_snapshot || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="收件邮箱">
            {{ mailSendPreview.preview.recipient_email || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="派稿文路径">
            {{ mailSendPreview.preview.dispatch_path || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="参考文件路径一">
            {{ mailSendPreview.preview.reference_file_path_one || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="mailSendPreview.preview.arrangement_id" class="mail-send-preview-content">
          <label>邮件标题</label>
          <el-input :model-value="mailSendPreview.preview.subject" readonly />
          <label>邮件正文</label>
          <el-input
            :model-value="mailSendPreview.preview.body"
            type="textarea"
            :rows="14"
            readonly
            resize="none"
          />
        </div>
      </div>
      <template #footer>
        <el-button :disabled="mailSendPreviewSending" @click="mailSendPreviewDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="mailSendPreviewSending"
          :disabled="mailSendPreviewConfirmDisabled"
          @click="confirmMailPreviewSend"
        >
          {{ mailSendPreviewMode === 'batch' ? '确认批量发送' : '确认发送' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="settlementDialogVisible" title="补录实际译员字数与结账信息" width="560px">
      <el-form :model="settlementForm" label-width="155px">
        <el-form-item label="译员">
          <el-input :model-value="settlementForm.translator_name" disabled />
        </el-form-item>
        <el-form-item label="实际译员字数">
          <div class="dialog-word-count-summary">
            <span>{{ formatWordCountValues(settlementForm.actual) }}</span>
            <WordCountMatrixPopover
              :model-value="settlementForm.word_count_matrix"
              :entity-type="settlementForm.entity_type"
              :entity-id="settlementForm.entity_id"
              :dispatch-id="settlementForm.dispatch_id"
              title="项目与译员字数统计"
              @saved="handleSettlementMatrixSaved"
            >
              <template #reference><el-button type="primary" link>编辑字数统计</el-button></template>
            </WordCountMatrixPopover>
          </div>
        </el-form-item>
        <el-form-item label="译员结账方式">
          <el-input
            v-model="settlementForm.settlement_method"
            clearable
            maxlength="100"
            placeholder="请输入结账方式，如：单结、月结"
          />
        </el-form-item>
        <el-form-item label="译员单价">
          <el-input-number v-model="settlementForm.translator_unit_price" :min="0" :precision="4" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="译员总价">
          <el-input-number v-model="settlementForm.translator_total_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
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

  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelManuscriptDispatch,
  confirmManuscriptDispatch,
  createManuscriptDispatch,
  getManuscriptContext,
  getManuscriptDispatches,
  getManuscriptMailPreview,
  getManuscriptMailStatus,
  sendManuscriptAssignment,
  sendManuscriptDispatch,
  updateManuscriptDispatch,
  updateManuscriptMailPaths,
  updateManuscriptSettlement
} from '@/api/manuscriptArrangements'
import { hasPermission } from '@/utils/permission'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import {
  createEmptyWordCountMatrix,
  createEmptyWordCountValues,
  formatWordCountMatrix,
  formatWordCountValues,
  getWordCountMatrixListSummary,
  normalizeWordCountValues,
  sumWordCountValues
} from '@/utils/wordCountMatrix'

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
const dispatchTableRef = ref(null)
const expandedDispatchIds = ref(new Set())
const expandedDispatchRowKeys = computed(() => [...expandedDispatchIds.value])
const selectedProject = ref(null)
const projectKeyword = ref('')
const dispatchKeyword = ref('')
const dispatchDialogVisible = ref(false)
const settlementDialogVisible = ref(false)
const selectedTranslatorIds = ref([])
const activeArrangementTranslatorId = ref('')
const workbenchStage = ref('arrange')
const workspaceTranslatorTableRef = ref(null)
const workspaceSelectedTranslators = ref([])
const translatorKeyword = ref('')
const translatorTab = ref('all')
const showTranslatorCode = ref(false)
const manuscriptLayoutUserKey = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
const projectPanelStorageKey = `manuscript_project_panel_collapsed:${manuscriptLayoutUserKey}`
const projectPanelCollapsed = ref(false)
try {
  projectPanelCollapsed.value = localStorage.getItem(projectPanelStorageKey) === '1'
} catch {}

const projectPanelSubtitle = computed(() => {
  if (!projectPanelCollapsed.value) return '选择需要安排译员的母订单或子订单'
  if (selectedProject.value) {
    const name = selectedProject.value.sub_project_name || selectedProject.value.project_name
    return `当前：${selectedProject.value.order_no} · ${name}`
  }
  return `${activeProjects.value.length} 个可安排项目，点击展开选择`
})

function toggleProjectPanel() {
  projectPanelCollapsed.value = !projectPanelCollapsed.value
  try {
    localStorage.setItem(projectPanelStorageKey, projectPanelCollapsed.value ? '1' : '0')
  } catch {}
}

const canWrite = computed(() => hasPermission('projects:write'))
const creatingNewBatch = ref(false)
const SEARCH_DEBOUNCE_MS = 400
let projectSearchTimer = null
let dispatchSearchTimer = null
let contextRequestId = 0
let dispatchRequestId = 0
let contextController = null
let dispatchController = null
const canManageSelectedProject = computed(() => (
  canWrite.value && Boolean(selectedProject.value?.can_manage_manuscript)
))
const inlineSettlement = ref([])
const inlineSavingId = ref('')

const canManageDispatch = (dispatch) => (
  canWrite.value && Boolean(dispatch?.can_manage_manuscript)
)

function ensureCanManage(target = selectedProject.value) {
  if (!canWrite.value) {
    ElMessage.warning('当前账号没有项目写入权限')
    return false
  }
  if (!target?.can_manage_manuscript) {
    ElMessage.warning(
      target?.manuscript_access_reason || '当前账号不能操作该项目的稿件安排'
    )
    return false
  }
  return true
}

function activeDispatchFor(project) {
  const target = projectIdentity(project)
  const items = dispatches.value.filter(
    (item) => projectIdentity(item) === target && item.status !== 'cancelled'
  )
  return items.find((item) => item.status === 'draft') || items[0] || null
}

const selectedProjectDispatch = computed(() => {
  if (creatingNewBatch.value) return null
  return selectedProject.value ? activeDispatchFor(selectedProject.value) : null
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

const mailStageVisible = computed(
  () => Boolean(
    selectedProjectDispatch.value
    && selectedProjectDispatch.value.status !== 'draft'
  )
)
const mailPreviewLoading = ref(false)
const mailPreviewError = ref('')
const mailPathsSaving = ref(false)
const mailPathsDirty = ref(false)
const mailPathsDispatchId = ref('')
const mailSendPreviewDialogVisible = ref(false)
const mailSendPreviewLoading = ref(false)
const mailSendPreviewSending = ref(false)
const mailSendPreviewError = ref('')
const mailSendPreviewMode = ref('single')
const MAX_MAIL_ATTACHMENT_BYTES = 10 * 1024 * 1024
const mailAttachmentFile = ref(null)
const mailAttachmentList = ref([])
const mailPreview = reactive({
  arrangement_id: '',
  recipient_email: '',
  subject: '',
  body: '',
  dispatch_path: '',
  reference_file_path_one: ''
})
const mailPathForm = reactive({
  dispatch_path: '',
  reference_file_path_one: ''
})
const mailSendPreview = reactive({
  dispatch: null,
  assignment: null,
  preview: {
    arrangement_id: '',
    recipient_email: '',
    subject: '',
    body: '',
    dispatch_path: '',
    reference_file_path_one: ''
  }
})
let mailPreviewRequestId = 0
let mailSendPreviewRequestId = 0

const mailSendPreviewBatchCount = computed(() => {
  const dispatch = mailSendPreview.dispatch
  if (!dispatch) return 0
  return activeAssignments(dispatch).filter((item) => item.status !== 'sent').length
})

const mailSendPreviewConfirmDisabled = computed(() => {
  const preview = mailSendPreview.preview
  return Boolean(
    mailSendPreviewLoading.value
    || mailSendPreviewSending.value
    || mailSendPreviewError.value
    || !preview.arrangement_id
    || !preview.recipient_email
    || !preview.dispatch_path
  )
})

function clearMailPreview() {
  Object.assign(mailPreview, {
    arrangement_id: '',
    recipient_email: '',
    subject: '',
    body: '',
    dispatch_path: '',
    reference_file_path_one: ''
  })
  mailPreviewError.value = ''
}

function resetMailPathForm() {
  Object.assign(mailPathForm, {
    dispatch_path: '',
    reference_file_path_one: ''
  })
  mailPathsDispatchId.value = ''
  mailPathsDirty.value = false
}

function clearMailSendPreview() {
  mailSendPreviewRequestId += 1
  mailSendPreviewLoading.value = false
  mailSendPreviewError.value = ''
  mailSendPreviewMode.value = 'single'
  mailSendPreview.dispatch = null
  mailSendPreview.assignment = null
  mailAttachmentFile.value = null
  mailAttachmentList.value = []
  Object.assign(mailSendPreview.preview, {
    arrangement_id: '',
    recipient_email: '',
    subject: '',
    body: '',
    dispatch_path: '',
    reference_file_path_one: ''
  })
}

function handleMailAttachmentChange(uploadFile) {
  const rawFile = uploadFile?.raw
  if (!rawFile) {
    mailAttachmentFile.value = null
    return
  }
  if (rawFile.size > MAX_MAIL_ATTACHMENT_BYTES) {
    mailAttachmentFile.value = null
    mailAttachmentList.value = []
    ElMessage.error('上传文件不能超过 10MB')
    return
  }
  if (rawFile.size === 0) {
    mailAttachmentFile.value = null
    mailAttachmentList.value = []
    ElMessage.error('不能上传空文件')
    return
  }
  mailAttachmentFile.value = rawFile
}

function handleMailAttachmentRemove() {
  mailAttachmentFile.value = null
}

function handleMailAttachmentExceed() {
  ElMessage.warning('每次发送只能上传一个附件，请先移除已选文件')
}

async function openMailPreviewDialog(dispatch, assignment, mode = 'single') {
  if (!ensureCanManage(dispatch)) return
  if (!mailStatus.configured) {
    ElMessage.error(mailStatus.detail || '邮件服务尚未配置')
    return
  }
  if (
    mailPathsDirty.value
    && selectedProjectDispatch.value?.id === dispatch?.id
  ) {
    ElMessage.warning('发送路径已修改，请先保存发送路径')
    return
  }
  if (!dispatch?.id || !assignment?.id) {
    ElMessage.warning('未找到可预览的待发送邮件')
    return
  }

  const requestId = ++mailSendPreviewRequestId
  mailSendPreviewMode.value = mode
  mailSendPreview.dispatch = dispatch
  mailSendPreview.assignment = assignment
  mailSendPreviewError.value = ''
  mailSendPreviewLoading.value = true
  mailSendPreviewDialogVisible.value = true
  try {
    const preview = await getManuscriptMailPreview(dispatch.id, assignment.id)
    if (requestId !== mailSendPreviewRequestId) return
    Object.assign(mailSendPreview.preview, preview || {})
  } catch (error) {
    if (requestId !== mailSendPreviewRequestId) return
    mailSendPreviewError.value = error.detail || '加载邮件预览失败'
  } finally {
    if (requestId === mailSendPreviewRequestId) {
      mailSendPreviewLoading.value = false
    }
  }
}

function openBatchMailPreviewDialog(dispatch) {
  const assignment = activeAssignments(dispatch).find(
    (item) => item.status !== 'sent'
  )
  if (!assignment) {
    ElMessage.info('该批次没有待发送邮件')
    return
  }
  openMailPreviewDialog(dispatch, assignment, 'batch')
}

async function confirmMailPreviewSend() {
  const dispatch = mailSendPreview.dispatch
  const assignment = mailSendPreview.assignment
  if (!dispatch || !assignment || mailSendPreviewConfirmDisabled.value) return

  mailSendPreviewSending.value = true
  try {
    const sent = mailSendPreviewMode.value === 'batch'
      ? await sendBatch(dispatch)
      : await sendAssignment(dispatch, assignment)
    if (sent) mailSendPreviewDialogVisible.value = false
  } finally {
    mailSendPreviewSending.value = false
  }
}

async function loadActiveMailPreview() {
  const requestId = ++mailPreviewRequestId
  const dispatchId = selectedProjectDispatch.value?.id
  const arrangementId = activeExistingArrangement.value?.id
  if (!mailStageVisible.value || !dispatchId || !arrangementId) {
    clearMailPreview()
    resetMailPathForm()
    mailPreviewLoading.value = false
    return
  }

  mailPreviewLoading.value = true
  mailPreviewError.value = ''
  try {
    const response = await getManuscriptMailPreview(dispatchId, arrangementId)
    if (requestId !== mailPreviewRequestId) return
    Object.assign(mailPreview, response || {})
    if (mailPathsDispatchId.value !== dispatchId || !mailPathsDirty.value) {
      Object.assign(mailPathForm, {
        dispatch_path: response?.dispatch_path || '',
        reference_file_path_one: response?.reference_file_path_one || ''
      })
      mailPathsDispatchId.value = dispatchId
      mailPathsDirty.value = false
    }
  } catch (error) {
    if (requestId !== mailPreviewRequestId) return
    clearMailPreview()
    mailPreviewError.value = error.detail || '加载邮件预览失败'
  } finally {
    if (requestId === mailPreviewRequestId) {
      mailPreviewLoading.value = false
    }
  }
}

async function saveMailPaths() {
  const dispatchId = selectedProjectDispatch.value?.id
  if (!dispatchId) return
  if (!ensureCanManage(selectedProjectDispatch.value)) return
  mailPathsSaving.value = true
  try {
    const saved = await updateManuscriptMailPaths(dispatchId, {
      dispatch_path: mailPathForm.dispatch_path.trim() || null,
      reference_file_path_one: mailPathForm.reference_file_path_one.trim() || null
    })
    const identity = projectIdentity(selectedProject.value)
    const freshValues = {
      dispatch_path: saved?.dispatch_path || '',
      reference_file_path_one: saved?.reference_file_path_one || ''
    }
    const contextProject = activeProjects.value.find(
      (item) => projectIdentity(item) === identity
    )
    if (contextProject) Object.assign(contextProject, freshValues)
    if (selectedProject.value) Object.assign(selectedProject.value, freshValues)
    mailPathsDirty.value = false
    await loadActiveMailPreview()
    ElMessage.success('发送路径已保存，并同步到项目详情')
  } catch (error) {
    ElMessage.error(error.detail || '保存发送路径失败')
  } finally {
    mailPathsSaving.value = false
  }
}

function buildInlineSettlement(dispatch) {
  if (!dispatch) return []
  return (dispatch.arrangements || []).map((item) => ({
    id: item.id,
    status: item.status,
    translator_name_snapshot: item.translator_name_snapshot,
    cooperation_type_snapshot: item.cooperation_type_snapshot,
    planned: normalizeWordCountValues(item.planned),
    actual: normalizeWordCountValues(item.actual),
    translation_scope: item.translation_scope,
    milestones: item.milestones || [],
    settlement_method: settlementInputValue(item),
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
  const dispatch = selectedProjectDispatch.value
  if (!dispatch) return
  if (!ensureCanManage(dispatch)) return
  inlineSavingId.value = row.id
  try {
    await updateManuscriptSettlement(dispatch.id, row.id, {
      settlement_method: String(row.settlement_method || '').trim() || null,
      custom_settlement_method: null,
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
  arrangements: [],
  updated_at: null
})

watch(
  [
    () => mailStageVisible.value,
    () => selectedProjectDispatch.value?.id,
    () => activeExistingArrangement.value?.id
  ],
  loadActiveMailPreview,
  { immediate: true }
)

const settlementForm = reactive({
  dispatch_id: '',
  arrangement_id: '',
  entity_type: 'project',
  entity_id: '',
  translator_name: '',
  actual: createEmptyWordCountValues(),
  word_count_matrix: createEmptyWordCountMatrix(),
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
const HIDDEN_MANUSCRIPT_PROJECT_STATUSES = new Set([
  '',
  'pending',
  'pending_confirmation'
])

function canShowInManuscriptArrangements(row) {
  return !HIDDEN_MANUSCRIPT_PROJECT_STATUSES.has(
    String(row?.project_status || '').trim()
  )
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

const plannedWordTotals = computed(() =>
  sumWordCountValues(dispatchForm.arrangements.map((item) => item.planned))
)

const wordDifferenceMessage = computed(() => {
  const estimate = selectedProject.value?.word_count_matrix?.translator_estimate
  return `译员预定合计：${formatWordCountValues(plannedWordTotals.value)}；项目预估：${formatWordCountValues(estimate)}。各计量口径分别汇总。`
})

const wordDifferenceType = computed(() => 'info')

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
  if (!selectedProject.value || workbenchReadonly.value || !canManageSelectedProject.value) return
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

function handleTranslatorRowClick(row, column) {
  if (!row || column?.type === 'selection') return

  const isSelected = workspaceSelectedTranslators.value.some(
    (item) => item.id === row.id
  )
  workspaceTranslatorTableRef.value?.toggleRowSelection(row, !isSelected)

  if (
    !isSelected
    && dispatchForm.arrangements.some((item) => item.translator_id === row.id)
  ) {
    activeArrangementTranslatorId.value = row.id
  }
}

function settlementInputValue(row) {
  const labels = {
    single: '单结',
    monthly: '月结',
    prepaid: '预付'
  }
  if (row?.settlement_method === 'other') {
    return String(row?.custom_settlement_method || '其他').trim()
  }
  return labels[row?.settlement_method] || String(row?.settlement_method || '').trim()
}

function settlementLabel(row) {
  return settlementInputValue(row) || '未填写'
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

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function isOverdue(value) {
  if (!value) return false
  const time = new Date(value).getTime()
  return Number.isFinite(time) && time < Date.now()
}

function projectWordSummary(row) {
  return formatWordCountMatrix(row?.word_count_matrix, { empty: '未填写' })
}

function projectWordCount(row) {
  return projectWordSummary(row)
}

function projectWordListSummary(row) {
  return getWordCountMatrixListSummary(row?.word_count_matrix)
}

function assignmentWordSummary(assignment) {
  if (!assignment) return '未填写'
  return `预定：${formatWordCountValues(assignment.planned)} / 实际：${formatWordCountValues(assignment.actual)}`
}

function assignmentTotalSummary(dispatch, dimension) {
  const totals = sumWordCountValues(
    activeAssignments(dispatch).map((item) => item?.[dimension])
  )
  return formatWordCountValues(totals)
}

function matrixEntityType(row) {
  return row?.entity_type === 'suborder' ? 'suborder' : 'project'
}

function matrixEntityId(row) {
  return matrixEntityType(row) === 'suborder' ? row?.sub_order_id : row?.translation_project_id
}

async function handleWordCountMatrixSaved() {
  const identity = projectIdentity(selectedProject.value)
  await Promise.all([loadContext(), loadDispatches()])
  const freshProject = activeProjects.value.find((item) => projectIdentity(item) === identity)
  if (freshProject) selectedProject.value = freshProject
  const freshDispatch = selectedProjectDispatch.value
  if (freshDispatch && dispatchForm.id === freshDispatch.id) hydrateDispatchForm(freshDispatch)
  await loadActiveMailPreview()
}

async function handleSettlementMatrixSaved(saved) {
  const translator = saved?.translators?.find(
    (item) => item.arrangement_id === settlementForm.arrangement_id
  )
  if (translator) settlementForm.actual = normalizeWordCountValues(translator.actual)
  await handleWordCountMatrixSaved()
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

function workbenchMilestoneLabel(milestone) {
  const name = legacyMilestoneName(milestone)
  if (milestone?.milestone_type === 'final') return '译员交稿全稿预定时间'
  const phase = name.match(/(?:预定时间|阶段)(\d+)$/)
  return phase ? `译员交稿_预定时间${phase[1]}` : name
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
派稿文路径：${selectedProject.value.dispatch_path || '待填写'}
参考文件路径一：${selectedProject.value.reference_file_path_one || '无'}

请以项目经理提供的稿件文件和最终要求为准。`
}

function createAssignment(translator) {
  return {
    translator_id: translator.id,
    translator_name: translator.translator_name,
    planned: createEmptyWordCountValues(),
    actual: createEmptyWordCountValues(),
    translation_scope: '',
    settlement_method: '',
    custom_settlement_method: '',
    translator_unit_price: null,
    translator_total_price: null,
    email_subject: defaultSubject(),
    email_body: defaultBody(translator),
    remarks: '',
    milestones: defaultMilestones()
  }
}

function normalizedProjectTranslatorEstimate() {
  return normalizeWordCountValues(
    selectedProject.value?.word_count_matrix?.translator_estimate
      || selectedProject.value?.word_count_matrix?.translatorEstimate
  )
}

function hasWordCountValue(values) {
  return Object.values(normalizeWordCountValues(values)).some((value) => value !== null)
}

function serializedWordCountValues(values) {
  return JSON.stringify(normalizeWordCountValues(values))
}

function applySingleTranslatorEstimateDefault(assignments = dispatchForm.arrangements) {
  if (assignments.length !== 1) return

  const estimate = normalizedProjectTranslatorEstimate()
  if (!hasWordCountValue(estimate)) return

  const assignment = assignments[0]
  const currentSnapshot = serializedWordCountValues(assignment.planned)
  const automaticSnapshot = assignment._projectEstimatePrefillSnapshot

  // 自动值未被改动时，项目预估发生变化也同步刷新；人工填写的内容永不覆盖。
  if (automaticSnapshot && currentSnapshot === automaticSnapshot) {
    assignment.planned = estimate
    assignment._projectEstimatePrefillSnapshot = serializedWordCountValues(estimate)
    return
  }
  if (hasWordCountValue(assignment.planned)) return

  assignment.planned = estimate
  assignment._projectEstimatePrefillSnapshot = serializedWordCountValues(estimate)
}

function revokeUnchangedSingleTranslatorDefaults(assignments) {
  if (assignments.length <= 1) return
  assignments.forEach((assignment) => {
    const automaticSnapshot = assignment._projectEstimatePrefillSnapshot
    if (!automaticSnapshot) return

    // 从单人改为多人时，仅撤回尚未被用户修改过的自动带入值。
    if (serializedWordCountValues(assignment.planned) === automaticSnapshot) {
      assignment.planned = createEmptyWordCountValues()
    }
    delete assignment._projectEstimatePrefillSnapshot
  })
}

function syncSelectedTranslators(ids) {
  const existing = new Map(
    dispatchForm.arrangements.map((item) => [item.translator_id, item])
  )
  const assignments = ids
    .map((id) => {
      if (existing.has(id)) return existing.get(id)
      const translator = translatorById(id)
      return translator ? createAssignment(translator) : null
    })
    .filter(Boolean)
  revokeUnchangedSingleTranslatorDefaults(assignments)
  applySingleTranslatorEstimateDefault(assignments)
  dispatchForm.arrangements = assignments
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

function isDispatchExpanded(row) {
  return expandedDispatchIds.value.has(row.id)
}

function handleDispatchExpandChange(_row, expandedRows) {
  expandedDispatchIds.value = new Set(expandedRows.map((item) => item.id))
}

function toggleDispatchExpansion(row) {
  if (!row.arrangements?.length) return
  dispatchTableRef.value?.toggleRowExpansion(row, !isDispatchExpanded(row))
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
  Object.assign(dispatchForm, { id: '', remarks: '', arrangements: [], updated_at: null })
  selectedTranslatorIds.value = []
  activeArrangementTranslatorId.value = ''
  workbenchStage.value = 'arrange'
}

function hydrateDispatchForm(row, { asNew = false } = {}) {
  dispatchForm.id = asNew ? '' : row.id
  dispatchForm.remarks = row.remarks || ''
  dispatchForm.updated_at = asNew ? null : (row.updated_at || null)
  dispatchForm.arrangements = (row.arrangements || []).map((item) => ({
    id: item.id,
    translator_id: item.translator_id,
    translator_name: item.translator_name_snapshot,
    translator_name_snapshot: item.translator_name_snapshot,
    planned: normalizeWordCountValues(item.planned),
    actual: normalizeWordCountValues(item.actual),
    translation_scope: item.translation_scope || '',
    settlement_method: settlementInputValue(item),
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
  if (asNew) applySingleTranslatorEstimateDefault()
}

function prepareWorkbenchForProject() {
  creatingNewBatch.value = false
  const existing = selectedProjectDispatch.value
  if (existing) {
    hydrateDispatchForm(existing)
    workbenchStage.value = existing.status === 'draft' ? 'arrange' : 'send'
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

function startNewBatch() {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择订单')
    return
  }
  if (!ensureCanManage()) return
  creatingNewBatch.value = true
  resetDispatchForm()
  selectedTranslatorIds.value = workspaceSelectedTranslators.value.map((item) => item.id)
  syncSelectedTranslators(selectedTranslatorIds.value)
  applySingleTranslatorEstimateDefault()
  activeArrangementTranslatorId.value = dispatchForm.arrangements[0]?.translator_id || ''
  workbenchStage.value = 'arrange'
}

function openCreateDialog() {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择订单')
    return
  }
  if (!ensureCanManage()) return
  resetDispatchForm()
  selectedTranslatorIds.value = workspaceSelectedTranslators.value.map((item) => item.id)
  syncSelectedTranslators(selectedTranslatorIds.value)
  activeArrangementTranslatorId.value =
    dispatchForm.arrangements[0]?.translator_id || ''
  dispatchDialogVisible.value = true
}

function editDraft(row) {
  if (!ensureCanManage(row)) return
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
  if (!ensureCanManage(row)) return
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
    expected_updated_at: dispatchForm.id ? dispatchForm.updated_at || null : undefined,
    arrangements: dispatchForm.arrangements.map((item) => ({
      translator_id: item.translator_id,
      planned: item.planned,
      actual: item.actual,
      translation_scope: item.translation_scope || null,
      settlement_method: String(item.settlement_method || '').trim() || null,
      custom_settlement_method: null,
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
  if (!ensureCanManage()) return
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
    creatingNewBatch.value = false
    dispatchForm.id = saved.id
    dispatchForm.updated_at = saved.updated_at || null
    if (shouldConfirm) {
      await confirmManuscriptDispatch(saved.id)
      ElMessage.success('派稿批次已确认，订单状态已更新为“已排译员”')
    } else {
      ElMessage.success('派稿草稿已保存')
    }
    dispatchDialogVisible.value = false
    await Promise.all([loadContext(), loadDispatches()])
    prepareWorkbenchForProject()
    if (shouldConfirm) workbenchStage.value = 'send'
  } catch (error) {
    ElMessage.error(error.detail || '保存稿件安排失败')
  } finally {
    saving.value = false
  }
}

async function sendActiveWorkbenchAssignment() {
  if (!selectedProjectDispatch.value || !activeExistingArrangement.value) return
  if (!ensureCanManage(selectedProjectDispatch.value)) return
  await openMailPreviewDialog(
    selectedProjectDispatch.value,
    activeExistingArrangement.value
  )
}

async function confirmExisting(row) {
  if (!ensureCanManage(row)) return
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
  if (!ensureCanManage(row)) return false
  if (!mailStatus.configured) {
    ElMessage.error(mailStatus.detail || '邮件服务尚未配置')
    return false
  }
  try {
    sendingBatchId.value = row.id
    const result = await sendManuscriptDispatch(row.id, mailAttachmentFile.value)
    if (result.failed_count) {
      ElMessage.warning(`发送完成：成功 ${result.sent_count}，失败 ${result.failed_count}，跳过 ${result.skipped_count}`)
    } else {
      ElMessage.success(`发送完成：成功 ${result.sent_count}，跳过 ${result.skipped_count}`)
    }
    await Promise.all([loadContext(), loadDispatches()])
    return true
  } catch (error) {
    ElMessage.error(error.detail || '批量发送失败')
    return false
  } finally {
    sendingBatchId.value = ''
  }
}

async function sendAssignment(dispatch, assignment) {
  if (!ensureCanManage(dispatch)) return false
  if (!mailStatus.configured) {
    ElMessage.error(mailStatus.detail || '邮件服务尚未配置')
    return false
  }
  try {
    sendingId.value = assignment.id
    await sendManuscriptAssignment(
      dispatch.id,
      assignment.id,
      mailAttachmentFile.value
    )
    ElMessage.success('邮件发送成功')
    await Promise.all([loadContext(), loadDispatches()])
    return true
  } catch (error) {
    ElMessage.error(error.detail || '邮件发送失败')
    await loadDispatches()
    return false
  } finally {
    sendingId.value = ''
  }
}

async function cancelBatch(row) {
  if (!ensureCanManage(row)) return
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
  if (!ensureCanManage(dispatch)) return
  Object.assign(settlementForm, {
    dispatch_id: dispatch.id,
    arrangement_id: assignment.id,
    entity_type: matrixEntityType(dispatch),
    entity_id: matrixEntityId(dispatch),
    translator_name: assignment.translator_name_snapshot,
    actual: normalizeWordCountValues(assignment.actual),
    word_count_matrix: createEmptyWordCountMatrix(),
    settlement_method: settlementInputValue(assignment),
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
  const dispatch = dispatches.value.find(
    (item) => item.id === settlementForm.dispatch_id
  )
  if (!ensureCanManage(dispatch)) return
  settlementSaving.value = true
  try {
    await updateManuscriptSettlement(
      settlementForm.dispatch_id,
      settlementForm.arrangement_id,
      {
        settlement_method: String(settlementForm.settlement_method || '').trim() || null,
        custom_settlement_method: null,
        translator_unit_price: settlementForm.translator_unit_price,
        translator_total_price: settlementForm.translator_total_price,
        remarks: settlementForm.remarks || null
      }
    )
    settlementDialogVisible.value = false
    ElMessage.success('结算信息已保存')
    await loadDispatches()
  } catch (error) {
    ElMessage.error(error.detail || '保存结算信息失败')
  } finally {
    settlementSaving.value = false
  }
}

function isAbortError(error) {
  return error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError'
}

function onProjectKeywordInput(value) {
  clearTimeout(projectSearchTimer)
  projectSearchTimer = null
  if (!String(value || '').trim()) {
    loadContext()
    return
  }
  projectSearchTimer = setTimeout(() => {
    projectSearchTimer = null
    loadContext()
  }, SEARCH_DEBOUNCE_MS)
}

function runProjectSearch() {
  clearTimeout(projectSearchTimer)
  projectSearchTimer = null
  loadContext()
}

function onDispatchKeywordInput(value) {
  clearTimeout(dispatchSearchTimer)
  dispatchSearchTimer = null
  if (!String(value || '').trim()) {
    loadDispatches()
    return
  }
  dispatchSearchTimer = setTimeout(() => {
    dispatchSearchTimer = null
    loadDispatches()
  }, SEARCH_DEBOUNCE_MS)
}

function runDispatchSearch() {
  clearTimeout(dispatchSearchTimer)
  dispatchSearchTimer = null
  loadDispatches()
}

async function loadContext() {
  contextController?.abort()
  contextController = new AbortController()
  const requestId = ++contextRequestId
  contextLoading.value = true
  try {
    const response = await getManuscriptContext({
      keyword: projectKeyword.value.trim() || undefined,
      project_limit: 100
    }, { signal: contextController.signal })
    if (requestId !== contextRequestId) return
    activeProjects.value = Array.isArray(response?.active_projects?.items)
      ? response.active_projects.items.filter(canShowInManuscriptArrangements)
      : []
    translators.value = Array.isArray(response?.translators) ? response.translators : []
    if (selectedProject.value) {
      const selectedIdentity = projectIdentity(selectedProject.value)
      selectedProject.value = activeProjects.value.find(
        (item) => projectIdentity(item) === selectedIdentity
      ) || null
    }
  } catch (error) {
    if (requestId !== contextRequestId || isAbortError(error)) return
    ElMessage.error(error.detail || '加载项目和译员信息失败，请检查网络后重试')
  } finally {
    if (requestId === contextRequestId) contextLoading.value = false
  }
}

async function loadDispatches() {
  dispatchController?.abort()
  dispatchController = new AbortController()
  const requestId = ++dispatchRequestId
  recordsLoading.value = true
  try {
    const response = await getManuscriptDispatches({
      limit: 500,
      keyword: dispatchKeyword.value.trim() || undefined
    }, { signal: dispatchController.signal })
    if (requestId !== dispatchRequestId) return
    dispatches.value = Array.isArray(response) ? response : []
  } catch (error) {
    if (requestId !== dispatchRequestId || isAbortError(error)) return
    ElMessage.error(error.detail || '加载稿件安排记录失败，请检查网络后重试')
  } finally {
    if (requestId === dispatchRequestId) recordsLoading.value = false
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
    if (selectedProject.value) prepareWorkbenchForProject()
    await loadActiveMailPreview()
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
onBeforeUnmount(() => {
  clearTimeout(projectSearchTimer)
  clearTimeout(dispatchSearchTimer)
  contextController?.abort()
  dispatchController?.abort()
})
</script>

<style scoped>
.manuscript-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 1120px;
}

.panel-header,
.panel-tools,
.selection-bar,
.assignment-card__header,
.subsection-header {
  display: flex;
  align-items: center;
}

.panel-header,
.selection-bar,
.assignment-card__header,
.subsection-header {
  justify-content: space-between;
}

.panel-header h2 {
  margin: 0;
}

.panel-header h2 {
  flex: none;
  font-size: 16px;
  line-height: 22px;
}

.panel-header > div:first-child {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 10px;
}

.panel-header > div:first-child > span {
  margin: 0;
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-header span {
  margin: 5px 0 0;
  color: var(--el-text-color-secondary);
}

.panel-tools {
  gap: 10px;
}

.panel-tools__divider {
  flex: none;
  width: 1px;
  height: 20px;
  margin: 0;
  background: var(--el-border-color);
}

.panel-header .el-button {
  height: 28px;
  min-height: 28px;
}

.panel-header :deep(.el-input__wrapper) {
  min-height: 28px;
}

.legacy-workbench {
  display: grid;
  grid-template-columns: minmax(680px, 2.15fr) minmax(390px, 1fr);
  height: calc(100vh - 200px);
  min-height: 480px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--el-card-border-radius, 4px);
  background: var(--color-surface);
  box-shadow: var(--el-box-shadow-light);
}

.legacy-workbench__left {
  display: grid;
  grid-template-rows: 1fr 1fr;
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--el-border-color);
}

.legacy-workbench__left.is-project-collapsed {
  grid-template-rows: auto minmax(0, 1fr);
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

.legacy-project-panel.is-collapsed :deep(.el-card__body) {
  display: none;
}

.project-panel-header {
  cursor: pointer;
  user-select: none;
}

.project-panel-header:hover h2 {
  color: var(--el-color-primary);
}

.project-panel-header:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.project-panel-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.project-panel-chevron {
  flex: none;
  width: 8px;
  height: 8px;
  margin-right: 3px;
  border-right: 2px solid var(--el-text-color-secondary);
  border-bottom: 2px solid var(--el-text-color-secondary);
  transform: rotate(225deg);
  transition: transform 0.2s ease;
}

.project-panel-chevron.is-collapsed {
  transform: rotate(45deg);
}

.legacy-project-panel :deep(.el-card__header),
.legacy-translator-panel :deep(.el-card__header) {
  padding: 5px 10px;
  background: var(--el-fill-color-light);
}

.legacy-assignment-panel :deep(.el-card__header) {
  padding: 6px 10px;
  background: var(--el-fill-color-light);
}

.records-panel :deep(.el-card__header) {
  padding: 6px 12px;
}

.legacy-project-panel :deep(.el-card__body),
.legacy-translator-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 6px 8px 8px;
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

.legacy-translator-panel :deep(.el-table__row) {
  cursor: pointer;
}

.legacy-project-panel :deep(.el-table .cell),
.legacy-translator-panel :deep(.el-table .cell) {
  padding-right: 6px;
  padding-left: 6px;
}

.legacy-assignment-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
  overflow-y: auto;
}

.legacy-assignment-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.legacy-assignment-panel__header > div:first-child {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 8px;
}

.legacy-assignment-panel__header h2 {
  flex: none;
  margin: 0;
  color: var(--el-color-primary);
  font-size: 16px;
}

.legacy-assignment-panel__header span {
  display: block;
  min-width: 0;
  margin-top: 0;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legacy-assignment-panel__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
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
  margin-bottom: 0;
}

.assignment-tabs > :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.assignment-tabs > :deep(.el-tabs__header .el-tabs__item) {
  min-width: 88px;
  font-weight: 600;
}

.assignment-stage-content {
  min-width: 0;
}

.assignment-translator-tabs {
  margin-bottom: 8px;
}

.assignment-translator-tabs :deep(.el-tabs__header) {
  margin-bottom: 8px;
}

.assignment-translator-tabs :deep(.el-tabs__item) {
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
}

.legacy-field-grid {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr);
  border-top: 1px solid var(--el-border-color);
  border-left: 1px solid var(--el-border-color);
}

.legacy-mail-fields {
  display: grid;
  grid-template-columns: 116px minmax(0, 1fr);
  border-top: 1px solid var(--el-border-color);
  border-left: 1px solid var(--el-border-color);
}

.legacy-field-grid > label,
.legacy-mail-fields > label {
  display: flex;
  min-height: 39px;
  align-items: center;
  padding: 7px 6px;
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-color-primary-light-9);
  color: var(--el-text-color-regular);
  font-size: 13px;
  word-break: break-word;
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

.legacy-word-count-summary--compact {
  justify-content: flex-start;
  min-width: 0;
}

.compact-table-link {
  max-width: 100%;
  height: auto;
  padding: 0;
}

.compact-table-value {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 5px;
  white-space: nowrap;
}

.compact-table-value__primary {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.compact-table-value__count {
  flex: none;
  padding: 0 5px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  line-height: 18px;
}

.compact-deadline {
  display: block;
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legacy-mail-editor {
  margin-top: 12px;
}

.mail-path-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
}

:deep(.mail-send-preview-dialog) {
  display: flex;
  max-height: 90vh;
  flex-direction: column;
  overflow: hidden;
}

:deep(.mail-send-preview-dialog .el-dialog__header),
:deep(.mail-send-preview-dialog .el-dialog__footer) {
  flex: none;
}

:deep(.mail-send-preview-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

:deep(.mail-send-preview-dialog .el-dialog__footer) {
  border-top: 1px solid var(--el-border-color);
  background: var(--el-fill-color-lighter);
}

.mail-send-preview-body > .el-alert {
  margin-bottom: 12px;
}

.mail-attachment-upload {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
}

.mail-attachment-upload > label {
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 32px;
}

.mail-attachment-upload :deep(.el-upload-list) {
  margin-bottom: 0;
}

.mail-send-preview-body :deep(.el-descriptions__content) {
  word-break: break-all;
}

.mail-send-preview-content {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  margin-top: 14px;
  border-top: 1px solid var(--el-border-color);
  border-left: 1px solid var(--el-border-color);
}

.mail-send-preview-content > label,
.mail-send-preview-content > :not(label) {
  padding: 6px;
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
}

.mail-send-preview-content > label {
  display: flex;
  align-items: center;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.mail-stage .el-alert {
  margin-bottom: 8px;
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

.panel-tools.project-panel-tools .el-input {
  width: 200px;
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

.translator-tabs :deep(.el-tabs__header) {
  margin-bottom: 6px;
}

.translator-tabs :deep(.el-tabs__item.is-top) {
  height: 30px;
  padding: 0 10px;
  font-size: 12px;
  line-height: 30px;
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

.dispatch-records-table :deep(.dispatch-expand-column) {
  padding: 0 !important;
  border-right: 0 !important;
}

.dispatch-records-table :deep(.dispatch-expand-column .cell) {
  display: none;
  padding: 0;
}

.dispatch-order-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.dispatch-order-cell > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
