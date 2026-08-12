<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>招聘项目详情</span>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
          <el-button v-if="canWrite" type="primary" @click="openAdd">新增招聘项目</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键字"><el-input v-model="searchForm.keyword" clearable placeholder="项目、客户、职位或属地" @input="handleTextSearch" @keyup.enter="handleSearch" /></el-form-item>
      <el-form-item label="项目状态"><el-select v-model="searchForm.projectStatus" clearable placeholder="全部" style="width: 180px" @change="handleSearch"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button><el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="advanced-filter-popover">
          <template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
          <div class="advanced-content">
            <el-form :model="searchForm" label-width="110px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><el-select v-model="searchForm.clientManagerId" clearable filterable style="width:100%" @change="handleSearch"><el-option v-for="user in activeUsers" :key="user.id" :label="userLabel(user)" :value="user.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="履职日期范围"><el-date-picker v-model="searchForm.employmentRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" @change="handleSearch" /></el-form-item></el-col>
              </el-row>
            </el-form>
            <div class="advanced-footer"><el-button link @click="clearAdvanced">清空高级条件</el-button><el-button type="primary" @click="advancedVisible=false">关闭</el-button></div>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" border row-key="id">
      <el-table-column label="序号" width="64" align="center"><template #default="{ $index }">{{ (pagination.page - 1) * pagination.limit + $index + 1 }}</template></el-table-column>
      <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.minWidth" :show-overflow-tooltip="column.tooltip !== false">
        <template #default="{ row }">
          <div v-if="column.key === 'orderNo'" class="order-cell">
            <BusinessDetailPopover :row="row" title="招聘项目详情" :items="detailItems" :status-label="statusLabel" :status-type="statusType">
              <template #reference><el-button type="primary" link @click.stop>{{ row.orderNo }}</el-button></template>
            </BusinessDetailPopover>
            <el-button type="primary" link title="打开项目路径" @click.stop="openPath(row.projectPath)">📂</el-button>
            <el-button type="primary" link title="复制项目路径" @click.stop="copyPath(row.projectPath)">⧉</el-button>
          </div>
          <el-button v-else-if="column.key === 'projectName'" type="primary" link class="wrap-link" @click="openProgress(row)">{{ row.projectName || '待生成' }}</el-button>
          <el-popover v-else-if="column.key === 'jobDescription'" trigger="click" placement="left" :width="560">
            <template #reference><el-button type="primary" link class="description-preview">{{ row.jobDescription || '-' }}</el-button></template>
            <div class="long-text-detail">{{ row.jobDescription || '-' }}</div>
          </el-popover>
          <el-popover v-else-if="column.key === 'clientShortName'" trigger="click" placement="left" :width="420">
            <template #reference><el-button type="primary" link>{{ row.clientShortName || '-' }}</el-button></template>
            <el-descriptions title="客户关联信息" :column="1" border size="small">
              <el-descriptions-item label="子客户/联系人">{{ displayValue(row.contactName) }}</el-descriptions-item>
              <el-descriptions-item label="客户单号/项目标识">{{ displayValue(row.customerOrderNo) }}</el-descriptions-item>
            </el-descriptions>
          </el-popover>
          <el-tag v-else-if="column.key === 'projectStatus'" :type="statusType(row.projectStatus)">{{ statusLabel(row.projectStatus) }}</el-tag>
          <el-button v-else-if="column.key === 'candidateCount'" type="primary" link @click="openCandidates(row)">{{ row.candidateCount || 0 }} 人</el-button>
          <span v-else-if="column.key === 'headcount'">{{ headcountText(row) }}</span>
          <span v-else-if="column.key === 'languageSummary'">{{ languageText(row) }}</span>
          <span v-else-if="column.key === 'employmentPeriod'">{{ periodText(row) }}</span>
          <span v-else-if="column.key === 'targetOnboard'">{{ row.targetOnboardType === 'anytime' ? '随时' : formatDate(row.targetOnboardDate) }}</span>
          <span v-else-if="column.key === 'serviceFee'">{{ feeText(row) }}</span>
          <span v-else-if="dateTimeColumnKeys.has(column.key)">{{ formatDateTime(row[column.key]) }}</span>
          <span v-else>{{ displayValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center"><template #default="{ row }"><TableActionButton v-if="canWrite" action="edit" @click="openEdit(row)" /><TableActionButton v-if="canWrite" action="delete" @click="removeProject(row)" /></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @current-change="fetchData" @size-change="handleSizeChange" />

    <el-dialog v-model="editorVisible" :title="editorTitle" width="min(960px, calc(100vw - 32px))" top="5vh" class="recruitment-editor" @closed="resetForm">
      <div ref="editorBodyRef" class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="125px">
          <div class="form-section"><h3>项目与职位</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input :model-value="form.orderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="项目状态" prop="projectStatus"><el-select v-model="form.projectStatus" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16"><el-col :span="24"><el-form-item label="项目名称"><div class="name-field"><el-input v-model="form.projectName" /><el-button :loading="nameLoading" @click="generateName">生成项目名称</el-button></div></el-form-item></el-col></el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="职位名称/类型" prop="positionTitle"><el-input v-model="form.positionTitle" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="招聘人数" prop="headcountMin"><div class="number-range"><el-input-number v-model="form.headcountMin" :min="0" controls-position="right" /><span>至</span><el-input-number v-model="form.headcountMax" :min="form.headcountMin || 0" controls-position="right" /></div></el-form-item></el-col>
            </el-row>
            <el-form-item label="职位描述"><el-input v-model="form.jobDescription" type="textarea" :rows="5" /></el-form-item>
          </div>

          <div class="form-section"><h3>客户信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户"><el-select v-model="form.clientSelection" filterable clearable style="width:100%" @change="selectClient"><el-option v-for="item in clientOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="子客户/联系人"><el-input v-model="form.contactName" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户简称"><el-input v-model="form.clientShortName" readonly placeholder="选择客户后自动带出" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户编号"><el-input v-model="form.clientCode" readonly placeholder="选择客户后自动带出" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户全称"><el-input v-model="form.clientName" readonly placeholder="选择客户后自动带出" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户领域"><el-input v-model="form.clientDomain" readonly placeholder="选择客户后自动带出" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户单号/项目标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><el-select v-model="form.clientManagerId" filterable clearable style="width:100%"><el-option v-for="user in managerUserOptions" :key="user.id" :label="userOptionLabel(user)" :value="user.id" :disabled="!user.is_active" /></el-select></el-form-item></el-col>
            </el-row>
          </div>

          <div class="form-section"><h3>招聘要求</h3>
            <el-form-item label="外语/翻译方向"><RecruitmentLanguageDirections v-model="form.languageDirections" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="拟履职周期" prop="employmentRange"><el-date-picker v-model="form.employmentRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="任职工作属地" prop="workLocation"><el-input v-model="form.workLocation" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="拟入职时间"><el-radio-group v-model="form.targetOnboardType"><el-radio value="date">具体日期</el-radio><el-radio value="anytime">随时</el-radio></el-radio-group></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="拟入职日期"><el-date-picker v-model="form.targetOnboardDate" value-format="YYYY-MM-DD" :disabled="form.targetOnboardType==='anytime'" style="width:100%" /></el-form-item></el-col>
            </el-row>
          </div>

          <div class="form-section"><h3>费用与扩展信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="费用模式"><el-select v-model="form.serviceFeeType" clearable style="width:100%"><el-option label="固定金额" value="fixed" /><el-option label="年薪比例" value="annual_salary_rate" /><el-option label="其他" value="other" /></el-select></el-form-item></el-col>
              <el-col v-if="form.serviceFeeType==='fixed'" :xs="24" :md="8"><el-form-item label="币种/金额"><div class="money-field"><el-select v-model="form.serviceFeeCurrency"><el-option label="人民币" value="CNY" /><el-option label="美元" value="USD" /><el-option label="港币" value="HKD" /></el-select><el-input-number v-model="form.serviceFeeAmount" :min="0" :precision="2" /></div></el-form-item></el-col>
              <el-col v-if="form.serviceFeeType==='annual_salary_rate'" :xs="24" :md="8"><el-form-item label="年薪比例"><el-input-number v-model="form.serviceFeeRate" :min="0" :max="100" :precision="2" /><span class="suffix">%</span></el-form-item></el-col>
            </el-row>
            <el-form-item label="费用说明"><el-input v-model="form.serviceFeeNote" /></el-form-item>
            <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="客户咨询时间"><el-date-picker v-model="form.customerConsultationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="客户确认时间"><el-date-picker v-model="form.customerConfirmationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
            <el-form-item label="项目路径"><el-input v-model="form.projectPath" /></el-form-item>
            <el-form-item label="报价单路径"><el-input v-model="form.quotationPath" /></el-form-item>
            <el-form-item label="合同路径"><el-input v-model="form.contractPath" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="3" /></el-form-item>
            <el-form-item label="邮件主题预览"><el-input v-model="form.emailSubjectPreview" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="发圈请求"><el-input v-model="form.socialPostRequest" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="资源请求"><el-input v-model="form.resourceRequest" type="textarea" :rows="2" /></el-form-item>
          </div>

          <div v-if="form.id" class="form-section candidate-section">
            <div class="section-heading">
              <h3>简历人选管理</h3>
              <div class="candidate-heading-actions">
                <span>共 {{ candidateRows.length }} 人</span>
                <el-button type="primary" size="small" @click="openCandidateEditor()">新增候选人</el-button>
              </div>
            </div>
            <RecruitmentCandidateTable
              :rows="candidateRows" :loading="candidateLoading" :can-write="canWrite" :resume-sources="resumeSources"
              @edit="openCandidateEditor" @delete="removeCandidate" @refresh="loadCandidates"
              @row-updated="replaceCandidate" @source-created="addResumeSource"
            />
          </div>
        </el-form>
      </div>
      <template #footer><div class="editor-footer"><el-button @click="editorVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveProject">保存</el-button></div></template>
    </el-dialog>

    <el-dialog v-model="progressVisible" :title="`${activeProject?.projectName || activeProject?.orderNo || ''} 项目进度表`" width="min(760px, calc(100vw - 32px))">
      <div class="inline-create progress-create" v-if="canWrite">
        <el-date-picker v-model="progressOccurredAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择发生时间" />
        <el-input v-model="progressNote" placeholder="补充进度说明" @keyup.enter="addProgress" />
        <el-button type="primary" :loading="progressSaving" @click="addProgress">添加记录</el-button>
      </div>
      <el-timeline v-loading="progressLoading"><el-timeline-item v-for="item in progressRows" :key="item.id" :timestamp="formatDateTime(item.occurredAt)" :type="item.isSystem ? 'primary' : 'success'" placement="top"><el-card shadow="never"><div v-if="item.fromStatus || item.toStatus"><b>{{ item.fromStatus ? statusLabel(item.fromStatus) : '创建项目' }}</b><span> → </span><b>{{ item.toStatus ? statusLabel(item.toStatus) : '补充记录' }}</b></div><div class="progress-note">{{ item.note || '-' }}</div><small>{{ item.operatorName || '系统' }} · {{ item.isSystem ? '系统记录' : '人工记录' }}</small></el-card></el-timeline-item></el-timeline>
    </el-dialog>

    <el-dialog v-model="candidateVisible" :title="`${activeProject?.projectName || activeProject?.orderNo || ''} 简历人选跟进情况表`" width="min(1180px, calc(100vw - 32px))">
      <div class="candidate-toolbar"><span>共 {{ candidateRows.length }} 人</span><el-button v-if="canWrite" type="primary" @click="openCandidateEditor()">新增候选人</el-button></div>
      <RecruitmentCandidateTable
        :rows="candidateRows" :loading="candidateLoading" :can-write="canWrite" :resume-sources="resumeSources"
        @edit="openCandidateEditor" @delete="removeCandidate" @refresh="loadCandidates"
        @row-updated="replaceCandidate" @source-created="addResumeSource"
      />
    </el-dialog>

    <el-dialog v-model="candidateEditorVisible" :title="candidateForm.id ? '编辑候选人' : '新增候选人'" width="min(760px, calc(100vw - 32px))" top="5vh" append-to-body class="candidate-editor-dialog">
      <div class="candidate-editor-body"><el-form ref="candidateFormRef" :model="candidateForm" :rules="candidateRules" label-width="110px">
        <el-form-item label="候选人姓名" prop="candidateName"><el-input v-model="candidateForm.candidateName" /></el-form-item>
        <el-form-item label="简历路径"><el-input v-model="candidateForm.resumePath" /></el-form-item>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="简历来源"><el-select v-model="candidateForm.resumeSourceId" filterable clearable style="width:100%"><el-option v-for="source in resumeSources" :key="source.id" :label="source.label" :value="source.id" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="入职日期"><el-date-picker v-model="candidateForm.actualOnboardDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col></el-row>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="一面日期"><el-date-picker v-model="candidateForm.firstInterviewDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="二面日期"><el-date-picker v-model="candidateForm.secondInterviewDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col></el-row>
        <el-form-item label="一面详情"><el-input v-model="candidateForm.firstInterviewDetails" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="二面详情"><el-input v-model="candidateForm.secondInterviewDetails" type="textarea" :rows="3" /></el-form-item>
        <el-collapse><el-collapse-item title="更多信息" name="legacy">
          <el-form-item label="当前阶段"><el-select v-model="candidateForm.stage" style="width:100%"><el-option v-for="item in candidateStageOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="联系方式"><el-input v-model="candidateForm.contactInfo" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="跟进人"><el-select v-model="candidateForm.ownerId" filterable clearable style="width:100%"><el-option v-for="user in activeUsers" :key="user.id" :label="userLabel(user)" :value="user.id" /></el-select></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="推荐时间"><el-date-picker v-model="candidateForm.recommendedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="原面试时间"><el-date-picker v-model="candidateForm.interviewAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="Offer时间"><el-date-picker v-model="candidateForm.offerAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="下次跟进"><el-date-picker v-model="candidateForm.nextFollowUpAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
          <el-form-item label="计划入职"><el-date-picker v-model="candidateForm.plannedOnboardDate" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="candidateForm.remarks" type="textarea" :rows="3" /></el-form-item>
        </el-collapse-item></el-collapse>
      </el-form></div>
      <template #footer><el-button @click="candidateEditorVisible=false">取消</el-button><el-button type="primary" :loading="candidateSaving" @click="saveCandidate">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'
import { getClients } from '@/api/clients'
import { getUsers } from '@/api/users'
import {
  createRecruitmentCandidate, createRecruitmentProgress, createRecruitmentProject,
  deleteRecruitmentCandidate, deleteRecruitmentProject, getRecruitmentCandidates,
  getRecruitmentProgress, getRecruitmentProject, getRecruitmentProjectCount,
  getRecruitmentProjects, getRecruitmentResumeSources, previewRecruitmentProjectName, updateRecruitmentCandidate,
  updateRecruitmentProject,
} from '@/api/recruitmentProjects'
import RecruitmentLanguageDirections from './recruitment/RecruitmentLanguageDirections.vue'
import RecruitmentCandidateTable from './recruitment/RecruitmentCandidateTable.vue'

const canWrite = hasPermission('projects:write')
const statusOptions = [
  ['pending_setup','新建待立项'],['sourcing','立项启动（寻访阶段）'],['recommending','简历推荐中'],['interviewing','面试进行中'],['offer_negotiation','Offer谈判阶段'],['pending_onboard','候选人待入职'],['probation','已入职保用期'],['closed','项目结案'],
].map(([value,label]) => ({ value,label }))
const candidateStageOptions = [['screening','待筛选'],['recommended','已推荐'],['interviewing','面试中'],['offer','Offer阶段'],['pending_onboard','待入职'],['onboarded','已入职'],['rejected','已淘汰']].map(([value,label]) => ({value,label}))
const statusLabel = (value) => statusOptions.find((item) => item.value === value)?.label || value || '-'
const statusType = (value) => ({ pending_setup:'info', sourcing:'primary', recommending:'warning', interviewing:'warning', offer_negotiation:'warning', pending_onboard:'primary', probation:'success', closed:'success' }[value] || 'info')
const candidateStageLabel = (value) => candidateStageOptions.find((item) => item.value === value)?.label || value || '-'

// 顺序严格对应业务字段清单；序号、操作是结构列，不参与字段设置。
const tableColumns = [
  {key:'orderNo',label:'订单号',minWidth:190,tooltip:false},
  {key:'projectName',label:'项目名称',minWidth:230,tooltip:false},
  {key:'jobDescription',label:'职位描述',minWidth:200,tooltip:false},
  {key:'positionTitle',label:'职位名称/类型',minWidth:160},
  {key:'headcount',label:'招聘人数',minWidth:100},
  {key:'clientManagerName',label:'现客户经理',minWidth:120},
  {key:'projectStatus',label:'项目状态',minWidth:160},
  {key:'clientShortName',label:'客户简称',minWidth:120},
  {key:'clientCode',label:'客户编号',minWidth:120},
  {key:'clientName',label:'客户全称',minWidth:180},
  {key:'clientDomain',label:'客户领域',minWidth:150},
  {key:'contactName',label:'子客户/联系人',minWidth:140},
  {key:'customerOrderNo',label:'客户单号/项目标识',minWidth:160},
  {key:'languageSummary',label:'外语/翻译方向',minWidth:190},
  {key:'targetOnboard',label:'拟入职日期',minWidth:120},
  {key:'employmentPeriod',label:'拟履职周期',minWidth:190},
  {key:'workLocation',label:'任职工作属地',minWidth:150},
  {key:'serviceFee',label:'服务费用',minWidth:150},
  {key:'candidateCount',label:'简历人选数',minWidth:110},
  {key:'customerConsultationTime',label:'客户咨询时间',minWidth:170},
  {key:'customerConfirmationTime',label:'客户确认时间',minWidth:170},
  {key:'quotationPath',label:'报价单路径',minWidth:210},
  {key:'contractPath',label:'合同路径',minWidth:210},
  {key:'remarks',label:'备注',minWidth:200},
  {key:'emailSubjectPreview',label:'邮件主题预览',minWidth:220},
  {key:'socialPostRequest',label:'发圈请求',minWidth:200},
  {key:'resourceRequest',label:'资源请求',minWidth:200},
]
const defaultColumnKeys = [
  'orderNo','projectName','jobDescription','headcount','projectStatus','clientShortName',
  'languageSummary','targetOnboard','employmentPeriod','workLocation','serviceFee','candidateCount',
]
const dateTimeColumnKeys = new Set(['customerConsultationTime', 'customerConfirmationTime'])
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns('recruitment-details-v3', tableColumns, defaultColumnKeys)
const visibleColumns = computed(() => tableColumns.filter((item) => isVisible(item.key)))
const detailItems = [
  {label:'订单号',key:'orderNo'},{label:'项目名称',key:'projectName'},{label:'职位名称/类型',key:'positionTitle'},{label:'现客户经理',key:'clientManagerName'},{label:'客户编号',key:'clientCode'},{label:'客户全称',key:'clientName'},{label:'客户领域',key:'clientDomain'},{label:'客户咨询时间',key:'customerConsultationTime'},{label:'客户确认时间',key:'customerConfirmationTime'},{label:'报价单路径',key:'quotationPath',span:2},{label:'合同路径',key:'contractPath',span:2},{label:'项目路径',key:'projectPath',span:2},{label:'备注',key:'remarks',span:2},{label:'邮件主题预览',key:'emailSubjectPreview',span:2},{label:'发圈请求',key:'socialPostRequest',span:2},{label:'资源请求',key:'resourceRequest',span:2},{label:'创建时间',key:'createdAt'},{label:'更新时间',key:'updatedAt'},
]

const rows = ref([]); const loading = ref(false); const users = ref([]); const clients = ref([]); const resumeSources = ref([])
const activeUsers = computed(() => users.value.filter((item) => item.is_active !== false))
const managerUserOptions = computed(() => { const current = users.value.find((item) => item.id === form.clientManagerId); return current && !current.is_active ? [current, ...activeUsers.value] : activeUsers.value })
const userLabel = (user) => user.full_name || user.username
const userOptionLabel = (user) => `${userLabel(user)}${user.is_active === false ? '（已停用）' : ''}`
const clientDomainText = (item) => [item?.field_level1, item?.field_level2].filter(Boolean).join(' / ')
const clientOptions = computed(() => clients.value.flatMap((client) => [
  {
    value:`client:${client.id}`,label:client.client_short_name || client.client_name,
    clientId:client.id,subClientId:'',clientShortName:client.client_short_name || '',
    clientCode:client.client_code || '',clientName:client.client_name || '',
    clientDomain:clientDomainText(client),clientManager:client.client_manager || '',
  },
  ...((client.sub_clients || []).map((sub) => ({
    value:`sub:${sub.id}`,label:`${client.client_short_name || client.client_name} / ${sub.client_short_name || sub.client_name}`,
    clientId:client.id,subClientId:sub.id,clientShortName:sub.client_short_name || '',
    clientCode:sub.sub_client_code || '',clientName:sub.client_name || '',
    clientDomain:clientDomainText(sub),clientManager:sub.client_manager || client.client_manager || '',
  }))),
]))

const pagination = reactive({page:1,limit:20,total:0})
const searchForm = reactive({keyword:'',projectStatus:'',clientManagerId:'',employmentRange:[]})
const advancedVisible = ref(false)
const advancedCount = computed(() => Number(!!searchForm.clientManagerId) + Number(searchForm.employmentRange?.length === 2))
let searchTimer = null; let controller = null; let sequence = 0
const buildFilters = () => ({ keyword:searchForm.keyword.trim() || undefined, project_status:searchForm.projectStatus || undefined, client_manager_id:searchForm.clientManagerId || undefined, employment_date_start:searchForm.employmentRange?.[0] || undefined, employment_date_end:searchForm.employmentRange?.[1] || undefined })
const fetchData = async () => { controller?.abort(); controller = new AbortController(); const current=++sequence; loading.value=true; try { const filters=buildFilters(); const [list,count]=await Promise.all([getRecruitmentProjects({skip:(pagination.page-1)*pagination.limit,limit:pagination.limit,...filters},{signal:controller.signal}),getRecruitmentProjectCount(filters,{signal:controller.signal})]); if(current!==sequence)return; rows.value=list||[]; pagination.total=count?.total||0 } catch(error){ if(error?.code!=='ERR_CANCELED'&&current===sequence) ElMessage.error(error?.response?.data?.detail||'招聘项目加载失败') } finally { if(current===sequence)loading.value=false } }
const handleTextSearch = (value) => { clearTimeout(searchTimer); if(!value)return handleSearch(); searchTimer=setTimeout(handleSearch,400) }
const handleSearch = () => { clearTimeout(searchTimer); pagination.page=1; fetchData() }
const resetSearch = () => { Object.assign(searchForm,{keyword:'',projectStatus:'',clientManagerId:'',employmentRange:[]}); handleSearch() }
const clearAdvanced = () => { searchForm.clientManagerId=''; searchForm.employmentRange=[]; handleSearch() }
const handleSizeChange = () => { pagination.page=1; fetchData() }

const emptyForm = () => ({id:'',orderNo:'',projectName:'',jobDescription:'',positionTitle:'',headcountMin:null,headcountMax:null,projectStatus:'pending_setup',clientId:'',subClientId:'',clientSelection:'',clientShortName:'',clientCode:'',clientName:'',clientDomain:'',contactName:'',customerOrderNo:'',clientManagerId:'',targetOnboardType:'date',targetOnboardDate:'',employmentRange:[],workLocation:'',serviceFeeType:'',serviceFeeCurrency:'CNY',serviceFeeAmount:null,serviceFeeRate:null,serviceFeeNote:'',customerConsultationTime:'',customerConfirmationTime:'',projectPath:'',quotationPath:'',contractPath:'',remarks:'',emailSubjectPreview:'',socialPostRequest:'',resourceRequest:'',languageDirections:[]})
const form = reactive(emptyForm()); const formRef=ref(); const editorBodyRef=ref(); const editorVisible=ref(false); const saving=ref(false); const nameLoading=ref(false); const editorTitle=computed(()=>form.id?'编辑招聘项目':'新增招聘项目')
const rules = { projectStatus:[{required:true,message:'请选择项目状态',trigger:'change'}], positionTitle:[{required:true,message:'请输入职位名称/类型',trigger:'blur'}], headcountMin:[{required:true,message:'请输入招聘人数',trigger:'change'}], employmentRange:[{required:true,message:'请选择拟履职周期',trigger:'change'}], workLocation:[{required:true,message:'请输入任职工作属地',trigger:'blur'}] }
const resolveManagerByName = (name) => {
  const exact = activeUsers.value.filter((user) => userLabel(user) === String(name || '').trim())
  if (exact.length === 1) return exact[0].id
  const fallback = activeUsers.value.filter((user) => userLabel(user) === '欧阳靖琳')
  return fallback.length === 1 ? fallback[0].id : ''
}
const selectClient = (value) => {
  const item=clientOptions.value.find((option)=>option.value===value)
  Object.assign(form, {
    clientId:item?.clientId||'',subClientId:item?.subClientId||'',
    clientShortName:item?.clientShortName||'',clientCode:item?.clientCode||'',
    clientName:item?.clientName||'',clientDomain:item?.clientDomain||'',
    clientManagerId:item ? resolveManagerByName(item.clientManager) : '',
  })
}
const resetForm = () => { Object.assign(form,emptyForm()); formRef.value?.clearValidate() }
const openAdd = () => { resetForm(); const defaultManager=activeUsers.value.filter((item)=>userLabel(item)==='欧阳靖琳'); if(defaultManager.length===1)form.clientManagerId=defaultManager[0].id; editorVisible.value=true }
const openEdit = async (row) => { try { const item=await getRecruitmentProject(row.id); Object.assign(form,emptyForm(),item,{employmentRange:item.employmentStart&&item.employmentEnd?[item.employmentStart,item.employmentEnd]:[],clientSelection:item.subClientId?`sub:${item.subClientId}`:(item.clientId?`client:${item.clientId}`:'')}); activeProject.value=item; candidateRows.value=[]; editorVisible.value=true; loadCandidates() } catch(error){ElMessage.error(error?.response?.data?.detail||'项目详情加载失败')} }
const clean = (value) => value===''?null:value
const buildPayload = () => ({projectName:clean(form.projectName),jobDescription:clean(form.jobDescription),positionTitle:clean(form.positionTitle),headcountMin:form.headcountMin,headcountMax:form.headcountMax??form.headcountMin,projectStatus:form.projectStatus,clientId:clean(form.clientId),subClientId:clean(form.subClientId),contactName:clean(form.contactName),customerOrderNo:clean(form.customerOrderNo),clientManagerId:clean(form.clientManagerId),targetOnboardType:form.targetOnboardType,targetOnboardDate:form.targetOnboardType==='anytime'?null:clean(form.targetOnboardDate),employmentStart:form.employmentRange?.[0]||null,employmentEnd:form.employmentRange?.[1]||null,workLocation:clean(form.workLocation),serviceFeeType:clean(form.serviceFeeType),serviceFeeCurrency:clean(form.serviceFeeCurrency),serviceFeeAmount:form.serviceFeeType==='fixed'?form.serviceFeeAmount:null,serviceFeeRate:form.serviceFeeType==='annual_salary_rate'?form.serviceFeeRate:null,serviceFeeNote:clean(form.serviceFeeNote),customerConsultationTime:clean(form.customerConsultationTime),customerConfirmationTime:clean(form.customerConfirmationTime),projectPath:clean(form.projectPath),quotationPath:clean(form.quotationPath),contractPath:clean(form.contractPath),remarks:clean(form.remarks),emailSubjectPreview:clean(form.emailSubjectPreview),socialPostRequest:clean(form.socialPostRequest),resourceRequest:clean(form.resourceRequest),languageDirections:form.languageDirections.filter((item)=>item.sourceLanguageId).map((item)=>({...item,targetLanguageId:item.directionType==='translation'?item.targetLanguageId:null}))})
const generateName = async () => { const payload=buildPayload(); if(!payload.employmentStart||!payload.employmentEnd||!payload.workLocation||!payload.positionTitle||!payload.languageDirections.length)return ElMessage.warning('请先填写拟履职周期、工作属地、外语/翻译方向和职位名称'); nameLoading.value=true; try { const result=await previewRecruitmentProjectName({employmentStart:payload.employmentStart,employmentEnd:payload.employmentEnd,workLocation:payload.workLocation,positionTitle:payload.positionTitle,languageDirections:payload.languageDirections}); form.projectName=result.projectName; ElMessage.success('项目名称已生成') } catch(error){ElMessage.error(error?.response?.data?.detail||'项目名称生成失败')} finally{nameLoading.value=false} }
const saveProject = async () => { if(!formRef.value)return; const valid=await formRef.value.validate().catch(()=>false); if(!valid){ editorBodyRef.value?.querySelector('.is-error')?.scrollIntoView({behavior:'smooth',block:'center'}); return } saving.value=true; try { const payload=buildPayload(); if(form.id)await updateRecruitmentProject(form.id,payload); else await createRecruitmentProject(payload); ElMessage.success(form.id?'招聘项目已更新':'招聘项目已创建'); editorVisible.value=false; fetchData() } catch(error){ElMessage.error(error?.response?.data?.detail||'保存失败')} finally{saving.value=false} }
const removeProject = async (row) => { try { await ElMessageBox.confirm(`确认删除招聘项目 ${row.orderNo} 吗？`,'提示',{type:'warning'}); await deleteRecruitmentProject(row.id); ElMessage.success('删除成功'); fetchData() } catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error?.response?.data?.detail||'删除失败')} }

