<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>项目详情</span>
        <el-button v-if="canWriteProjects" type="primary" @click="handleAdd">新增项目</el-button>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="项目名称">
        <el-input v-model="searchForm.projectName" placeholder="请输入项目名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="订单号">
        <el-input v-model="searchForm.orderNo" placeholder="请输入订单号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="客户简称">
        <el-input v-model="searchForm.clientShortName" placeholder="请输入客户简称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="searchForm.projectStatus" placeholder="请选择状态" clearable style="width: 160px" @change="handleSearch">
          <el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" row-key="id" border :row-class-name="getProjectRowClassName">
      <el-table-column type="expand" width="48">
        <template #default="{ row }">
          <div class="sub-order-panel">
            <div class="sub-order-panel__header">
              <div class="sub-order-panel__meta">
                <span>子订单列表</span>
                <el-tag size="small" type="info">共 {{ getSubOrderCount(row) }} 条</el-tag>
                <el-tag v-if="hasMoreSubOrders(row)" size="small" type="warning">当前仅显示前 {{ SUB_ORDER_PREVIEW_LIMIT }} 条</el-tag>
              </div>
              <el-button v-if="hasMoreSubOrders(row)" type="primary" link @click="goToSubOrderManagement(row)">进入子订单管理页</el-button>
            </div>
            <el-table :data="getVisibleSubOrders(row)" border>
              <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
              <el-table-column prop="subProjectName" label="子项目名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="languagePair" label="语言" min-width="120" />
              <el-table-column label="字数摘要" min-width="180">
                <template #default="{ row: subRow }">{{ formatWordCountSummary(subRow) }}</template>
              </el-table-column>
              <el-table-column label="译员安排" min-width="180" show-overflow-tooltip>
                <template #default="{ row: subRow }">{{ formatAssignedTranslators(subRow.assignedTranslators, subRow.translatorName) }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" min-width="120">
                <template #default="{ row: subRow }">
                  <el-tag :type="getStatusType(subRow.status)">{{ getStatusLabel(subRow.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="详情" width="100" fixed="right">
                <template #default="{ row: subRow }">
                  <DetailPopover :row="subRow" title="子订单详情" :items="subOrderDetailItems" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row: subRow }">
                  <el-button v-if="canWriteProjects" type="primary" size="small" link @click="openProjectEditorForSubOrder(row, subRow)">编辑</el-button>
                  <el-button v-if="canWriteProjects" type="danger" size="small" link @click="handleDeleteSubOrder(subRow)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column type="index" label="序号" width="55" />
      <el-table-column prop="orderNo" label="订单号" min-width="220">
        <template #default="{ row }">
          <div class="order-no-actions">
            <span class="order-no-text" :title="row.orderNo">{{ row.orderNo }}</span>
            <div class="order-no-btns" v-if="canReadProjectFiles">
              <el-button type="primary" size="small" link :title="'打开路径'" @click.stop="openOriginalPath(row)">
                <svg viewBox="0 0 1024 1024" width="14" height="14" fill="currentColor"><path d="M928 256H512L416 160H128a96 96 0 0 0-96 96v544a96 96 0 0 0 96 96h800a96 96 0 0 0 96-96V352a96 96 0 0 0-96-96zM128 256h249.6l64 64H128V256zm800 544H128V448h800v352z"/></svg>
              </el-button>
              <el-button type="primary" size="small" link :title="'复制路径'" @click.stop="copyOriginalPath(row)">
                <svg viewBox="0 0 1024 1024" width="14" height="14" fill="currentColor"><path d="M768 128H256a64 64 0 0 0-64 64v512a64 64 0 0 0 64 64h512a64 64 0 0 0 64-64V192a64 64 0 0 0-64-64zm0 576H256V192h512v512zM640 832v64a64 64 0 0 1-64 64H160a64 64 0 0 1-64-64V384a64 64 0 0 1 64-64h64v64H160v512h416v-64h64z"/></svg>
              </el-button>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="customerOrderNo" label="客户单号" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.customerOrderNo || '-' }}</template>
      </el-table-column>
      <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="serviceContent" label="服务内容" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.serviceContent || '-' }}</template>
      </el-table-column>
      <el-table-column prop="taskType" label="任务类型" min-width="100">
        <template #default="{ row }">{{ row.taskType || '-' }}</template>
      </el-table-column>
      <el-table-column prop="clientShortName" label="客户简称" min-width="110" show-overflow-tooltip />
      <el-table-column prop="projectManagerName" label="项目经理" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.projectManagerName || '-' }}</template>
      </el-table-column>
      <el-table-column label="已分配译员" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ formatAssignedTranslators(row.assignedTranslators, row.translatorName) }}</template>
      </el-table-column>
      <el-table-column prop="projectStatus" label="状态" min-width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.projectStatus)">{{ getStatusLabel(row.projectStatus) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="customerDeadlineTime" label="客户交稿时间" min-width="150" show-overflow-tooltip />
      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <DetailPopover :row="row" title="项目详情" :items="projectDetailItems" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canReadProjectFiles" type="success" size="small" @click="handleFiles(row)">文件</el-button>
          <el-button v-if="canWriteProjects" type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button v-if="canWriteProjects" type="danger" size="small" @click="handleDeleteProject(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      style="margin-top: 20px"
      @size-change="applyPagination"
      @current-change="applyPagination"
    />

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1160px" top="4vh" @closed="onProjectDialogClosed">
      <div class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
          <el-tabs v-model="projectDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <el-collapse v-model="projectBasicExpandedSections" class="project-basic-collapse">
                  <el-collapse-item name="project">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目与客户</span>
                        <span class="project-basic-collapse__hint">订单、项目名称、客户及服务信息</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled /></el-form-item></el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="项目名称">
                      <div class="auto-name-field">
                        <el-input
                          v-model="form.projectName"
                          placeholder="选择客户简称后自动生成"
                          @input="handleProjectNameInput"
                        />
                        <div class="auto-name-field__hint">按“客户简称-当前日期”自动生成，存在子订单时追加批次；也可手动修改。</div>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="任务类型">
                      <el-select
                        v-model="form.taskType"
                        filterable
                        allow-create
                        clearable
                        placeholder="成交项目自动取自咨询类型，也可手工补录"
                        style="width: 100%"
                      >
                        <el-option v-for="item in taskTypeOptions" :key="item" :label="item" :value="item" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="来源咨询 ID"><el-input v-model="form.consultationId" readonly placeholder="手工新增项目无来源咨询" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="客户简称">
                      <el-autocomplete
                        v-model="form.clientShortName"
                        :fetch-suggestions="fetchClientSuggestions"
                        value-key="client_short_name"
                        placeholder="选择母客户或其下的子客户"
                        clearable
                        :debounce="300"
                        :trigger-on-focus="true"
                        style="width: 100%"
                        @select="handleClientSelect"
                        @input="handleClientShortNameInput"
                        @clear="clearSelectedClient"
                      >
                        <template #default="{ item }">
                          <div class="client-suggestion">
                            <span>
                              {{ item.client_short_name }}
                              <el-tag v-if="item.sub_client_id" size="small" type="warning">子客户</el-tag>
                            </span>
                            <span class="client-suggestion__meta">{{ item.client_code }} · {{ item.client_name }}{{ item.parent_client_short_name ? ` · 归属 ${item.parent_client_short_name}` : '' }}</span>
                          </div>
                        </template>
                      </el-autocomplete>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户编号"><el-input v-model="form.clientCode" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户单号"><el-input v-model="form.customerOrderNo" placeholder="客户公司内部用于记录该外包项目的单号" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="负责人联系方式"><el-input v-model="form.managerContact" readonly placeholder="选择客户后从客户表自动带出" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="服务内容">
                      <el-select
                        v-model="form.serviceContent"
                        filterable
                        allow-create
                        default-first-option
                        clearable
                        placeholder="可选择翻译、排版，或直接输入自定义内容"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="item in serviceContentOptions"
                          :key="item"
                          :label="item"
                          :value="item"
                        />
                      </el-select>
                    </el-form-item>
                  </el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="form.languagePair" /></el-form-item></el-col>
                      </el-row>
                    </div>
                  </el-collapse-item>

                  <el-collapse-item name="business">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目商务信息</span>
                        <span class="project-basic-collapse__hint">合同、报价单及客户要求</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="合同类型">
                      <el-input v-model="form.projectContractType" clearable placeholder="请输入项目合同类型" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="合同状态">
                      <el-input v-model="form.projectContractStatus" clearable placeholder="请输入项目合同状态" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="需提供报价单">
                  <el-checkbox v-model="form.quotationRequired">需要提供项目报价单</el-checkbox>
                </el-form-item>
                <el-row v-if="form.quotationRequired" :gutter="16">
                  <el-col :xs="24" :md="8">
                    <el-form-item label="报价单状态">
                      <el-input v-model="form.quotationStatus" clearable placeholder="请输入状态" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="16">
                    <el-form-item label="报价单路径">
                      <el-input v-model="form.quotationPath" clearable placeholder="如 \\win-server\项目报价单" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="客户专业要求">
                  <el-input v-model="form.customerRequirementProfessional" type="textarea" :rows="2" placeholder="请输入客户专业要求" />
                </el-form-item>
                      <el-form-item label="客户特殊要求">
                  <el-input v-model="form.customerRequirementSpecial" type="textarea" :rows="2" placeholder="请输入客户特殊要求" />
                      </el-form-item>
                    </div>
                  </el-collapse-item>

                  <el-collapse-item name="execution">
                    <template #title>
                      <div class="project-basic-collapse__title">
                        <span>项目执行信息</span>
                        <span class="project-basic-collapse__hint">状态、负责人、字数、时间及确认信息</span>
                      </div>
                    </template>
                    <div class="project-basic-collapse__body">
                      <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态" prop="projectStatus"><el-select v-model="form.projectStatus" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="项目经理">
                      <el-select
                        v-model="form.projectManagerId"
                        filterable
                        clearable
                        placeholder="绑定管理层主负责人"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="manager in projectManagerOptions"
                          :key="manager.id"
                          :label="manager.full_name || manager.username"
                          :value="manager.id"
                        />
                      </el-select>
                      <div class="auto-name-field__hint">管理层主负责人，与当前流程处理人相互独立。</div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="字数摘要">
                      <div class="word-count-summary">
                        <span>{{ formatWordCountSummary(form) }}</span>
                        <el-button type="primary" link @click="openWordCountDrawer('project')">字数详情</el-button>
                      </div>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户反馈"><el-input v-model="form.clientFeedback" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户接单时间"><el-date-picker v-model="form.customerReceptionTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="PM确认人 ID"><el-input v-model="form.pmConfirmedBy" /></el-form-item></el-col>
                </el-row>
                      <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="大项目经理确认"><el-input v-model="form.majorProjectManagerConfirmation" readonly placeholder="由“稿件安排”的确认安排操作自动记录" /></el-form-item></el-col>
                      </el-row>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </el-tab-pane>

            <el-tab-pane label="分配与预估" name="assignment">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="已分配译员"><el-input :model-value="formatAssignedTranslators(form.assignedTranslators, form.translatorName)" readonly placeholder="请在“稿件安排”模块中分配译员" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-alert title="新的译员分配统一由“稿件安排”维护；历史单译员字段仅用于兼容旧数据。" type="info" :closable="false" show-icon /></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="字数与预估">
                      <div class="word-count-summary">
                        <span>{{ formatWordCountSummary(form) }}</span>
                        <el-button type="primary" link @click="openWordCountDrawer('project')">展开字数详情</el-button>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="网络文件路径"><el-input v-model="form.networkFilePath" type="textarea" :rows="3" placeholder="如需多个路径，可按行填写" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="参考文件路径一"><el-input v-model="form.referenceFilePathOne" type="textarea" :rows="2" placeholder="供稿件安排发信时引用，通过项目外键自动带入" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in progressFieldConfigs" :key="item.key" class="progress-card">
                  <div class="progress-card__header">
                    <span>{{ item.label }}</span>
                    <strong>{{ formatProgressDisplay(form[item.key]) }}</strong>
                  </div>
                  <el-slider
                    v-model="form[item.key]"
                    :min="0"
                    :max="100"
                    :marks="progressMarks"
                    show-input
                    input-size="small"
                  />
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="子订单" name="suborders">
              <template v-if="form.id">
                <div class="section-header">
                  <div class="section-title">子订单管理</div>
                  <div class="section-actions">
                    <el-button v-if="canWriteProjects" type="primary" @click="openCreateSubOrderDialog">新增子订单</el-button>
                    <el-button v-if="canWriteProjects" @click="openBatchDialog">批量新增子订单</el-button>
                    <el-button v-if="hasMoreSubOrders({ subOrders: currentProjectSubOrders })" @click="goToSubOrderManagement(form)">查看全部子订单</el-button>
                  </div>
                </div>

                <el-alert
                  v-if="hasMoreSubOrders({ subOrders: currentProjectSubOrders })"
                  title="当前仅展示前 10 条子订单，更多数据请进入独立子订单管理页查看和操作。"
                  type="warning"
                  :closable="false"
                  show-icon
                  class="sub-order-alert"
                />

                <el-table :data="getVisibleSubOrders({ subOrders: currentProjectSubOrders })" border>
                  <el-table-column prop="subOrderNo" label="子订单号" min-width="180" />
                  <el-table-column prop="subProjectName" label="子项目名称" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="languagePair" label="语言" min-width="120" />
                  <el-table-column prop="wordCount" label="字数" min-width="100" />
                  <el-table-column prop="status" label="状态" min-width="120">
                    <template #default="{ row }">
                      <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="详情" width="100" fixed="right">
                    <template #default="{ row }">
                      <DetailPopover :row="row" title="子订单详情" :items="subOrderDetailItems" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="180" fixed="right">
                    <template #default="{ row }">
                      <el-button v-if="canWriteProjects" type="primary" size="small" link @click="handleEditSubOrder(row)">编辑</el-button>
                      <el-button v-if="canWriteProjects" type="danger" size="small" link @click="handleDeleteSubOrder(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
              <el-alert v-else title="请先保存母订单，再在此 Tab 中新增或批量新增子订单。" type="info" :closable="false" show-icon />
            </el-tab-pane>

            <el-tab-pane v-if="canReadProjectFiles" label="项目文件" name="files">
              <ProjectFilesTab
                v-if="form.id"
                :project-id="form.id"
                :order-no="form.orderNo"
                entity-type="project"
                :active="projectDialogTab === 'files'"
                @status-change="handleProjectFileStatusChange"
              />
              <el-alert
                v-else
                title="请先保存项目，文件记录将自动关联保存后的订单号。"
                type="info"
                :closable="false"
                show-icon
              />
            </el-tab-pane>
          </el-tabs>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="canWriteProjects" type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="subOrderDialogVisible" :title="subOrderDialogTitle" width="1040px" top="6vh" @closed="resetSubOrderForm">
      <div class="editor-body">
        <el-form ref="subOrderFormRef" :model="subOrderForm" :rules="subOrderRules" label-width="120px">
          <el-tabs v-model="subOrderDialogTab" class="editor-tabs">
            <el-tab-pane label="基础信息" name="basic">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="母订单号"><el-input :model-value="form.orderNo" disabled /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="子订单号"><el-input v-model="subOrderForm.subOrderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="子项目名称" prop="subProjectName"><el-input v-model="subOrderForm.subProjectName" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="状态"><el-select v-model="subOrderForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="subOrderForm.fileTypeSecondary" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="subOrderForm.languagePair" :show-hint="false" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="subOrderForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="字数摘要">
                      <div class="word-count-summary">
                        <span>{{ formatWordCountSummary(subOrderForm) }}</span>
                        <el-button type="primary" link @click="openWordCountDrawer('subOrder')">字数详情</el-button>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="subOrderForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                  <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="subOrderForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="客户反馈"><el-input v-model="subOrderForm.clientFeedback" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="备注"><el-input v-model="subOrderForm.remarks" type="textarea" :rows="3" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="分配与预估" name="assignment">
              <div class="form-section">
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="已分配译员"><el-input :model-value="formatAssignedTranslators(subOrderForm.assignedTranslators, subOrderForm.translatorName)" readonly placeholder="请在“稿件安排”模块中分配译员" /></el-form-item></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-alert title="新的译员分配统一由“稿件安排”维护；历史单译员字段仅用于兼容旧数据。" type="info" :closable="false" show-icon /></el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24">
                    <el-form-item label="字数与预估">
                      <div class="word-count-summary">
                        <span>{{ formatWordCountSummary(subOrderForm) }}</span>
                        <el-button type="primary" link @click="openWordCountDrawer('subOrder')">展开字数详情</el-button>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-row :gutter="16">
                  <el-col :xs="24"><el-form-item label="网络文件路径"><el-input v-model="subOrderForm.networkFilePath" type="textarea" :rows="3" /></el-form-item></el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <el-tab-pane label="进度跟踪" name="progress">
              <div class="progress-grid">
                <div v-for="item in subOrderProgressFieldConfigs" :key="item.key" class="progress-card">
                  <div class="progress-card__header">
                    <span>{{ item.label }}</span>
                    <strong>{{ formatProgressDisplay(subOrderForm[item.key]) }}</strong>
                  </div>
                  <el-slider
                    v-model="subOrderForm[item.key]"
                    :min="0"
                    :max="100"
                    :marks="progressMarks"
                    show-input
                    input-size="small"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="subOrderDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitSubOrder">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="批量新增子订单" width="860px" @closed="resetBatchForm">
      <el-form ref="batchFormRef" :model="batchForm" :rules="batchRules" label-width="140px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="生成数量" prop="count"><el-input-number v-model="batchForm.count" :min="1" :max="50" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="起始序号"><el-input-number v-model="batchForm.startIndex" :min="1" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24"><el-form-item label="子项目名前缀"><el-input v-model="batchForm.subProjectNamePrefix" placeholder="留空则按 母项目名称-子订单01 自动生成" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">批量公共字段</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="batchForm.status" clearable style="width: 100%"><el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="优先级"><el-select v-model="batchForm.priority" clearable style="width: 100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="文本类型"><el-input v-model="batchForm.fileTypeSecondary" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="batchForm.languagePair" :show-hint="false" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="字数摘要">
              <div class="word-count-summary">
                <span>{{ formatWordCountSummary(batchForm) }}</span>
                <el-button type="primary" link @click="openWordCountDrawer('batch')">字数详情</el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="batchForm.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="发客户时间"><el-date-picker v-model="batchForm.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="译员ID"><el-input v-model="batchForm.translatorId" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="24">
            <el-alert title="客户、内部及历史预估字数统一在“字数详情”中维护。" type="info" :closable="false" />
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchCreateSubOrders">批量创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="wordCountDrawerVisible"
      :title="`${wordCountDrawerTitle} · 字数详情`"
      width="820px"
      append-to-body
      destroy-on-close
      class="word-count-dialog"
      @closed="syncLegacyWordCount(wordCountDrawerTarget)"
    >
      <el-alert
        title="按统计来源分别记录；项目摘要优先显示公司内部统计，其次显示客户统计，最后回退到旧字数字段。"
        type="info"
        :closable="false"
        show-icon
        class="word-count-dialog__alert"
      />
      <div class="excel-word-grid">
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
              <th>客户统计</th>
              <td class="excel-word-grid__editor">
                <el-input-number
                  v-model="wordCountDrawerTarget.customerWordCount"
                  :min="0"
                  controls-position="right"
                  @change="syncLegacyWordCount(wordCountDrawerTarget)"
                />
              </td>
              <td class="excel-word-grid__editor">
                <el-select v-model="wordCountDrawerTarget.customerWordCountType" clearable placeholder="选择计量口径">
                  <el-option v-for="item in wordCountTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </td>
              <td class="excel-word-grid__text">客户提供的原始统计</td>
            </tr>
            <tr>
              <th>公司内部统计</th>
              <td class="excel-word-grid__editor">
                <el-input-number
                  v-model="wordCountDrawerTarget.internalWordCount"
                  :min="0"
                  controls-position="right"
                  @change="syncLegacyWordCount(wordCountDrawerTarget)"
                />
              </td>
              <td class="excel-word-grid__editor">
                <el-select v-model="wordCountDrawerTarget.internalWordCountType" clearable placeholder="选择计量口径">
                  <el-option v-for="item in wordCountTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </td>
              <td class="excel-word-grid__text">公司复核后的统计</td>
            </tr>
            <tr>
              <th>预计译员字数</th>
              <td class="excel-word-grid__editor">
                <el-input-number
                  v-model="wordCountDrawerTarget.expectedTranslatorWordCount"
                  :min="0"
                  controls-position="right"
                />
              </td>
              <td class="excel-word-grid__editor">
                <el-input
                  v-model="wordCountDrawerTarget.expectedTranslatorStatsMethod"
                  placeholder="预计统计方式"
                />
              </td>
              <td class="excel-word-grid__text">稿件安排优先比较基准</td>
            </tr>
            <tr class="excel-word-grid__compatibility">
              <th>原项目字数（兼容）</th>
              <td class="excel-word-grid__editor">
                <el-input-number
                  v-model="wordCountDrawerTarget.wordCount"
                  :min="0"
                  controls-position="right"
                  disabled
                />
              </td>
              <td class="excel-word-grid__text">—</td>
              <td class="excel-word-grid__text">内部统计优先、客户统计其次，由页面自动同步</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <el-button type="primary" @click="closeWordCountDrawer">完成</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElDescriptions, ElDescriptionsItem, ElDrawer, ElMessage, ElMessageBox, ElTag } from 'element-plus'
