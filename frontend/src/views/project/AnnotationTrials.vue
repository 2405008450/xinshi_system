<template>
  <el-card class="compact-list-card">
    <template #header>
      <div class="card-header">
        <div><h2>试标/试采流程</h2><p>跨项目查看候选进度；选择项目后可打开项目级管理窗口</p></div>
        <div class="header-actions">
          <CustomFieldManager v-if="canWrite&&projectId" table-code="trial" :project-id="projectId" @changed="loadFields" />
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="3" @reset="resetColumns" />
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite&&!deleteMode" type="primary" :disabled="!projectId" @click="openEditor()">新增候选</el-button>
          <el-button :disabled="!projectId" @click="openWorkspaceById">打开管理窗口</el-button>
        </div>
      </div>
    </template>

    <div class="trial-search-toolbar">
      <el-select v-model="projectId" clearable filterable placeholder="全部标注项目" class="project-filter" @change="handleProjectChange"><el-option v-for="item in projects" :key="item.id" :label="projectLabel(item)" :value="item.id" /></el-select>
      <el-input v-model="filters.keyword" clearable placeholder="搜索项目、编号、姓名、意愿或评语" class="keyword-filter" @input="handleKeywordInput" @keyup.enter="search" />
      <el-button type="primary" @click="search">查询</el-button><el-button @click="resetFilters">重置</el-button>
      <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="trial-advanced-popover">
        <template #reference><el-button>高级筛选<span v-if="advancedCount" class="filter-count">{{ advancedCount }}</span></el-button></template>
        <div class="advanced-panel">
          <div class="advanced-header"><strong>高级筛选</strong><el-button link type="primary" @click="clearAdvanced">清空高级条件</el-button></div>
          <AppForm label-position="top"><el-row :gutter="16">
            <el-col :xs="24" :md="8"><el-form-item label="人员"><el-select v-model="personId" clearable filterable style="width:100%" @change="search"><el-option v-for="item in talents" :key="item.id" :label="talentLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="语言方向"><el-select v-model="filters.languageItemId" clearable :disabled="!selectedProject" style="width:100%" @change="search"><el-option v-for="item in selectedProject?.languageItems||[]" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="候选阶段"><el-select v-model="filters.candidateStage" clearable style="width:100%" @change="search"><el-option v-for="item in stageOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="业务类型"><el-select v-model="filters.activityType" clearable style="width:100%" @change="search"><el-option v-for="item in activityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="工作职责"><el-select v-model="filters.dutyRole" clearable style="width:100%" @change="search"><el-option v-for="item in dutyOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="结果"><el-select v-model="filters.trialResult" clearable style="width:100%" @change="search"><el-option v-for="item in resultOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          </el-row></AppForm>
          <div class="advanced-footer"><el-button @click="advancedVisible=false">关闭</el-button></div>
        </div>
      </el-popover>
    </div>

    <AnnotationTrialTable ref="trialTableRef" :rows="rows" :columns="visibleColumns" :custom-fields="customFields" :loading="loading" :delete-mode="deleteMode" :can-write="canWrite" @selection-change="handleDeleteSelectionChange" @follow-up="openFollowUps" @accounts="openAccounts" @edit="openEditor" />
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @size-change="handlePageChange" @current-change="handlePageChange" />
  </el-card>

  <DraggableFormDialog v-model="workspaceVisible" :fullscreen="workspaceMaximized" width="min(1500px, calc(100vw - 32px))" top="3vh" class="trial-workspace-dialog" append-to-body @closed="closeWorkspace">
    <template #header><div class="workspace-dialog-header">
      <div class="workspace-title" @mousedown.stop><strong>{{ activeProject?.orderNo||'-' }} · {{ activeProject?.projectName||'未命名项目' }}</strong><span>试标/试采管理</span></div>
      <div class="workspace-header-actions" @mousedown.stop>
        <AnnotationProjectDetailPopover v-if="activeProject?.id" :project-id="activeProject.id" :summary="activeProject" placement="bottom-end"><template #reference><el-button>项目详情</el-button></template></AnnotationProjectDetailPopover>
        <el-button @click="workspaceMaximized=!workspaceMaximized">{{ workspaceMaximized?'恢复窗口':'最大化' }}</el-button>
      </div>
    </div></template>
    <div class="workspace-body" v-loading="workspaceLoading">
      <div class="workspace-summary-toolbar"><div><strong>语言方向与人数策略</strong><span class="summary-note">按10%转化率计算建议联系人数；储备数据来自人才概览</span></div><div class="header-actions"><el-button @click="openComparison">资源比较</el-button><el-button v-if="canWrite" @click="openStrategyEditor">编辑人数策略</el-button><el-button v-if="canWrite" type="primary" @click="openEditor()">添加候选人</el-button></div></div>
      <div class="language-summary-grid">
        <div v-for="item in languageSummaries" :key="item.languageItemId" class="language-summary-card" :class="{'is-warning':item.reserveTotal<10}">
          <div class="language-summary-title"><strong>{{ item.languageDisplay }}</strong><el-tag v-if="item.reserveTotal<10" type="danger" size="small">储备不足10</el-tag></div>
          <div class="language-summary-metrics"><div><span>人才概览储备</span><strong>{{ item.reserveTotal }}</strong></div><div><span>计划人数</span><strong>{{ item.plannedHeadcount }}</strong></div><div><span>建议联系</span><strong>{{ item.suggestedContactCount }}</strong></div><div><span>候选</span><strong>{{ item.candidateCount }}</strong></div><div><span>已联系</span><strong>{{ item.contactedCount }}</strong></div><div><span>已确认</span><strong>{{ item.confirmedCount }}</strong></div><div><span>已提交</span><strong>{{ item.submittedCount }}</strong></div><div><span>已通过</span><strong>{{ item.passedCount }}</strong></div></div>
          <div v-if="item.strategyNote" class="strategy-note">{{ item.strategyNote }}</div>
        </div>
        <el-empty v-if="!languageSummaries.length" description="请先在项目详情中维护语言方向" :image-size="64" />
      </div>
      <el-alert title="人才概览储备为各来源数量累计，可能包含重复；实际候选人员来自人才总库。语言方向按任一语种命中。" type="info" :closable="false" show-icon />
      <div class="workspace-table-heading"><strong>候选资源</strong><span>共 {{ pagination.total }} 条</span></div>
      <AnnotationTrialTable :rows="rows" :columns="visibleColumns" :custom-fields="customFields" :loading="loading" :delete-mode="false" :can-write="canWrite" @follow-up="openFollowUps" @accounts="openAccounts" @edit="openEditor" />
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next" class="pagination" @size-change="handlePageChange" @current-change="handlePageChange" />
    </div>
    <template #footer><el-button @click="workspaceVisible=false">关闭</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="editorVisible" width="min(980px, calc(100vw - 32px))" top="5vh" append-to-body class="trial-editor-dialog" @opened="onEditorOpened" @closed="resetEditor">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="form.id?'编辑试标/试采候选':'新增试标/试采候选'" :subtitle="activeProjectLabel" :fetch-suggestions="fetchFieldSuggestions" placeholder="搜索字段，如截止时间" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBodyRef"><AppForm ref="formRef" :model="form" :rules="rules" label-width="110px">
      <section class="form-section"><h3>人员与职责</h3>
        <el-form-item label="标注项目" prop="projectId"><ReadonlyField :model-value="activeProjectLabel" source="locked" placeholder="请先选择项目" /></el-form-item>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="语言方向" prop="languageItemId"><el-select v-model="form.languageItemId" :disabled="Boolean(form.id)" style="width:100%" @change="languageChanged"><el-option v-for="item in activeProject?.languageItems||[]" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="人员" prop="personId"><div class="inline-control"><el-select v-model="form.personId" filterable :disabled="!form.languageItemId||Boolean(form.id)" placeholder="按任一语种匹配" style="width:100%" @change="personChanged"><el-option v-for="item in eligibleTalents" :key="item.id" :label="talentLabel(item)" :value="item.id" /></el-select><el-button v-if="canWrite&&!form.id" @click="openQuickTalent">快速新增</el-button></div></el-form-item></el-col></el-row>
        <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="业务类型" prop="activityType"><el-select v-model="form.activityType" style="width:100%"><el-option v-for="item in activityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="工作职责" prop="dutyRole"><el-select v-model="form.dutyRole" style="width:100%"><el-option v-for="item in dutyOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="轮次"><el-input-number v-model="form.roundNo" :min="1" style="width:100%" /></el-form-item></el-col></el-row>
        <el-form-item label="候选阶段" prop="candidateStage"><el-select v-model="form.candidateStage" style="width:100%"><el-option v-for="item in stageOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      </section>
      <section class="form-section"><h3>意愿、报价与账号</h3>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="意愿"><el-select v-model="form.willingnessLevel" clearable style="width:100%"><el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="平台账号"><el-select v-model="form.platformAccountId" clearable filterable :loading="accountLoading" :disabled="!form.personId" style="width:100%"><el-option v-for="item in accountOptions" :key="item.id" :label="accountOptionLabel(item)" :value="item.id" /></el-select></el-form-item></el-col></el-row>
        <el-form-item label="意愿说明"><el-input v-model="form.willingnessText" type="textarea" :rows="2" /></el-form-item>
        <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="报价金额" prop="quoteAmount"><el-input-number v-model="form.quoteAmount" :min="0" :precision="2" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="币种"><el-select v-model="form.quoteCurrency" clearable style="width:100%"><el-option v-for="item in currencyOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="计费单位" prop="billingUnit"><el-select v-model="form.billingUnit" clearable style="width:100%"><el-option v-for="item in billingOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col></el-row>
        <div class="form-tip">试标/试采报价仅作历史参考，进入正式安排时需要重新确认。</div>
      </section>
      <section class="form-section"><h3>时间与结果</h3>
        <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="开始时间"><el-date-picker v-model="form.startedAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="截止时间" prop="deadlineAt"><el-date-picker v-model="form.deadlineAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="实际提交时间"><el-date-picker v-model="form.submittedAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item></el-col></el-row>
        <el-form-item label="结果"><el-select v-model="form.trialResult" clearable style="width:100%"><el-option v-for="item in resultOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item label="结果说明" prop="resultNote"><el-input v-model="form.resultNote" type="textarea" :rows="3" placeholder="选择“部分通过”时必须填写" /></el-form-item>
      </section>
      <section class="form-section"><h3>项目级表现</h3>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="配合度"><el-select v-model="form.cooperationLevel" clearable style="width:100%"><el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="守时度"><el-select v-model="form.punctualityLevel" clearable style="width:100%"><el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col></el-row>
        <el-form-item label="配合度说明"><el-input v-model="form.cooperationNote" type="textarea" :rows="2" /></el-form-item><el-form-item label="守时度说明"><el-input v-model="form.punctualityNote" type="textarea" :rows="2" /></el-form-item><el-form-item label="总体评分"><el-input-number v-model="form.overallScore" :min="1" :max="10" /></el-form-item><el-form-item label="项目经理评价"><el-input v-model="form.managerComment" type="textarea" :rows="3" /></el-form-item>
      </section>
      <section v-if="editorFields.length" class="form-section"><h3>项目自定义字段</h3><AnnotationCustomFieldInputs :fields="editorFields" :values="form.customValues" /></section>
    </AppForm></div>
    <template #footer><el-button @click="editorVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="strategyVisible" title="试标/试采人数策略" width="min(820px, calc(100vw - 32px))" top="8vh" append-to-body class="strategy-dialog">
    <AppForm label-width="110px"><div v-for="item in strategyDrafts" :key="item.languageItemId" class="strategy-editor-row"><h4>{{ item.languageDisplay }}</h4><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="计划人数"><el-input-number v-model="item.plannedHeadcount" :min="1" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="预计转化率"><el-input-number v-model="item.conversionPercent" :min="1" :max="100" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="建议联系"><ReadonlyField :model-value="String(suggestedContact(item))" source="auto" /></el-form-item></el-col></el-row><el-form-item label="策略备注"><el-input v-model="item.strategyNote" type="textarea" :rows="2" /></el-form-item></div></AppForm>
    <template #footer><el-button @click="strategyVisible=false">取消</el-button><el-button type="primary" :loading="strategySaving" @click="saveStrategies">保存</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="followUpVisible" :title="`${activeTrial?.personName||'候选人'} · 跟进记录`" width="min(760px, calc(100vw - 32px))" top="8vh" append-to-body class="follow-up-dialog">
    <div v-loading="followUpLoading" class="follow-up-body"><el-timeline v-if="followUpRows.length"><el-timeline-item v-for="item in followUpRows" :key="item.id" :timestamp="`${formatDateTime(item.createdAt)} · ${item.createdByName||'未知用户'}`"><el-tag size="small" effect="plain">{{ followUpTypeLabel(item.followUpType) }}</el-tag><div class="follow-up-content">{{ item.content }}</div><div v-if="item.nextFollowUpAt" class="detail-secondary">下次跟进：{{ formatDateTime(item.nextFollowUpAt) }}</div></el-timeline-item></el-timeline><el-empty v-else description="暂无跟进记录" :image-size="64" /><AppForm v-if="canWrite" :model="followUpForm" label-width="90px" class="follow-up-form"><el-form-item label="跟进类型"><el-select v-model="followUpForm.followUpType" style="width:100%"><el-option v-for="item in followUpTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item label="跟进内容"><el-input v-model="followUpForm.content" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item><el-form-item label="下次跟进"><el-date-picker v-model="followUpForm.nextFollowUpAt" type="datetime" clearable value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item></AppForm></div>
    <template #footer><el-button @click="followUpVisible=false">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="followUpSaving" @click="saveFollowUp">添加跟进</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="quickTalentVisible" title="快速新增人才" width="min(620px, calc(100vw - 32px))" append-to-body>
    <AppForm ref="quickTalentFormRef" :model="quickTalentForm" :rules="quickTalentRules" label-width="100px"><el-form-item label="姓名" prop="fullName"><el-input v-model="quickTalentForm.fullName" /></el-form-item><el-form-item label="联系电话"><el-input v-model="quickTalentForm.primaryPhone" /></el-form-item><el-form-item label="电子邮箱"><el-input v-model="quickTalentForm.primaryEmail" /></el-form-item><el-form-item label="掌握语种" prop="languageId"><el-select v-model="quickTalentForm.languageId" style="width:100%"><el-option v-for="item in quickLanguageOptions" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item><el-alert title="保存后生成正式人才档案和资源编号，其他资料可稍后补充。" type="info" :closable="false" show-icon /></AppForm>
    <template #footer><el-button @click="quickTalentVisible=false">取消</el-button><el-button type="primary" :loading="quickTalentSaving" @click="saveQuickTalent">保存并选用</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="comparisonVisible" title="同语言方向资源比较" width="min(1200px, calc(100vw - 32px))" top="5vh" append-to-body class="comparison-dialog">
    <div class="comparison-toolbar"><el-select v-model="comparisonLanguageItemId" style="width:280px" @change="loadComparison"><el-option v-for="item in activeProject?.languageItems||[]" :key="item.id" :label="item.display" :value="item.id" /></el-select></div>
    <el-table :data="comparisonRows" v-loading="comparisonLoading" border><el-table-column prop="resourceCode" label="资源编号" width="120" /><el-table-column prop="fullName" label="姓名" width="120" /><el-table-column label="母语" min-width="130"><template #default="{row}">{{ languageSkillsText(row,'native') }}</template></el-table-column><el-table-column label="第一外语" min-width="130"><template #default="{row}">{{ languageSkillsText(row,'foreign') }}</template></el-table-column><el-table-column label="本科院校/专业" min-width="220"><template #default="{row}">{{ educationText(row) }}</template></el-table-column><el-table-column label="标注经验" min-width="220" show-overflow-tooltip><template #default="{row}">{{ row.annotationExperience||'-' }}</template></el-table-column><el-table-column label="总体评分" width="100"><template #default="{row}">{{ row.overallScore||'-' }}</template></el-table-column><el-table-column label="项目情况" min-width="160"><template #default="{row}">{{ projectSituationText(row) }}</template></el-table-column></el-table>
    <template #footer><el-button @click="comparisonVisible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as projectApi from '@/api/annotationProjects'