const currentLocalDateTime = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
const progressVisible=ref(false), progressLoading=ref(false), progressSaving=ref(false), progressRows=ref([]), progressNote=ref(''), progressOccurredAt=ref(currentLocalDateTime()), activeProject=ref(null)
const openProgress = async (row) => { activeProject.value=row; progressNote.value=''; progressOccurredAt.value=currentLocalDateTime(); progressVisible.value=true; progressLoading.value=true; try{progressRows.value=await getRecruitmentProgress(row.id)}catch{ElMessage.error('进度记录加载失败')}finally{progressLoading.value=false} }
const addProgress = async () => { if(!progressOccurredAt.value)return ElMessage.warning('请选择发生时间'); if(!progressNote.value.trim())return ElMessage.warning('请输入进度说明'); progressSaving.value=true; try{await createRecruitmentProgress(activeProject.value.id,{note:progressNote.value.trim(),occurredAt:progressOccurredAt.value}); progressNote.value=''; progressOccurredAt.value=currentLocalDateTime(); progressRows.value=await getRecruitmentProgress(activeProject.value.id)}catch(error){ElMessage.error(error?.response?.data?.detail||'添加失败')}finally{progressSaving.value=false} }

const candidateVisible=ref(false),candidateLoading=ref(false),candidateRows=ref([]),candidateEditorVisible=ref(false),candidateSaving=ref(false),candidateFormRef=ref()
const emptyCandidate=()=>({id:'',candidateName:'',contactInfo:'',resumePath:'',resumeSourceId:'',stage:'screening',recommendedAt:'',interviewAt:'',offerAt:'',plannedOnboardDate:'',actualOnboardDate:'',firstInterviewDate:'',firstInterviewDetails:'',secondInterviewDate:'',secondInterviewDetails:'',ownerId:'',nextFollowUpAt:'',remarks:''})
const candidateForm=reactive(emptyCandidate()); const candidateRules={candidateName:[{required:true,message:'请输入候选人姓名',trigger:'blur'}]}
const loadCandidates=async()=>{candidateLoading.value=true;try{candidateRows.value=await getRecruitmentCandidates(activeProject.value.id)}catch{ElMessage.error('候选人加载失败')}finally{candidateLoading.value=false}}
const openCandidates=async(row)=>{activeProject.value=row;candidateVisible.value=true;await loadCandidates()}
const openCandidateEditor=(row=null)=>{Object.assign(candidateForm,emptyCandidate(),row||{});candidateEditorVisible.value=true}
const candidatePayload=()=>Object.fromEntries(Object.keys(emptyCandidate()).filter((key)=>key!=='id').map((key)=>[key,clean(candidateForm[key])]))
const saveCandidate=async()=>{const valid=await candidateFormRef.value?.validate().catch(()=>false);if(!valid)return;candidateSaving.value=true;try{if(candidateForm.id)await updateRecruitmentCandidate(candidateForm.id,candidatePayload());else await createRecruitmentCandidate(activeProject.value.id,candidatePayload());candidateEditorVisible.value=false;await loadCandidates();await fetchData();ElMessage.success('候选人已保存')}catch(error){ElMessage.error(error?.response?.data?.detail||'保存失败')}finally{candidateSaving.value=false}}
const removeCandidate=async(row)=>{try{await ElMessageBox.confirm(`确认删除候选人 ${row.candidateName} 吗？`,'提示',{type:'warning'});await deleteRecruitmentCandidate(row.id);await loadCandidates();await fetchData()}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error('删除失败')}}
const replaceCandidate=(updated)=>{const index=candidateRows.value.findIndex((item)=>item.id===updated.id);if(index>=0)candidateRows.value.splice(index,1,updated)}
const addResumeSource=(source)=>{if(!resumeSources.value.some((item)=>item.id===source.id))resumeSources.value.push(source);resumeSources.value.sort((a,b)=>Number(a.isCustom)-Number(b.isCustom)||a.label.localeCompare(b.label,'zh-CN'))}