import { getProjects, getProjectCount, createProject, updateProject, deleteProject, getNextOrderNo } from '@/api/projects'
import { getProjectFilesByProject } from '@/api/projectFiles'
import { getClients } from '@/api/clients'
import { createSubOrder, deleteSubOrder, getSubOrdersByProject, updateSubOrder } from '@/api/subOrders'
import { getProjectManagerCandidatesAPI } from '@/api/workflow'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import ProjectFilesTab from './components/ProjectFilesTab.vue'
import { hasPermission } from '@/utils/permission'
import { buildAutoProjectName, isAutoProjectName } from '@/utils/projectNaming'

const SUB_ORDER_PREVIEW_LIMIT = 10
const canWriteProjects = hasPermission('projects:write')
const canReadProjectFiles = hasPermission('project_files:read')
const router = useRouter()
const projectDialogTab = ref('basic')
const projectBasicExpandedSections = ref(['project', 'business', 'execution'])
const subOrderDialogTab = ref('basic')
const projectStatusOptions = [
  { label: '待确认', value: 'pending_confirmation' },
  { label: '已确认', value: 'confirmed' },
  { label: '已整理', value: 'organized' },
  { label: '已排译员', value: 'translator_assigned' },
  { label: '已发译员', value: 'sent_to_translator' },
  { label: '译员发回', value: 'translator_returned' },
  { label: '已专检', value: 'special_checked' },
  { label: '已排版', value: 'typeset' },
  { label: '已专检排版', value: 'special_checked_typeset' },
  { label: '已审核', value: 'reviewed' },
  { label: '已发客户', value: 'sent_to_client' },
  { label: '客户反馈', value: 'client_feedback' },
  { label: '反馈后发客户', value: 'feedback_sent_to_client' },
  { label: '已取消', value: 'cancelled' },
  { label: '已部分取消', value: 'partially_cancelled' },
  { label: '已暂停', value: 'paused' }
]
const priorityOptions = ['低', '中', '高', '紧急']
const serviceContentOptions = ['翻译', '排版']
const wordCountTypeOptions = [
  { label: '字符数（不计空格）', value: 'characters_no_spaces' },
  { label: '字数', value: 'words' },
  { label: '中文字符和朝鲜语单词', value: 'cjk_chars_korean_words' },
  { label: '外文字数（除中日韩）', value: 'foreign_words' }
]
const progressFieldConfigs = [
  { key: 'translatorDeliveryProgress', label: '译员交付进度' },
  { key: 'preReviewQcProgress', label: '审校前 QC' },
  { key: 'review1Progress', label: '审校 1' },
  { key: 'review2Progress', label: '审校 2' },
  { key: 'postReviewQcProgress', label: '审校后 QC' },
  { key: 'layoutProgress', label: '排版进度' },
  { key: 'consolidationProgress', label: '整合进度' }
]
const taskTypeOptions = [
  '笔译项目',
  '口译项目',
  '招聘项目',
  '标注项目',
  '配音项目',
  '字幕项目',
  '公证项目',
  '认证项目',
  '其他项目',
  '非项目工作',
]
const subOrderProgressFieldConfigs = [
  ...progressFieldConfigs,
  { key: 'reviewProgress', label: '审核进度（旧字段）' }
]
const progressFieldSet = new Set(subOrderProgressFieldConfigs.map((item) => item.key))
const progressMarks = { 0: '0%', 50: '50%', 100: '100%' }
const projectDetailItems = [
  { label: 'ID', key: 'id', span: 2 },
  { label: '订单号', key: 'orderNo' },
  { label: '项目名称', key: 'projectName' },
  { label: '服务内容', key: 'serviceContent', span: 2 },
  { label: '任务类型', key: 'taskType' },
  { label: '来源咨询ID', key: 'consultationId', span: 2 },
  { label: '客户ID', key: 'clientId' },
  { label: '子客户ID', key: 'subClientId' },
  { label: '客户简称', key: 'clientShortName' },
  { label: '客户编号', key: 'clientCode' },
  { label: '客户单号', key: 'customerOrderNo' },
  { label: '项目经理', key: 'projectManagerName' },
  { label: '客户负责人', key: 'clientManager' },
  { label: '负责人联系方式', key: 'managerContact' },
  { label: '状态', key: 'projectStatus', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '项目文件名', key: 'projectFileName' },
  { label: '翻译文本领域', key: 'projectFileTranslationDomainLevel1', formatter: (value, row) => formatHierarchy(row.projectFileTranslationDomainLevel1, row.projectFileTranslationDomainLevel2) },
  { label: '文件类型', key: 'projectFileTypeLevel1', formatter: (value, row) => formatHierarchy(row.projectFileTypeLevel1, row.projectFileTypeLevel2) },
  { label: '文件格式', key: 'projectFileFormat' },
  { label: '文件属性', key: 'projectFileAttributeLevel1', formatter: (value, row) => formatHierarchy(row.projectFileAttributeLevel1, row.projectFileAttributeLevel2, row.projectFileAttributeLevel3) },
  { label: '文件难度', key: 'projectFileDifficulty' },
  { label: '项目合同', key: 'projectContractType', formatter: (value, row) => formatHierarchy(row.projectContractType, row.projectContractStatus) },
  { label: '项目报价单', key: 'quotationRequired', span: 2, formatter: (value, row) => formatProjectQuotation(row) },
  { label: '客户专业要求', key: 'customerRequirementProfessional', span: 2 },
  { label: '客户特殊要求', key: 'customerRequirementSpecial', span: 2 },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '客户提供字数', key: 'customerWordCount' },
  { label: '客户统计口径', key: 'customerWordCountType', formatter: formatWordCountType },
  { label: '内部核算字数', key: 'internalWordCount' },
  { label: '内部统计口径', key: 'internalWordCountType', formatter: formatWordCountType },
  { label: '原项目字数（兼容字段）', key: 'wordCount' },
  { label: '客户接单时间', key: 'customerReceptionTime' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: 'PM确认人ID', key: 'pmConfirmedBy' },
  { label: '大项目经理确认', key: 'majorProjectManagerConfirmation' },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '预计统计方式', key: 'expectedTranslatorStatsMethod' },
  { label: '预计译员字数', key: 'expectedTranslatorWordCount' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前QC', key: 'preReviewQcProgress' },
  { label: '审校1', key: 'review1Progress' },
  { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '参考文件路径一', key: 'referenceFilePathOne', span: 2 },
  { label: '创建人ID', key: 'createdBy' },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const subOrderDetailItems = [
  { label: 'ID', key: 'id', span: 2 },
  { label: '母订单ID', key: 'parentProjectId', span: 2 },
  { label: '子订单号', key: 'subOrderNo' },
  { label: '子项目名称', key: 'subProjectName' },
  { label: '状态', key: 'status', type: 'status' },
  { label: '文本类型', key: 'fileTypeSecondary' },
  { label: '翻译方向', key: 'languagePair' },
  { label: '优先级', key: 'priority' },
  { label: '客户提供字数', key: 'customerWordCount' },
  { label: '客户统计口径', key: 'customerWordCountType', formatter: formatWordCountType },
  { label: '内部核算字数', key: 'internalWordCount' },
  { label: '内部统计口径', key: 'internalWordCountType', formatter: formatWordCountType },
  { label: '原项目字数（兼容字段）', key: 'wordCount' },
  { label: '客户交稿时间', key: 'customerDeadlineTime' },
  { label: '发客户时间', key: 'sentToClientTime' },
  { label: '客户反馈', key: 'clientFeedback', span: 2 },
  { label: '已分配译员', key: 'assignedTranslators', span: 2, formatter: (value, row) => formatAssignedTranslators(value, row.translatorName) },
  { label: '译员分配时间', key: 'translatorAssignmentTime' },
  { label: '预计统计方式', key: 'expectedTranslatorStatsMethod' },
  { label: '预计译员字数', key: 'expectedTranslatorWordCount' },
  { label: '译员交付进度', key: 'translatorDeliveryProgress' },
  { label: '审校前QC', key: 'preReviewQcProgress' },
  { label: '审核进度（旧字段）', key: 'reviewProgress' },
  { label: '审校1', key: 'review1Progress' },
  { label: '审校2', key: 'review2Progress' },
  { label: '审校后QC', key: 'postReviewQcProgress' },
  { label: '排版进度', key: 'layoutProgress' },
  { label: '整合进度', key: 'consolidationProgress' },
  { label: '网络文件路径', key: 'networkFilePath', span: 2 },
  { label: '备注', key: 'remarks', span: 2 },
  { label: '创建人ID', key: 'createdBy' },
  { label: '创建时间', key: 'createdAt' },
  { label: '更新时间', key: 'updatedAt' }
]
const createEmptyProjectForm = () => ({ id: '', orderNo: '', projectName: '', serviceContent: '', taskType: '', consultationId: '', clientId: '', subClientId: '', clientShortName: '', clientCode: '', customerOrderNo: '', clientManager: '', managerContact: '', fileTypeSecondary: '', projectContractType: '', projectContractStatus: '', quotationRequired: false, quotationStatus: '', quotationPath: '', customerRequirementProfessional: '', customerRequirementSpecial: '', languagePair: '', priority: '', wordCount: 0, customerWordCount: null, customerWordCountType: '', internalWordCount: null, internalWordCountType: '', projectStatus: 'pending_confirmation', projectManagerId: '', projectManagerName: '', customerReceptionTime: '', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', pmConfirmedBy: '', majorProjectManagerConfirmation: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, translatorDeliveryProgress: 0, preReviewQcProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '', referenceFilePathOne: '' })
const createEmptySubOrderForm = () => ({ id: '', parentProjectId: '', subOrderNo: '', subProjectName: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCount: 0, customerWordCount: null, customerWordCountType: '', internalWordCount: null, internalWordCountType: '', customerDeadlineTime: '', sentToClientTime: '', clientFeedback: '', translatorId: '', translatorName: '', assignedTranslators: [], translatorAssignmentTime: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, status: 'pending_confirmation', translatorDeliveryProgress: 0, preReviewQcProgress: 0, reviewProgress: 0, review1Progress: 0, review2Progress: 0, postReviewQcProgress: 0, layoutProgress: 0, consolidationProgress: 0, networkFilePath: '', remarks: '' })
const createBatchForm = () => ({ count: 1, startIndex: 1, subProjectNamePrefix: '', fileTypeSecondary: '', languagePair: '', priority: '', wordCount: 0, customerWordCount: null, customerWordCountType: '', internalWordCount: null, internalWordCountType: '', customerDeadlineTime: '', sentToClientTime: '', translatorId: '', expectedTranslatorStatsMethod: '', expectedTranslatorWordCount: 0, status: 'pending_confirmation' })
const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const subOrderDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const wordCountDrawerVisible = ref(false)
const wordCountDrawerEntity = ref('project')
const dialogTitle = ref('新增项目')
const subOrderDialogTitle = ref('新增子订单')
const formRef = ref(null)
const subOrderFormRef = ref(null)
const batchFormRef = ref(null)
const tableData = ref([])
const currentProjectSubOrders = ref([])
const projectManagerOptions = ref([])
const projectNameManuallyEdited = ref(false)
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const searchForm = reactive({ projectName: '', orderNo: '', clientShortName: '', projectStatus: '' })
const form = reactive(createEmptyProjectForm())
const subOrderForm = reactive(createEmptySubOrderForm())
const batchForm = reactive(createBatchForm())
const wordCountDrawerTarget = computed(() => {
  if (wordCountDrawerEntity.value === 'subOrder') return subOrderForm
  if (wordCountDrawerEntity.value === 'batch') return batchForm
  return form
})
const wordCountDrawerTitle = computed(() => ({
  project: '母订单',
  subOrder: '子订单',
  batch: '批量子订单'
}[wordCountDrawerEntity.value] || '项目'))
const rules = { projectStatus: [{ required: true, message: '请选择状态', trigger: 'change' }] }
const subOrderRules = { subProjectName: [{ required: true, message: '请输入子项目名称', trigger: 'blur' }] }
const batchRules = { count: [{ required: true, message: '请输入生成数量', trigger: 'change' }] }
const NULLABLE_FIELDS = ['serviceContent', 'taskType', 'consultationId', 'clientId', 'subClientId', 'projectManagerId', 'customerOrderNo', 'customerReceptionTime', 'customerDeadlineTime', 'sentToClientTime', 'pmConfirmedBy', 'translatorId', 'translatorAssignmentTime', 'expectedTranslatorStatsMethod', 'customerWordCountType', 'internalWordCountType', 'clientFeedback', 'networkFilePath', 'referenceFilePathOne', 'fileTypeSecondary', 'projectContractType', 'projectContractStatus', 'quotationStatus', 'quotationPath', 'customerRequirementProfessional', 'customerRequirementSpecial', 'languagePair', 'priority', 'remarks', 'subProjectName']
const legacyStatusMap = {
  pending: 'pending_confirmation',
  in_progress: 'confirmed',
  completed: 'sent_to_client',
  terminated: 'cancelled'
}
const normalizeStatus = (status) => legacyStatusMap[status] || status
const getStatusLabel = (status) => projectStatusOptions.find(item => item.value === normalizeStatus(status))?.label || status || '-'
const getStatusType = (status) => ({
  pending_confirmation: 'info',
  confirmed: 'primary',
  organized: 'primary',
  translator_assigned: 'warning',
  sent_to_translator: 'warning',
  translator_returned: 'primary',
  special_checked: 'primary',
  typeset: 'primary',
  special_checked_typeset: 'primary',
  reviewed: 'success',
  sent_to_client: 'success',
  client_feedback: 'success',
  feedback_sent_to_client: 'success',
  cancelled: 'danger',
  partially_cancelled: 'danger',
  paused: 'warning'
}[normalizeStatus(status)] || 'info')
const displayValue = (value) => (value === null || value === undefined || value === '' ? '-' : value)
function formatHierarchy(...values) {
  const normalized = values.filter((value) => String(value || '').trim())
  return normalized.length ? normalized.join(' / ') : '-'
}
function formatProjectQuotation(row = {}) {
  if (!row.quotationRequired) return '无需提供'
  return [row.quotationStatus || '需提供', row.quotationPath].filter(Boolean).join(' / ')
}
function hasWordCount(value) {
  return value !== null && value !== undefined && value !== ''
}
function formatWordCountType(value) {
  return wordCountTypeOptions.find((item) => item.value === value)?.label || value || '未选口径'
}
function formatWordCountValue(value, type) {
  if (!hasWordCount(value)) return '未填写'
  return `${Number(value).toLocaleString('zh-CN')} · ${formatWordCountType(type)}`
}
function formatWordCountSummary(target = {}) {
  if (hasWordCount(target.internalWordCount)) {
    return `内部：${formatWordCountValue(target.internalWordCount, target.internalWordCountType)}`
  }
  if (hasWordCount(target.customerWordCount)) {
    return `客户：${formatWordCountValue(target.customerWordCount, target.customerWordCountType)}`
  }
  if (hasWordCount(target.wordCount)) {
    return `历史：${Number(target.wordCount).toLocaleString('zh-CN')}`
  }
  return '尚未填写'
}
function syncLegacyWordCount(target) {
  if (!target) return
  if (hasWordCount(target.internalWordCount)) {
    target.wordCount = target.internalWordCount
  } else if (hasWordCount(target.customerWordCount)) {
    target.wordCount = target.customerWordCount
  }
}
function openWordCountDrawer(entity) {
  wordCountDrawerEntity.value = entity
  wordCountDrawerVisible.value = true
}
function closeWordCountDrawer() {
  syncLegacyWordCount(wordCountDrawerTarget.value)
  wordCountDrawerVisible.value = false
}
const formatAssignedTranslators = (items, legacyName = '') => {
  if (Array.isArray(items) && items.length) {
    return items
      .map((item) => {
        const name = item.translatorName || item.translator_name || ''
        const scope = item.translationScope || item.translation_scope || ''
        return scope ? `${name}（${scope}）` : name
      })
      .filter(Boolean)
      .join('、')
  }
  return legacyName || '-'
}
const pad = (value) => String(value).padStart(2, '0')
const syncProjectName = ({ force = false } = {}) => {
  if (projectNameManuallyEdited.value && !force) return
  form.projectName = buildAutoProjectName(form.clientShortName, currentProjectSubOrders.value.length)
}
const handleProjectNameInput = () => {
  projectNameManuallyEdited.value = true
}
const clampProgress = (value) => Math.max(0, Math.min(100, Number(value) || 0))
const parseProgressValue = (value) => {
  if (value === null || value === undefined || value === '') return 0
  if (typeof value === 'number') return clampProgress(value)
  const matched = String(value).match(/-?\d+/)
  return clampProgress(matched ? Number(matched[0]) : 0)
}
const normalizeProgressValue = (value) => `${clampProgress(value)}%`
const formatProgressDisplay = (value) => `${clampProgress(value)}%`
const normalizeProject = (project) => ({ ...project, subOrders: Array.isArray(project.subOrders) ? [...project.subOrders].sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : [] })
const getSubOrderCount = (row) => Array.isArray(row?.subOrders) ? row.subOrders.length : 0
const hasMoreSubOrders = (row) => getSubOrderCount(row) > SUB_ORDER_PREVIEW_LIMIT
const getVisibleSubOrders = (row) => (Array.isArray(row?.subOrders) ? row.subOrders.slice(0, SUB_ORDER_PREVIEW_LIMIT) : [])
const applyPagination = () => { fetchData() }
const cleanPayload = (payload) => {
  const result = { ...payload }
  NULLABLE_FIELDS.forEach((key) => {
    if (result[key] === '') result[key] = null
  })
  progressFieldSet.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(result, key)) {
      result[key] = normalizeProgressValue(result[key])
    }
  })
  delete result.translatorName
  delete result.assignedTranslators
  delete result.clientManager
  delete result.managerContact
  delete result.projectManagerName
  result.quotationRequired = Boolean(result.quotationRequired)
  if (!result.quotationRequired) {
    result.quotationStatus = null
    result.quotationPath = null
  }
  if (result.wordCount === null || result.wordCount === undefined) result.wordCount = 0
  if (result.expectedTranslatorWordCount === null || result.expectedTranslatorWordCount === undefined) {
    result.expectedTranslatorWordCount = 0
  }
  return result
}
const assignReactive = (target, defaultsFactory, values = {}) => {
  const defaults = defaultsFactory()
  Object.keys(defaults).forEach((key) => {
    if (progressFieldSet.has(key)) {
      target[key] = parseProgressValue(values[key] ?? defaults[key])
    } else if (key === 'projectStatus' || key === 'status') {
      target[key] = normalizeStatus(values[key] ?? defaults[key])
    } else {
      target[key] = values[key] ?? defaults[key]
    }
  })
}
const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      project_name: searchForm.projectName || undefined,
      order_no: searchForm.orderNo || undefined,
      client_short_name: searchForm.clientShortName || undefined,
      project_status: searchForm.projectStatus || undefined
    }
    const [response, countResponse] = await Promise.all([
      getProjects(params),
      getProjectCount({
        project_name: params.project_name,
        order_no: params.order_no,
        client_short_name: params.client_short_name,
        project_status: params.project_status
      })
    ])
    tableData.value = (Array.isArray(response) ? response : []).map(normalizeProject)
    pagination.total = countResponse?.total || tableData.value.length
  } catch (error) {
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || error.message || 'Failed to load projects')
  } finally {
    loading.value = false
  }
}
const refreshProjectSubOrders = async (projectId) => {
  if (!projectId) return
  const response = await getSubOrdersByProject(projectId)
  const normalized = Array.isArray(response) ? response.sort((a, b) => (a.subOrderNo || '').localeCompare(b.subOrderNo || '')) : []
  currentProjectSubOrders.value = normalized
  tableData.value = tableData.value.map((item) => item.id === projectId ? { ...item, subOrders: normalized } : item)
  if (form.id === projectId) syncProjectName()
}