import * as ops from '@/api/annotationOps'
import * as talentApi from '@/api/talents'
import AnnotationCustomFieldInputs from '@/components/annotation/AnnotationCustomFieldInputs.vue'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import AnnotationTrialTable from '@/components/annotation/AnnotationTrialTable.vue'
import CustomFieldManager from '@/components/annotation/CustomFieldManager.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const route=useRoute(),router=useRouter(),canWrite=hasPermission('projects:write')
const projects=ref([]),talents=ref([]),rows=ref([]),customFields=ref([]),editorFields=ref([]),accountOptions=ref([])
const projectId=ref(''),loading=ref(false),accountLoading=ref(false),advancedVisible=ref(false),trialTableRef=ref(null)
const pagination=reactive({page:1,limit:20,total:0})
const filters=reactive({keyword:'',personId:'',languageItemId:'',candidateStage:'',activityType:'',dutyRole:'',trialResult:''})
const personId=computed({get:()=>filters.personId,set:value=>{filters.personId=value}})
const activityOptions=[{value:'trial',label:'试标'},{value:'collection',label:'试采'}]
const dutyOptions=[{value:'executor',label:'执行'},{value:'quality_inspector',label:'质检'}]
const stageOptions=[{value:'backup',label:'备选'},{value:'contacted',label:'已联系'},{value:'pending_confirmation',label:'待确认'},{value:'confirmed',label:'已确认'},{value:'in_progress',label:'进行中'},{value:'submitted',label:'已提交'},{value:'reviewed',label:'已评审'},{value:'withdrawn',label:'已退出'}]
const resultOptions=[{value:'passed',label:'通过'},{value:'failed',label:'未通过'},{value:'partially_passed',label:'部分通过'},{value:'withdrawn',label:'退出'}]
const levelOptions=[{value:'high',label:'高'},{value:'medium',label:'中'},{value:'low',label:'低'}]
const billingOptions=[{value:'occurrence',label:'次'},{value:'item',label:'条'},{value:'work_hour',label:'工作小时'},{value:'effective_hour',label:'有效小时'}]
const currencyOptions=['CNY','USD','HKD','EUR','GBP']
const followUpTypeOptions=[{value:'contact',label:'联系'},{value:'status',label:'状态'},{value:'schedule',label:'时间安排'},{value:'quote',label:'报价'},{value:'result',label:'结果'},{value:'other',label:'其他'}]
const labelOf=(options,value)=>options.find(item=>item.value===value)?.label||value||'-'
const followUpTypeLabel=value=>labelOf(followUpTypeOptions,value)
const projectLabel=item=>`${item.orderNo||'-'} · ${item.projectName||'未命名'}`
const talentLabel=item=>`${item.fullName||'未命名'}（${item.resourceCode||'-'}）`
const accountOptionLabel=item=>[item.platformName||item.platformUrl,item.nickname,item.loginAccount].filter(Boolean).join(' · ')||'未命名账号'
const selectedProject=computed(()=>projects.value.find(item=>item.id===projectId.value)||null)
const advancedCount=computed(()=>['personId','languageItemId','candidateStage','activityType','dutyRole','trialResult'].filter(key=>filters[key]).length)