const displayValue=(value)=>value===null||value===undefined||value===''?'-':value
const formatDate=(value)=>value?new Intl.DateTimeFormat('zh-CN').format(new Date(`${value}T00:00:00`)):'-'
const formatDateTime=(value)=>value?new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)):'-'
const headcountText=(row)=>row.headcountMin==null?'-':(row.headcountMax!=null&&row.headcountMax!==row.headcountMin?`${row.headcountMin}–${row.headcountMax}人`:`${row.headcountMin}人`)
const languageText=(row)=>(row.languageDirections||[]).map((item)=>item.label).join('；')||'-'
const periodText=(row)=>row.employmentStart&&row.employmentEnd?`${formatDate(row.employmentStart)}—${formatDate(row.employmentEnd)}`:'-'
const feeText=(row)=>row.serviceFeeType==='fixed'?`${row.serviceFeeCurrency||'CNY'} ${row.serviceFeeAmount??'-'}`:row.serviceFeeType==='annual_salary_rate'?`年薪 ${row.serviceFeeRate??'-'}%`:row.serviceFeeType==='other'?(row.serviceFeeNote||'其他'):'-'
const toOpenPathHref=(path)=>`openpath://${encodeURIComponent(String(path).replace(/^\\\\/,'')).replace(/%5C/gi,'\\').replace(/%2F/gi,'/')}`
const openPath=(path)=>{if(!path?.trim())return ElMessage.warning('该项目暂无路径');window.location.href=toOpenPathHref(path.trim())}
const copyPath=async(path)=>{if(!path?.trim())return ElMessage.warning('该项目暂无路径');try{await navigator.clipboard.writeText(path.trim());ElMessage.success('路径已复制')}catch{ElMessage.error('复制失败，请手工复制')}}