const loadProjectManagerOptions = async () => {
  if (projectManagerOptions.value.length) return
  try {
    projectManagerOptions.value = await getProjectManagerCandidatesAPI({ include_current: true })
  } catch {
    projectManagerOptions.value = []
  }
}

const fetchClientSuggestions = async (queryString, callback) => {
  const keyword = String(queryString || '').trim()
  try {
    const clients = await getClients({
      skip: 0,
      limit: 20,
      client_short_name: keyword || undefined,
      frequent_first: true
    })
    const options = (Array.isArray(clients) ? clients : []).flatMap((client) => {
      const parentOption = {
        id: client.id,
        parent_client_id: client.id,
        sub_client_id: null,
        client_short_name: client.client_short_name || '',
        client_code: client.client_code || '',
        client_name: client.client_name || '',
        client_manager: client.client_manager || '',
        manager_contact: client.manager_contact || '',
        parent_client_short_name: ''
      }
      const subClientOptions = (Array.isArray(client.sub_clients) ? client.sub_clients : []).map((subClient) => ({
        id: subClient.id,
        parent_client_id: client.id,
        sub_client_id: subClient.id,
        client_short_name: subClient.client_short_name || '',
        client_code: subClient.sub_client_code || '',
        client_name: subClient.client_name || '',
        client_manager: subClient.client_manager || client.client_manager || '',
        manager_contact: subClient.manager_contact || client.manager_contact || '',
        parent_client_short_name: client.client_short_name || ''
      }))
      return [parentOption, ...subClientOptions]
    })
    callback(options)
  } catch {
    callback([])
  }
}
const handleClientSelect = (client) => {
  form.clientId = client.parent_client_id || client.id || ''
  form.subClientId = client.sub_client_id || ''
  form.clientShortName = client.client_short_name || ''
  form.clientCode = client.client_code || ''
  form.clientManager = client.client_manager || ''
  form.managerContact = client.manager_contact || ''
  projectNameManuallyEdited.value = false
  syncProjectName({ force: true })
}
const handleClientShortNameInput = () => {
  form.clientId = ''
  form.subClientId = ''
  form.clientCode = ''
  form.clientManager = ''
  form.managerContact = ''
  form.projectName = ''
  projectNameManuallyEdited.value = false
}
const clearSelectedClient = () => {
  form.clientId = ''
  form.subClientId = ''
  form.clientShortName = ''
  form.clientCode = ''
  form.clientManager = ''
  form.managerContact = ''
  form.projectName = ''
  projectNameManuallyEdited.value = false
}