const staticColumns=[
  {key:'projectOrderNo',label:'订单号',width:130},{key:'projectName',label:'项目名称',minWidth:180},{key:'resourceCode',label:'资源编号',width:120},{key:'personName',label:'姓名',width:110},{key:'languageDisplay',label:'语言方向',minWidth:150},{key:'activityType',label:'业务类型',width:90},{key:'dutyRole',label:'工作职责',width:90},{key:'candidateStage',label:'候选阶段',width:100,tooltip:false},{key:'willingnessLevel',label:'意愿',width:80,tooltip:false},{key:'quote',label:'试标/试采报价',minWidth:170},{key:'startedAt',label:'开始时间',width:160,type:'datetime'},{key:'deadlineAt',label:'截止时间',width:160,type:'datetime'},{key:'submittedAt',label:'实际提交时间',width:160,type:'datetime'},{key:'trialResult',label:'结果',width:100},{key:'overallScore',label:'评分',width:75},{key:'latestFollowUp',label:'最近跟进',minWidth:190},
]
const tableColumns=computed(()=>[...staticColumns,...customFields.value.map(field=>({key:`custom:${field.id}`,label:field.fieldLabel,minWidth:130,customField:field}))])
const defaultColumnKeys=['projectOrderNo','projectName','resourceCode','personName','languageDisplay','activityType','dutyRole','candidateStage','willingnessLevel','trialResult','latestFollowUp']
const {selectedKeys:visibleColumnKeys,isVisible,reset:resetColumns}=useTableColumns('annotation-trials-v2',tableColumns,defaultColumnKeys)
const visibleColumns=computed(()=>tableColumns.value.filter(item=>isVisible(item.key)))
const buildQuery=()=>({personId:personId.value||undefined,languageItemId:filters.languageItemId||undefined,candidateStage:filters.candidateStage||undefined,activityType:filters.activityType||undefined,dutyRole:filters.dutyRole||undefined,trialResult:filters.trialResult||undefined,keyword:filters.keyword.trim()||undefined})
let searchTimer=null,requestController=null,requestId=0,accountRequestId=0
const loadFields=async()=>{customFields.value=projectId.value?await ops.getCustomFields('trial',projectId.value):[]}
const fetchRows=async()=>{requestController?.abort();requestController=new AbortController();const current=++requestId;loading.value=true;const query=buildQuery();try{const [items,count]=await Promise.all([ops.getTrials(projectId.value,{...query,skip:(pagination.page-1)*pagination.limit,limit:pagination.limit},{signal:requestController.signal}),ops.getTrialCount(projectId.value,query,{signal:requestController.signal})]);if(current!==requestId)return;rows.value=items||[];pagination.total=count?.total||0;await loadFields()}catch(error){if(error?.code!=='ERR_CANCELED'&&current===requestId)ElMessage.error(error.detail||'加载试标/试采记录失败')}finally{if(current===requestId)loading.value=false}}
const search=()=>{clearTimeout(searchTimer);pagination.page=1;exitDeleteMode();return fetchRows()}
const handleKeywordInput=value=>{clearTimeout(searchTimer);if(!value?.trim())return search();searchTimer=setTimeout(search,400)}
const handleProjectChange=()=>{filters.languageItemId='';search()}
const clearAdvanced=()=>{Object.assign(filters,{personId:'',languageItemId:'',candidateStage:'',activityType:'',dutyRole:'',trialResult:''});search()}
const resetFilters=()=>{projectId.value='';Object.assign(filters,{keyword:'',personId:'',languageItemId:'',candidateStage:'',activityType:'',dutyRole:'',trialResult:''});customFields.value=[];search()}
const handlePageChange=()=>{exitDeleteMode();fetchRows()}
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:trialTableRef,pagination,deleteRow:row=>ops.deleteTrial(row.id),getLabel:row=>`${row.personName||'未命名人才'} · ${row.languageDisplay||'-'}`,reload:fetchRows,entityName:'试标/试采候选记录'})