onMounted(async()=>{const [userRows,clientRows,sourceRows]=await Promise.all([getUsers({skip:0,limit:500}),getClients({skip:0,limit:500}),getRecruitmentResumeSources()]).catch(()=>[[],[],[]]);users.value=userRows||[];clients.value=clientRows||[];resumeSources.value=sourceRows||[];fetchData()})
onBeforeUnmount(()=>{clearTimeout(searchTimer);controller?.abort()})
</script>

<style scoped>
.card-header,.header-actions,.advanced-footer,.candidate-toolbar,.inline-create,.name-field,.number-range,.money-field,.candidate-heading-actions{display:flex;align-items:center;gap:8px}.card-header,.candidate-toolbar{justify-content:space-between}.search-form{margin-bottom:8px}.pagination{margin-top:20px}.advanced-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-footer{justify-content:flex-end;border-top:1px solid var(--el-border-color-lighter);padding-top:10px}.order-cell{display:flex;align-items:center}.wrap-link{height:auto;white-space:normal;text-align:left}.description-preview{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.long-text-detail{max-height:560px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}.editor-body{overflow-y:auto;padding:0 4px}.form-section{padding:0 8px 12px;margin-bottom:14px;border:1px solid var(--el-border-color-lighter);border-radius:6px}.form-section h3{margin:0 -8px 16px;padding:10px 14px;background:var(--el-fill-color-light);font-size:15px}.section-heading{position:relative}.section-heading h3{padding-right:210px}.candidate-heading-actions{position:absolute;right:8px;top:6px}.name-field{width:100%}.name-field .el-input{flex:1}.number-range .el-input-number{width:130px}.money-field{width:100%}.money-field .el-select{width:110px}.suffix{margin-left:6px}.editor-footer{justify-content:flex-end}.inline-create{margin-bottom:18px}.inline-create .el-input{flex:1}.progress-create :deep(.el-date-editor){width:210px;flex:none}.progress-note{margin:8px 0;white-space:pre-wrap}.candidate-toolbar{margin-bottom:12px}
:deep(.recruitment-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:deep(.recruitment-editor .el-dialog__header),:deep(.recruitment-editor .el-dialog__footer){flex:none}:deep(.recruitment-editor .el-dialog__body){display:flex;flex:1;min-height:0;overflow:hidden;padding-top:8px}:deep(.recruitment-editor .editor-body){flex:1;min-height:0}:deep(.recruitment-editor .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
:global(.candidate-editor-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.candidate-editor-dialog .el-dialog__header),:global(.candidate-editor-dialog .el-dialog__footer){flex:none}:global(.candidate-editor-dialog .el-dialog__body){display:flex;flex:1;min-height:0;overflow:hidden;padding-top:8px}:global(.candidate-editor-dialog .candidate-editor-body){flex:1;min-height:0;overflow-y:auto;padding:0 4px}:global(.candidate-editor-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
@media(max-width:720px){.search-form :deep(.el-form-item){display:flex;margin-right:0}.search-form :deep(.el-form-item__content){flex:1}.name-field,.number-range,.money-field,.progress-create{align-items:stretch;flex-direction:column}.number-range .el-input-number,.money-field .el-select,.progress-create :deep(.el-date-editor){width:100%}.section-heading h3{padding-right:8px;padding-bottom:52px}.candidate-heading-actions{left:8px;right:auto;top:38px}}
</style>