const getOriginalPath = async (row) => {
  if (!row?.id) return ''
  const files = await getProjectFilesByProject(row.id, { skip: 0, limit: 1 })
  return Array.isArray(files) ? String(files[0]?.storage_path || '').trim() : ''
}
const toOpenPathHref = (path) => {
  const stripped = path.replace(/^\\\\/, '')
  return `openpath://${encodeURIComponent(stripped).replace(/%5C/gi, '\\').replace(/%2F/gi, '/')}`
}
const openOriginalPath = async (row) => {
  try {
    const path = await getOriginalPath(row)
    if (!path) {
      ElMessage.warning('该订单暂无原文路径')
      return
    }
    window.location.href = toOpenPathHref(path)
  } catch (error) {
    ElMessage.error(error.detail || error.message || '获取原文路径失败')
  }
}
const copyOriginalPath = async (row) => {
  try {
    const path = await getOriginalPath(row)
    if (!path) {
      ElMessage.warning('该订单暂无原文路径')
      return
    }
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch (error) {
    ElMessage.error(error.detail || error.message || '复制失败，请稍后重试')
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const resetSearch = () => { searchForm.projectName = ''; searchForm.orderNo = ''; searchForm.clientShortName = ''; searchForm.projectStatus = ''; handleSearch() }
const clearSearch = () => {
  searchForm.projectName = ''
  searchForm.orderNo = ''
  searchForm.clientShortName = ''
  searchForm.projectStatus = ''
}
const resetProjectForm = () => {
  assignReactive(form, createEmptyProjectForm)
  projectNameManuallyEdited.value = false
  projectDialogTab.value = 'basic'
  projectBasicExpandedSections.value = ['project', 'business', 'execution']
}
const resetSubOrderForm = () => { assignReactive(subOrderForm, createEmptySubOrderForm); subOrderFormRef.value?.clearValidate(); subOrderDialogTab.value = 'basic' }
const resetBatchForm = () => { Object.assign(batchForm, createBatchForm()); batchFormRef.value?.clearValidate() }
const generateOrderNo = async () => { try { return await getNextOrderNo() } catch { const now = new Date(); return `TP-${String(now.getFullYear()).slice(-2)}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${String(Math.floor(Math.random() * 999) + 1).padStart(3, '0')}` } }
const goToSubOrderManagement = (project) => {
  const projectId = project.id || form.id
  if (!projectId) return
  router.push({ name: 'TranslationSubOrderManagement', params: { projectId }, query: { orderNo: project.orderNo || form.orderNo || '', projectName: project.projectName || form.projectName || '' } })
}
const handleAdd = async () => {
  dialogTitle.value = '新增项目'
  resetProjectForm()
  currentProjectSubOrders.value = []
  await loadProjectManagerOptions()
  form.orderNo = await generateOrderNo()
  dialogVisible.value = true
}
const handleEdit = async (row) => {
  dialogTitle.value = '编辑项目详情'
  await loadProjectManagerOptions()
  assignReactive(form, createEmptyProjectForm, row)
  currentProjectSubOrders.value = Array.isArray(row.subOrders) ? [...row.subOrders] : []
  projectNameManuallyEdited.value = Boolean(form.projectName) && !isAutoProjectName(form.projectName, form.clientShortName)
  syncProjectName()
  projectDialogTab.value = 'basic'
  projectBasicExpandedSections.value = ['project', 'business', 'execution']
  dialogVisible.value = true
  if (row.id) {
    try {
      await refreshProjectSubOrders(row.id)
    } catch (error) {
      ElMessage.error(error.detail || error.message || '加载子订单失败')
    }
  }
}
const handleFiles = async (row) => { await handleEdit(row); projectDialogTab.value = 'files' }
const handleProjectFileStatusChange = (status) => {
  if (!status) return
  form.projectStatus = normalizeStatus(status)
  const row = tableData.value.find((item) => item.id === form.id)
  if (row) row.projectStatus = form.projectStatus
}
const handleDeleteProject = async (row) => { try { await ElMessageBox.confirm(`确认删除母订单 ${row.orderNo} 吗？`, '提示', { type: 'warning' }); await deleteProject(row.id); ElMessage.success('删除成功'); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '删除失败') } }
const handleSubmit = async () => {
  if (!formRef.value || submitLoading.value) return
  syncProjectName()
  const valid = await formRef.value.validate().catch((invalidFields) => {
    if (invalidFields?.projectStatus) {
      projectDialogTab.value = 'basic'
      if (!projectBasicExpandedSections.value.includes('execution')) {
        projectBasicExpandedSections.value = [...projectBasicExpandedSections.value, 'execution']
      }
    }
    return false
  })
  if (!valid) return

  submitLoading.value = true
  try {
    syncLegacyWordCount(form)
    const payload = cleanPayload({ ...form })
    const isCreate = dialogTitle.value === '新增项目'
    if (isCreate) {
      await createProject(payload)
      // 新项目按创建时间倒序展示；回到第一页并清除可能隐藏新项目的旧筛选条件。
      pagination.page = 1
      clearSearch()
      ElMessage.success('创建成功')
    } else {
      await updateProject(payload.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false

    try {
      await fetchData()
    } catch {
      // fetchData 内部已处理错误；保存结果不应被误报为失败。
    }
  } catch (error) {
    ElMessage.error(error.detail || error.message || '保存失败')
  } finally {
    submitLoading.value = false
  }
}
const onProjectDialogClosed = () => { resetProjectForm(); resetSubOrderForm(); resetBatchForm(); currentProjectSubOrders.value = [] }
const createSubOrderDefaultsFromProject = () => ({ fileTypeSecondary: form.fileTypeSecondary, languagePair: form.languagePair, priority: form.priority, wordCount: form.wordCount, customerWordCount: form.customerWordCount, customerWordCountType: form.customerWordCountType, internalWordCount: form.internalWordCount, internalWordCountType: form.internalWordCountType, customerDeadlineTime: form.customerDeadlineTime, sentToClientTime: form.sentToClientTime, translatorId: form.translatorId, translatorAssignmentTime: form.translatorAssignmentTime, expectedTranslatorStatsMethod: form.expectedTranslatorStatsMethod, expectedTranslatorWordCount: form.expectedTranslatorWordCount, status: form.projectStatus || 'pending_confirmation', translatorDeliveryProgress: form.translatorDeliveryProgress, preReviewQcProgress: form.preReviewQcProgress, review1Progress: form.review1Progress, review2Progress: form.review2Progress, postReviewQcProgress: form.postReviewQcProgress, layoutProgress: form.layoutProgress, consolidationProgress: form.consolidationProgress, networkFilePath: form.networkFilePath, clientFeedback: form.clientFeedback })
const openCreateSubOrderDialog = () => { resetSubOrderForm(); subOrderDialogTitle.value = '新增子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...createSubOrderDefaultsFromProject(), parentProjectId: form.id }); subOrderDialogVisible.value = true }
const handleEditSubOrder = (row) => { resetSubOrderForm(); subOrderDialogTitle.value = '编辑子订单'; assignReactive(subOrderForm, createEmptySubOrderForm, { ...row, parentProjectId: row.parentProjectId || form.id }); subOrderDialogVisible.value = true }
const openProjectEditorForSubOrder = async (projectRow, subOrderRow) => { await handleEdit(projectRow); await nextTick(); handleEditSubOrder(subOrderRow) }
const buildSubOrderPayload = (source) => {
  syncLegacyWordCount(source)
  return cleanPayload({ parentProjectId: form.id, subProjectName: source.subProjectName || '', fileTypeSecondary: source.fileTypeSecondary || '', languagePair: source.languagePair || '', priority: source.priority || '', wordCount: source.wordCount ?? 0, customerWordCount: source.customerWordCount, customerWordCountType: source.customerWordCountType || '', internalWordCount: source.internalWordCount, internalWordCountType: source.internalWordCountType || '', customerDeadlineTime: source.customerDeadlineTime || '', sentToClientTime: source.sentToClientTime || '', clientFeedback: source.clientFeedback || '', translatorId: source.translatorId || '', translatorAssignmentTime: source.translatorAssignmentTime || '', expectedTranslatorStatsMethod: source.expectedTranslatorStatsMethod || '', expectedTranslatorWordCount: source.expectedTranslatorWordCount ?? 0, status: source.status || 'pending', translatorDeliveryProgress: source.translatorDeliveryProgress ?? 0, preReviewQcProgress: source.preReviewQcProgress ?? 0, reviewProgress: source.reviewProgress ?? 0, review1Progress: source.review1Progress ?? 0, review2Progress: source.review2Progress ?? 0, postReviewQcProgress: source.postReviewQcProgress ?? 0, layoutProgress: source.layoutProgress ?? 0, consolidationProgress: source.consolidationProgress ?? 0, networkFilePath: source.networkFilePath || '', remarks: source.remarks || '' })
}
const handleSubmitSubOrder = async () => { if (!subOrderFormRef.value) return; const valid = await subOrderFormRef.value.validate().catch(() => false); if (!valid) return; try { const payload = buildSubOrderPayload(subOrderForm); if (subOrderDialogTitle.value === '新增子订单') { await createSubOrder(payload); ElMessage.success('子订单创建成功') } else { await updateSubOrder(subOrderForm.id, payload); ElMessage.success('子订单更新成功') } subOrderDialogVisible.value = false; await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '子订单保存失败') } }
const handleDeleteSubOrder = async (row) => { try { await ElMessageBox.confirm(`确认删除子订单 ${row.subOrderNo} 吗？`, '提示', { type: 'warning' }); await deleteSubOrder(row.id); ElMessage.success('子订单删除成功'); if (form.id && row.parentProjectId === form.id) await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || error.message || '子订单删除失败') } }
const openBatchDialog = () => { resetBatchForm(); Object.assign(batchForm, { ...createBatchForm(), ...createSubOrderDefaultsFromProject(), subProjectNamePrefix: form.projectName ? `${form.projectName}-子订单` : '' }); batchDialogVisible.value = true }
const createBatchSubProjectName = (index) => { const prefix = batchForm.subProjectNamePrefix || (form.projectName ? `${form.projectName}-子订单` : '子订单'); return `${prefix}${String(index).padStart(2, '0')}` }
const handleBatchCreateSubOrders = async () => { if (!batchFormRef.value) return; const valid = await batchFormRef.value.validate().catch(() => false); if (!valid) return; try { for (let offset = 0; offset < batchForm.count; offset += 1) { const sequence = batchForm.startIndex + offset; const payload = buildSubOrderPayload({ ...batchForm, subProjectName: createBatchSubProjectName(sequence), remarks: '' }); await createSubOrder(payload) } batchDialogVisible.value = false; ElMessage.success(`已批量创建 ${batchForm.count} 条子订单`); await refreshProjectSubOrders(form.id); await fetchData() } catch (error) { ElMessage.error(error.detail || error.message || '批量新增失败') } }
const getProjectRowClassName = ({ row }) => (getSubOrderCount(row) ? '' : 'no-expand-row')
const detailGroups = [
  {
    title: '基本信息',
    keys: ['id', 'orderNo', 'subOrderNo', 'projectName', 'subProjectName', 'parentProjectId', 'serviceContent', 'taskType', 'projectStatus', 'status', 'priority'],
  },
  {
    title: '客户与文件',
    keys: ['consultationId', 'clientId', 'subClientId', 'clientShortName', 'clientCode', 'customerOrderNo', 'clientManager', 'managerContact', 'fileTypeSecondary', 'projectFileName', 'projectFileTranslationDomainLevel1', 'projectFileTypeLevel1', 'projectFileFormat', 'projectFileAttributeLevel1', 'projectFileDifficulty', 'projectContractType', 'quotationRequired', 'customerRequirementProfessional', 'customerRequirementSpecial', 'languagePair', 'networkFilePath', 'referenceFilePathOne'],
  },
  {
    title: '字数与时间',
    keys: ['customerWordCount', 'customerWordCountType', 'internalWordCount', 'internalWordCountType', 'wordCount', 'customerReceptionTime', 'customerDeadlineTime', 'sentToClientTime', 'clientFeedback'],
  },
  {
    title: '执行进度',
    keys: ['pmConfirmedBy', 'majorProjectManagerConfirmation', 'assignedTranslators', 'translatorAssignmentTime', 'expectedTranslatorStatsMethod', 'expectedTranslatorWordCount', 'translatorDeliveryProgress', 'preReviewQcProgress', 'reviewProgress', 'review1Progress', 'review2Progress', 'postReviewQcProgress', 'layoutProgress', 'consolidationProgress', 'remarks'],
  },
  {
    title: '系统信息',
    keys: ['createdBy', 'createdAt', 'updatedAt'],
  },
]

const DetailPopover = defineComponent({
  name: 'DetailDrawer',
  props: {
    row: { type: Object, required: true },
    title: { type: String, default: '详情' },
    items: { type: Array, default: () => [] },
  },
  setup(props) {
    const visible = ref(false)
    const showAllFields = ref(false)
    const hasValue = (item) => {
      const value = props.row[item.key]
      if (Array.isArray(value)) return value.length > 0
      return value !== null && value !== undefined && value !== ''
    }
    const hiddenFieldCount = computed(() => props.items.filter((item) => !hasValue(item)).length)
    const groupedItems = computed(() => {
      const knownKeys = new Set(detailGroups.flatMap((group) => group.keys))
      const visibleItems = showAllFields.value ? props.items : props.items.filter(hasValue)
      const groups = detailGroups
        .map((group) => ({
          title: group.title,
          items: visibleItems.filter((item) => group.keys.includes(item.key)),
        }))
        .filter((group) => group.items.length)
      const remainingItems = visibleItems.filter((item) => !knownKeys.has(item.key))
      if (remainingItems.length) groups.splice(groups.length - 1, 0, { title: '其他信息', items: remainingItems })
      return groups
    })
    const renderValue = (item) => {
      if (item.type === 'status') {
        return h(ElTag, { type: getStatusType(props.row[item.key]) }, () => getStatusLabel(props.row[item.key]))
      }
      const value = item.formatter
        ? item.formatter(props.row[item.key], props.row)
        : displayValue(props.row[item.key])
      return h('span', { class: 'detail-value' }, value)
    }

    return () => [
      h(ElButton, {
        type: 'primary',
        size: 'small',
        link: true,
        onClick: () => { visible.value = true },
      }, () => '查看详情'),
      h(ElDrawer, {
        modelValue: visible.value,
        'onUpdate:modelValue': (value) => { visible.value = value },
        size: 'min(760px, 100vw)',
        direction: 'rtl',
        appendToBody: true,
        destroyOnClose: true,
        class: 'detail-drawer',
        onClosed: () => { showAllFields.value = false },
      }, {
        header: () => h('div', { class: 'detail-drawer__header' }, [
          h('div', [
            h('div', { class: 'detail-drawer__title' }, props.title),
            h('div', { class: 'detail-drawer__subtitle' }, props.row.orderNo || props.row.subOrderNo || props.row.projectName || props.row.subProjectName || '未命名记录'),
          ]),
          props.row.projectStatus || props.row.status
            ? h(ElTag, { type: getStatusType(props.row.projectStatus || props.row.status) }, () => getStatusLabel(props.row.projectStatus || props.row.status))
            : null,
        ]),
        default: () => h('div', { class: 'detail-drawer__content' }, [
          hiddenFieldCount.value
            ? h('div', { class: 'detail-drawer__toolbar' }, [
              h('span', { class: 'detail-drawer__hint' },
                showAllFields.value ? '当前显示全部字段' : `已隐藏 ${hiddenFieldCount.value} 个空字段`
              ),
              h(ElButton, {
                size: 'small',
                onClick: () => { showAllFields.value = !showAllFields.value },
              }, () => showAllFields.value ? '隐藏空字段' : '显示全部字段'),
            ])
            : null,
          ...groupedItems.value.map((group) => h('section', { key: group.title, class: 'detail-section' }, [
            h('h3', { class: 'detail-section__title' }, group.title),
            h(ElDescriptions, { column: 2, border: true, size: 'small' }, () =>
              group.items.map((item) => h(ElDescriptionsItem, {
                key: item.key,
                label: item.label,
                span: item.span || 1,
              }, () => renderValue(item)))
            ),
          ])),
        ]),
      }),
    ]
  },
})
onMounted(fetchData)
</script>

<style scoped>
.search-form { margin-bottom: 20px; }
.card-header,
.section-header,
.sub-order-panel__header { display: flex; align-items: center; justify-content: space-between; }
.sub-order-panel__meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.order-no-actions { display: flex; align-items: center; gap: 6px; }
.order-no-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.order-no-btns { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.order-no-btns :deep(.el-button) { margin-left: 0; padding: 0; height: 18px; line-height: 18px; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.client-suggestion { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.client-suggestion__meta { color: var(--el-text-color-secondary); font-size: 12px; }
.auto-name-field { width: 100%; }
.auto-name-field__hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.word-count-summary { width: 100%; min-height: 32px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 10px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-fill-color-lighter); color: var(--el-text-color-regular); }
.word-count-dialog__alert { margin-bottom: 16px; }
.word-count-dialog .el-dialog__body { max-height: 60vh; overflow-y: auto; }
.excel-word-grid { overflow-x: auto; border-top: 1px solid var(--el-border-color); border-left: 1px solid var(--el-border-color); }
.excel-word-grid table { width: 100%; min-width: 680px; table-layout: fixed; border-collapse: collapse; }
.excel-word-grid__source { width: 155px; }
.excel-word-grid__count { width: 165px; }
.excel-word-grid__method { width: 235px; }
.excel-word-grid__usage { width: auto; }
.excel-word-grid th,
.excel-word-grid td { height: 46px; padding: 0; border-right: 1px solid var(--el-border-color); border-bottom: 1px solid var(--el-border-color); vertical-align: middle; }
.excel-word-grid thead th { padding: 10px 12px; background: var(--el-fill-color-dark); color: var(--el-text-color-primary); text-align: left; font-size: 13px; font-weight: 600; }
.excel-word-grid tbody th { padding: 8px 12px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); text-align: left; font-weight: 500; }
.excel-word-grid__text { padding: 8px 12px !important; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.excel-word-grid__compatibility th,
.excel-word-grid__compatibility td { background: var(--el-fill-color-lighter); }
.excel-word-grid__editor :deep(.el-input-number),
.excel-word-grid__editor :deep(.el-select),
.excel-word-grid__editor :deep(.el-input) { width: 100%; height: 45px; }
.excel-word-grid__editor :deep(.el-input__wrapper),
.excel-word-grid__editor :deep(.el-select__wrapper) { min-height: 45px; border-radius: 0; box-shadow: none; }
.excel-word-grid__editor :deep(.el-input-number .el-input__wrapper) { padding-left: 12px; }
.excel-word-grid__editor :deep(.el-input-number__increase),
.excel-word-grid__editor :deep(.el-input-number__decrease) { border-radius: 0; }
.excel-word-grid__editor:focus-within { outline: 2px solid var(--el-color-primary); outline-offset: -2px; }
.editor-body { max-height: 68vh; overflow-y: auto; padding-right: 4px; }
.editor-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.form-section { padding: 4px 2px 12px; }
.project-basic-collapse__title { display: flex; align-items: center; min-width: 0; gap: 12px; color: var(--el-text-color-primary); font-weight: 600; }
.project-basic-collapse__hint { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.project-basic-collapse__body { padding: 16px 12px 0; }
.project-basic-collapse :deep(.el-collapse-item__header) { height: 48px; padding: 0 12px; background: var(--el-fill-color-lighter); }
.project-basic-collapse :deep(.el-collapse-item__content) { padding-bottom: 8px; }
.progress-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.progress-card { padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: var(--radius-lg); background: var(--color-surface); }
.progress-card__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-size: 14px; }
.section-title { margin: 12px 0; font-size: 15px; font-weight: 600; }
.section-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.sub-order-panel { padding: 12px 24px 20px; background: #fafafa; }
.sub-order-panel__header { margin-bottom: 12px; }
.sub-order-alert { margin-bottom: 12px; }
.detail-drawer__header { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-right: 12px; }
.detail-drawer__title { color: var(--color-text-primary); font-size: 18px; font-weight: 600; }
.detail-drawer__subtitle { margin-top: 4px; color: var(--color-text-muted); font-size: 13px; }
.detail-drawer__content { display: flex; flex-direction: column; gap: 20px; padding-bottom: 12px; }
.detail-drawer__toolbar { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: -20px -20px 0; padding: 12px 20px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.detail-drawer__hint { color: var(--color-text-muted); font-size: 13px; }
.detail-section__title { margin: 0 0 10px; padding-left: 10px; border-left: 3px solid var(--color-primary); color: var(--color-text-primary); font-size: 15px; font-weight: 600; }
.detail-section :deep(.el-descriptions__label) { width: 128px; color: var(--color-text-secondary); white-space: nowrap; }
.detail-value { color: var(--color-text-secondary); word-break: break-word; overflow-wrap: anywhere; }
.el-alert { margin-top: 16px; }
:deep(.no-expand-row .el-table__expand-icon) { visibility: hidden; pointer-events: none; }

@media (max-width: 640px) {
  .detail-drawer__header { align-items: flex-start; }
  .detail-section :deep(.el-descriptions__label) { width: 96px; white-space: normal; }
}
</style>