const workspaceVisible=ref(false),workspaceMaximized=ref(false),workspaceLoading=ref(false),activeProject=ref(null),strategies=ref([]),trialSummary=ref({total:0,items:[]})
const reserves=reactive({})
const activeProjectLabel=computed(()=>activeProject.value?projectLabel(activeProject.value):'')
const loadWorkspaceContext=async()=>{if(!activeProject.value?.id)return;workspaceLoading.value=true;try{const languageIds=[...new Set((activeProject.value.languageItems||[]).flatMap(item=>[item.sourceLanguageId,item.targetLanguageId]).filter(Boolean))];const [strategyRows,summary,reserveResult]=await Promise.all([ops.getTrialStrategies(activeProject.value.id),ops.getTrialSummary(activeProject.value.id),languageIds.length?projectApi.lookupAnnotationLanguageReserves(languageIds):Promise.resolve({items:[]})]);strategies.value=strategyRows||[];trialSummary.value=summary||{total:0,items:[]};for(const key of Object.keys(reserves))delete reserves[key];for(const item of reserveResult?.items||[])reserves[item.languageId]=item}catch(error){ElMessage.error(error.detail||'加载试标/试采管理信息失败')}finally{workspaceLoading.value=false}}
const languageSummaries=computed(()=>{const summaryMap=Object.fromEntries((trialSummary.value.items||[]).map(item=>[item.languageItemId,item]));const strategyMap=Object.fromEntries((strategies.value||[]).map(item=>[item.languageItemId,item]));return(activeProject.value?.languageItems||[]).map(language=>{const strategy=strategyMap[language.id]||{plannedHeadcount:1,conversionRate:0.1,suggestedContactCount:10};const summary=summaryMap[language.id]||{candidateCount:0,contactedCount:0,confirmedCount:0,submittedCount:0,passedCount:0};const endpointIds=[...new Set([language.sourceLanguageId,language.targetLanguageId].filter(Boolean))];const reserveTotal=endpointIds.reduce((total,id)=>total+Number(reserves[id]?.total||0),0);return{languageItemId:language.id,languageDisplay:language.display,reserveTotal,...strategy,...summary}})})
const openWorkspaceById=async()=>{if(!projectId.value)return ElMessage.warning('请先选择标注项目');workspaceVisible.value=true;workspaceLoading.value=true;try{activeProject.value=await projectApi.getAnnotationProject(projectId.value);await Promise.all([loadWorkspaceContext(),fetchRows()])}catch(error){ElMessage.error(error.detail||'打开试标/试采管理失败')}finally{workspaceLoading.value=false}}
const closeWorkspace=()=>{workspaceMaximized.value=false;activeProject.value=null;strategies.value=[];trialSummary.value={total:0,items:[]}}
const strategyVisible=ref(false),strategySaving=ref(false),strategyDrafts=ref([])
const openStrategyEditor=()=>{strategyDrafts.value=languageSummaries.value.map(item=>({languageItemId:item.languageItemId,languageDisplay:item.languageDisplay,plannedHeadcount:item.plannedHeadcount||1,conversionPercent:Math.round(Number(item.conversionRate||0.1)*100),strategyNote:item.strategyNote||''}));strategyVisible.value=true}
const suggestedContact=item=>Math.ceil(Number(item.plannedHeadcount||1)/(Number(item.conversionPercent||10)/100))
const saveStrategies=async()=>{strategySaving.value=true;try{strategies.value=await ops.saveTrialStrategies(activeProject.value.id,strategyDrafts.value.map(item=>({languageItemId:item.languageItemId,plannedHeadcount:item.plannedHeadcount,conversionRate:Number(item.conversionPercent)/100,strategyNote:item.strategyNote.trim()||null})));strategyVisible.value=false;ElMessage.success('人数策略已保存')}catch(error){ElMessage.error(error.detail||'保存人数策略失败')}finally{strategySaving.value=false}}

const emptyForm=()=>({id:'',projectId:'',personId:'',languageItemId:'',platformAccountId:null,roundNo:1,activityType:'trial',dutyRole:'executor',candidateStage:'backup',willingnessLevel:null,willingnessText:'',quoteAmount:null,quoteCurrency:'CNY',billingUnit:null,startedAt:null,deadlineAt:null,submittedAt:null,trialStatus:'pending',trialResult:null,resultNote:'',cooperationLevel:null,cooperationNote:'',punctualityLevel:null,punctualityNote:'',overallScore:null,managerComment:'',customValues:{}})
const form=reactive(emptyForm()),editorVisible=ref(false),saving=ref(false),formRef=ref(null),editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const rules={projectId:[{required:true,message:'请选择标注项目',trigger:'change'}],languageItemId:[{required:true,message:'请选择语言方向',trigger:'change'}],personId:[{required:true,message:'请选择人员',trigger:'change'}],activityType:[{required:true,message:'请选择业务类型',trigger:'change'}],dutyRole:[{required:true,message:'请选择工作职责',trigger:'change'}],candidateStage:[{required:true,message:'请选择候选阶段',trigger:'change'}],quoteAmount:[{validator:(_r,value,callback)=>((value==null&&!form.billingUnit)||(value>0&&form.billingUnit))?callback():callback(new Error('报价金额和计费单位必须同时填写')),trigger:['change','blur']}],billingUnit:[{validator:(_r,value,callback)=>((form.quoteAmount==null&&!value)||(form.quoteAmount>0&&value))?callback():callback(new Error('报价金额和计费单位必须同时填写')),trigger:'change'}],deadlineAt:[{validator:(_r,value,callback)=>!value||!form.startedAt||new Date(value)>=new Date(form.startedAt)?callback():callback(new Error('截止时间不能早于开始时间')),trigger:'change'}],resultNote:[{validator:(_r,value,callback)=>form.trialResult!=='partially_passed'||String(value||'').trim()?callback():callback(new Error('部分通过时请填写结果说明')),trigger:['change','blur']}]}
const selectedLanguageItem=computed(()=>activeProject.value?.languageItems?.find(item=>item.id===form.languageItemId)||null)
const eligibleTalents=computed(()=>{const language=selectedLanguageItem.value;if(!language)return[];const required=new Set([language.sourceLanguageId,language.targetLanguageId].filter(Boolean));const ids=skill=>[skill.sourceLanguageId,skill.targetLanguageId].filter(Boolean);const score=person=>(person.annotationLanguageSkills||[]).reduce((best,skill)=>Math.max(best,ids(skill).filter(id=>required.has(id)).length),0);return talents.value.filter(person=>(form.id&&person.id===form.personId)||(person.annotationLanguageSkills||[]).some(skill=>ids(skill).some(id=>required.has(id)))).sort((a,b)=>score(b)-score(a)||String(a.fullName).localeCompare(String(b.fullName),'zh-CN'))})
const loadAccounts=async()=>{const current=++accountRequestId;accountOptions.value=[];if(!form.projectId||!form.personId)return;accountLoading.value=true;try{const result=await ops.getAccounts({projectId:form.projectId,personId:form.personId,assignmentState:'assigned',skip:0,limit:500});if(current===accountRequestId)accountOptions.value=result}catch(error){if(current===accountRequestId)ElMessage.error(error.detail||'加载平台账号失败')}finally{if(current===accountRequestId)accountLoading.value=false}}
const languageChanged=()=>{form.personId='';form.platformAccountId=null;accountOptions.value=[]}
const personChanged=async()=>{form.platformAccountId=null;await loadAccounts()}
const openEditor=async(row=null)=>{let project=row?projects.value.find(item=>item.id===row.projectId):activeProject.value||selectedProject.value;if(!project)return ElMessage.warning('请先选择标注项目');try{project=await projectApi.getAnnotationProject(project.id);activeProject.value=project}catch(error){return ElMessage.error(error.detail||'加载项目详情失败')}Object.assign(form,emptyForm(),row||{},{projectId:project.id});if(!form.languageItemId&&project.languageItems?.length===1)form.languageItemId=project.languageItems[0].id;editorFields.value=await ops.getCustomFields('trial',project.id);editorVisible.value=true;await loadAccounts()}
const onEditorOpened=async()=>{await nextTick();editorBodyRef.value?.closest('.el-dialog__body')?.scrollTo({top:0,behavior:'auto'})}
const resetEditor=()=>{Object.assign(form,emptyForm());formRef.value?.clearValidate();clearFieldSearch()}
const save=async()=>{const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return;saving.value=true;try{const{id,...payload}=form;id?await ops.updateTrial(id,payload):await ops.createTrial(payload);editorVisible.value=false;ElMessage.success('试标/试采候选记录已保存');await Promise.all([fetchRows(),activeProject.value?.id?loadWorkspaceContext():Promise.resolve()])}catch(error){ElMessage.error(error.detail||'保存失败')}finally{saving.value=false}}

const followUpVisible=ref(false),followUpLoading=ref(false),followUpSaving=ref(false),activeTrial=ref(null),followUpRows=ref([])
const followUpForm=reactive({followUpType:'contact',content:'',nextFollowUpAt:null})
const openFollowUps=async row=>{activeTrial.value=row;followUpVisible.value=true;followUpLoading.value=true;try{followUpRows.value=await ops.getTrialFollowUps(row.id)}catch(error){ElMessage.error(error.detail||'加载跟进记录失败')}finally{followUpLoading.value=false}}
const saveFollowUp=async()=>{if(!followUpForm.content.trim())return ElMessage.warning('请填写跟进内容');followUpSaving.value=true;try{await ops.createTrialFollowUp(activeTrial.value.id,{...followUpForm,content:followUpForm.content.trim()});Object.assign(followUpForm,{followUpType:'contact',content:'',nextFollowUpAt:null});followUpRows.value=await ops.getTrialFollowUps(activeTrial.value.id);await fetchRows();ElMessage.success('跟进记录已添加')}catch(error){ElMessage.error(error.detail||'添加跟进失败')}finally{followUpSaving.value=false}}
const openAccounts=row=>router.push({name:'AnnotationProjectDetails',query:{section:'accounts',projectId:row.projectId,personId:row.personId,view:'project'}})

const quickTalentVisible=ref(false),quickTalentSaving=ref(false),quickTalentFormRef=ref(null),quickTalentForm=reactive({fullName:'',primaryPhone:'',primaryEmail:'',languageId:''})
const quickTalentRules={fullName:[{required:true,message:'请填写姓名',trigger:'blur'}],languageId:[{required:true,message:'请选择掌握语种',trigger:'change'}]}
const quickLanguageOptions=computed(()=>{const item=selectedLanguageItem.value;if(!item)return[];return[{id:item.sourceLanguageId,label:item.sourceLanguageLabel},...(item.targetLanguageId?[{id:item.targetLanguageId,label:item.targetLanguageLabel}]:[])]})
const openQuickTalent=()=>{Object.assign(quickTalentForm,{fullName:'',primaryPhone:'',primaryEmail:'',languageId:quickLanguageOptions.value[0]?.id||''});quickTalentVisible.value=true}
const saveQuickTalent=async()=>{const valid=await quickTalentFormRef.value?.validate().catch(()=>false);if(!valid)return;quickTalentSaving.value=true;try{const saved=await talentApi.createTalent({fullName:quickTalentForm.fullName.trim(),primaryPhone:quickTalentForm.primaryPhone.trim()||null,primaryEmail:quickTalentForm.primaryEmail.trim()||null,status:'standby',capabilities:[{capabilityType:'annotation',status:'active'}],annotationLanguageSkills:[{sourceLanguageId:quickTalentForm.languageId,targetLanguageId:null}]});talents.value=await talentApi.getProjectTalentOptions('annotation');form.personId=saved.id;quickTalentVisible.value=false;await loadAccounts();ElMessage.success(`已创建人才档案 ${saved.resourceCode||''}`)}catch(error){ElMessage.error(error.detail||'快速新增人才失败')}finally{quickTalentSaving.value=false}}

const comparisonVisible=ref(false),comparisonLoading=ref(false),comparisonLanguageItemId=ref(''),comparisonRows=ref([])
const openComparison=()=>{comparisonLanguageItemId.value=activeProject.value?.languageItems?.[0]?.id||'';comparisonVisible.value=true;loadComparison()}
const loadComparison=async()=>{if(!comparisonLanguageItemId.value)return;comparisonLoading.value=true;try{const candidates=await ops.getTrials(activeProject.value.id,{languageItemId:comparisonLanguageItemId.value,skip:0,limit:500});const ids=[...new Set(candidates.map(item=>item.personId))].slice(0,50);const details=await Promise.allSettled(ids.map(id=>talentApi.getTalent(id)));comparisonRows.value=details.filter(item=>item.status==='fulfilled').map(item=>item.value)}catch(error){ElMessage.error(error.detail||'加载资源比较失败')}finally{comparisonLoading.value=false}}
const languageSkillsText=(row,role)=>(row.languageSkills||[]).filter(item=>item.role===role).map(item=>item.languageLabel||item.languageName).filter(Boolean).join('、')||'-'
const educationText=row=>{const item=(row.educationExperiences||[]).find(value=>value.educationLevel==='bachelor')||row.educationExperiences?.[0];return item?[item.schoolName||item.school,item.major].filter(Boolean).join(' · ')||'-':'-'}
const projectSituationText=row=>row.projectSituation?.primary?.projectName?`${row.projectSituation.primary.projectName}${row.projectSituation.total>1?` +${row.projectSituation.total-1}`:''}`:'-'

const applyRoute=async()=>{const nextProjectId=String(route.query.projectId||'');filters.personId=String(route.query.personId||'');if(nextProjectId){projectId.value=nextProjectId;await search();if(route.query.section==='trials')await openWorkspaceById()}}
onMounted(async()=>{try{const[projectRows,talentRows]=await Promise.all([projectApi.getAnnotationProjects({skip:0,limit:500}),talentApi.getProjectTalentOptions('annotation')]);projects.value=projectRows||[];talents.value=talentRows||[];await applyRoute();if(!route.query.projectId)await fetchRows()}catch(error){ElMessage.error(error.detail||'加载试标/试采基础数据失败')}})
watch(()=>[route.query.projectId,route.query.personId],async([nextProject,nextPerson],[previousProject,previousPerson])=>{if(nextProject===previousProject&&nextPerson===previousPerson)return;projectId.value=String(nextProject||'');filters.personId=String(nextPerson||'');filters.languageItemId='';await search()})
onBeforeUnmount(()=>{clearTimeout(searchTimer);requestController?.abort()})
</script>

<style scoped>
.card-header,.header-actions,.trial-search-toolbar,.workspace-summary-toolbar,.workspace-dialog-header,.workspace-header-actions,.workspace-title,.inline-control,.comparison-toolbar{display:flex;align-items:center}
.card-header,.workspace-summary-toolbar,.workspace-dialog-header{justify-content:space-between}
.card-header{gap:16px}.card-header h2{margin:0}.card-header p{margin:4px 0 0;color:var(--el-text-color-secondary)}
.header-actions,.trial-search-toolbar,.workspace-header-actions{gap:8px}.trial-search-toolbar{margin-bottom:16px;flex-wrap:wrap}
.project-filter{width:min(380px,calc(100vw - 32px))}.keyword-filter{width:300px}
.filter-count{display:inline-flex;min-width:18px;height:18px;margin-left:5px;padding:0 5px;align-items:center;justify-content:center;border-radius:9px;color:#fff;background:var(--el-color-primary);font-size:11px}
.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-header,.advanced-footer{display:flex;align-items:center;justify-content:space-between}.advanced-header{margin-bottom:12px}.advanced-footer{justify-content:flex-end}
.pagination{justify-content:flex-end;margin-top:16px}.workspace-title{min-width:0;align-items:flex-start;flex-direction:column;gap:3px;cursor:text;user-select:text}.workspace-title span,.summary-note,.workspace-table-heading span{color:var(--el-text-color-secondary);font-size:12px}
.workspace-body{display:grid;gap:14px}.workspace-summary-toolbar{gap:16px}.summary-note{margin-left:10px}
.language-summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.language-summary-card{padding:14px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-extra-light)}.language-summary-card.is-warning{border-color:var(--el-color-danger-light-5);background:var(--el-color-danger-light-9)}
.language-summary-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}.language-summary-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.language-summary-metrics>div{display:flex;flex-direction:column;gap:3px}.language-summary-metrics span{color:var(--el-text-color-secondary);font-size:12px}.language-summary-metrics strong{font-size:18px}.strategy-note{margin-top:10px;padding-top:8px;border-top:1px dashed var(--el-border-color);color:var(--el-text-color-secondary);white-space:pre-wrap}
.workspace-table-heading{display:flex;align-items:center;gap:8px;margin-top:4px}.form-section{margin-bottom:16px;padding:16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.form-section h3{margin:0 0 16px;font-size:16px}.inline-control{width:100%;gap:8px}.form-tip{margin:-6px 0 4px 110px;color:var(--el-text-color-secondary);font-size:12px}
.strategy-editor-row{padding:12px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.strategy-editor-row+.strategy-editor-row{margin-top:12px}.strategy-editor-row h4{margin:0 0 12px}.follow-up-body{max-height:60vh;overflow-y:auto}.follow-up-content{margin:6px 0;white-space:pre-wrap;word-break:break-word}.follow-up-form{padding-top:14px;border-top:1px solid var(--el-border-color-lighter)}.detail-secondary{color:var(--el-text-color-secondary);font-size:12px}.comparison-toolbar{justify-content:flex-end;margin-bottom:12px}
@media(max-width:768px){.card-header,.workspace-summary-toolbar,.workspace-dialog-header{align-items:stretch;flex-direction:column}.header-actions,.workspace-header-actions{flex-wrap:wrap}.project-filter,.keyword-filter{width:100%}.language-summary-metrics{grid-template-columns:repeat(2,1fr)}.form-tip{margin-left:0}}
</style>

<style>
.trial-advanced-popover{max-width:calc(100vw - 32px)!important}
.trial-workspace-dialog,.trial-editor-dialog,.strategy-dialog,.follow-up-dialog,.comparison-dialog{display:flex;max-height:94vh;flex-direction:column;overflow:hidden}.trial-editor-dialog{max-height:90vh}
.trial-workspace-dialog .el-dialog__header,.trial-workspace-dialog .el-dialog__footer,.trial-editor-dialog .el-dialog__header,.trial-editor-dialog .el-dialog__footer,.strategy-dialog .el-dialog__header,.strategy-dialog .el-dialog__footer,.follow-up-dialog .el-dialog__header,.follow-up-dialog .el-dialog__footer,.comparison-dialog .el-dialog__header,.comparison-dialog .el-dialog__footer{flex:none}
.trial-workspace-dialog .el-dialog__body,.trial-editor-dialog .el-dialog__body,.strategy-dialog .el-dialog__body,.follow-up-dialog .el-dialog__body,.comparison-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.trial-workspace-dialog .el-dialog__footer,.trial-editor-dialog .el-dialog__footer,.strategy-dialog .el-dialog__footer,.follow-up-dialog .el-dialog__footer,.comparison-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
.trial-workspace-dialog.is-fullscreen{max-width:none!important;max-height:none!important}.trial-workspace-dialog.is-fullscreen .el-dialog__body{padding-top:12px}
</style>
