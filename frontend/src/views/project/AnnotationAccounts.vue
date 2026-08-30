<template>
  <el-card class="page-card annotation-accounts compact-list-card" :class="{ 'annotation-accounts--focus': viewMode === 'project' }">
    <template #header>
      <div v-if="viewMode === 'project'" class="focus-header card-header">
        <div class="focus-header__title">
          <el-button :disabled="saving || projectDeleting" @click="returnToAssets">返回账号预览</el-button>
          <span class="focus-header__divider" />
          <div class="focus-header__project">
            <el-select :model-value="projectId" filterable :disabled="saving || projectDeleting" placeholder="切换标注项目" @change="switchProjectInSheet">
              <el-option v-for="item in projects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" />
            </el-select>
            <p>项目账号表 · 表格编辑模式</p>
          </div>
        </div>
        <div class="actions header-actions">
          <CustomFieldManager v-if="canWrite && !projectDeleteMode" table-code="account_assignment" :project-id="projectId" button-label="动态字段" scope-hint="字段仅作用于当前项目；固定列不可删除，自定义列停用后历史数据仍会保留。" auto-field-key :disabled="sheetLocked || !projectId" @changed="handleProjectFieldsChanged" />
          <el-button v-if="canWrite && !projectDeleteMode" :disabled="sheetLocked||!effectiveClientId||!projectId||!platforms.length" @click="importVisible=true">导入</el-button>
          <BatchDeleteToolbar v-if="canWrite && !sheetLocked" :active="projectDeleteMode" :selected-count="projectSelectedRows.length" :loading="projectDeleting" @enter="enterProjectDeleteMode" @exit="exitProjectDeleteMode" @confirm="confirmProjectBatchDelete" />
          <el-button v-if="canWrite && !projectDeleteMode" type="primary" :disabled="saving||!effectiveClientId||!platforms.length" @click="addProjectSheetRow">新增账号</el-button>
        </div>
      </div>
      <div v-else class="header card-header">
        <div><h2>标注员账号预览</h2><p>集中查看各客户平台账号、当前分配状态及标注员分配履历</p></div>
        <div class="actions header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" @reset="resetColumns" />
          <el-popover v-if="canWrite" v-model:visible="platformManagerVisible" trigger="click" placement="bottom-end" :width="560" popper-class="platform-manager-popper">
            <template #reference><el-button :disabled="!effectiveClientId">平台管理</el-button></template>
            <div class="platform-manager">
              <div class="panel-title"><strong>客户平台</strong><el-button link type="primary" @click="openPlatform()">新增平台</el-button></div>
              <el-empty v-if="!platforms.length" description="暂无平台" :image-size="70" />
              <div v-for="item in platforms" :key="item.id" class="platform-row">
                <div class="platform-info"><strong>{{ platformName(item) }}</strong><span>{{ item.platformUrl }}</span></div>
                <div class="actions"><el-button link type="primary" @click="openPlatform(item)">编辑</el-button><el-button link type="danger" @click="removePlatform(item)">删除</el-button></div>
              </div>
            </div>
          </el-popover>
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
        </div>
      </div>
    </template>

    <div class="filters" :class="{ 'filters--focus': viewMode === 'project' }">
      <el-select v-if="viewMode === 'assets'" v-model="clientId" :disabled="sheetLocked" filterable remote clearable :loading="clientSearchLoading" :remote-method="searchClients" placeholder="输入客户名称后联想" style="width:260px" @change="changeClient">
        <el-option v-for="item in clients" :key="item.id" :label="item.client_short_name || item.client_name" :value="item.id" />
      </el-select>
      <el-select v-if="viewMode === 'assets'" v-model="projectId" :disabled="sheetLocked" clearable filterable placeholder="选择项目（选择后仍停留账号预览）" style="width:min(420px, calc(100vw - 32px))" @change="projectSelectionChanged">
        <el-option v-for="item in clientProjects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" />
      </el-select>
      <el-tooltip v-if="viewMode === 'assets'" content="请先选择标注项目" :disabled="Boolean(projectId)" placement="top">
        <span><el-button type="primary" :disabled="!projectId" @click="enterProjectSheet">进入项目账号表</el-button></span>
      </el-tooltip>
      <div v-if="viewMode === 'assets'" class="assignment-language-field">
        <el-select v-model="assignmentLanguageItemId" :disabled="sheetLocked||!projectId" clearable filterable placeholder="账号适用语言（选择人员前必选）" style="width:250px">
          <el-option v-for="item in languageItems" :key="item.id" :label="item.display" :value="item.id" />
        </el-select>
        <el-tooltip content="表示该账号在所选项目中用于哪种语言或语言组合，选项来自“标注项目管理”。单语言项目会自动带出，多语言项目需人工选择。" placement="top"><el-icon class="language-help"><QuestionFilled /></el-icon></el-tooltip>
      </div>
      <el-input v-model="keyword" :disabled="sheetLocked" clearable placeholder="平台、编号、姓名或昵称" style="width:280px" @input="onKeyword" @keyup.enter="queryNow" />
      <el-button class="query-button" type="primary" :disabled="sheetLocked" @click="queryNow">查询</el-button><el-button :disabled="sheetLocked" @click="resetFilters">重置</el-button>
      <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="account-advanced-popper">
        <template #reference><el-button :disabled="sheetLocked">高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
        <div class="advanced-panel">
          <div class="advanced-title">高级筛选</div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12"><el-form-item label="平台"><el-select v-model="filters.platformId" clearable style="width:100%" @change="selectionChanged"><el-option v-for="item in platforms" :key="item.id" :label="platformName(item)" :value="item.id" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="分配状态"><el-select v-model="filters.assignmentState" clearable style="width:100%" @change="selectionChanged"><el-option label="已分配" value="assigned" /><el-option label="未分配" value="unassigned" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="账号状态"><el-select v-model="filters.accountStatus" clearable style="width:100%" @change="selectionChanged"><el-option v-for="(label,value) in accountStatusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="语言方向"><el-select v-model="filters.languageItemId" clearable filterable style="width:100%" @change="selectionChanged"><el-option v-for="item in filterLanguageItems" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item></el-col>
          </el-row>
          <div class="advanced-actions"><el-button link type="primary" @click="clearAdvanced">清空高级条件</el-button><el-button @click="advancedVisible=false">关闭</el-button></div>
        </div>
      </el-popover>
    </div>

    <ProjectAccountSpreadsheet
      ref="projectSpreadsheetRef"
      :key="projectSpreadsheetKey"
      v-if="viewMode==='project'"
      focus-mode
      :rows="rows"
      :fields="projectCustomFields"
      :talents="talents"
      :platforms="platforms"
      :users="users"
      :language-items="languageItems"
      :project-id="projectId"
      :current-user-id="currentUserId"
      :project-name="selectedProject?.projectName || selectedProject?.orderNo || '项目账号表'"
      :loading="loading"
      :saving="saving"
      :total-rows="pagination.total"
      :max-rows="PROJECT_SHEET_MAX_ROWS"
      :save-errors="sheetSaveErrors"
      :delete-mode="projectDeleteMode"
      @save="saveProjectSheetChanges"
      @dirty-change="sheetDirtyChanged"
      @selection-change="handleProjectDeleteSelectionChange"
    >
      <template #selected-row-actions="{ row, dirtyCount }">
        <BusinessDetailPopover :row="row" title="项目账号记录详情" :loading="assignmentLoading===row.id" @show="loadAssignments(row)">
          <template #content>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="平台">{{ row.platformName || host(row.platformUrl) }}</el-descriptions-item>
              <el-descriptions-item label="登录账号">{{ row.loginAccount || '-' }}</el-descriptions-item>
              <el-descriptions-item label="密码">{{ row.password || '-' }}</el-descriptions-item>
              <el-descriptions-item label="分配人员">{{ row.personName || '-' }}</el-descriptions-item>
              <el-descriptions-item label="性别">{{ row.personGender || '-' }}</el-descriptions-item>
              <el-descriptions-item label="项目">{{ row.projectName || selectedProject?.projectName || '-' }}</el-descriptions-item>
              <el-descriptions-item label="语言方向" :span="2">{{ row.languageLabels?.join('、') || '-' }}</el-descriptions-item>
              <el-descriptions-item v-for="field in projectCustomFields" :key="field.id" :label="field.fieldLabel" :span="field.dataType==='textarea'?2:1">
                <AnnotationCustomFieldImage v-if="field.dataType==='image'" :model-value="row.assignmentCustomValues?.[field.id]||null" :project-id="projectId" :field-id="field.id" readonly />
                <template v-else>{{ formatValue(row.assignmentCustomValues?.[field.id]) }}</template>
              </el-descriptions-item>
              <el-descriptions-item label="分配履历" :span="2">
                <el-table :data="assignmentCache[row.id] || []" size="small" max-height="260">
                  <el-table-column prop="personName" label="标注员" />
                  <el-table-column prop="projectName" label="项目" />
                  <el-table-column prop="assignedOn" label="分配日期" width="110" />
                  <el-table-column prop="releasedOn" label="释放日期" width="110"><template #default="scope">{{ scope.row.releasedOn || '使用中' }}</template></el-table-column>
                </el-table>
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </BusinessDetailPopover>
        <PrimaryEditButton v-if="canWrite" :disabled="Boolean(dirtyCount)" title="请先保存或放弃表格修改" @click="openAccount(row)" />
      </template>
    </ProjectAccountSpreadsheet>

    <el-table ref="accountTableRef" v-else :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column v-if="viewMode==='assets'" key="asset-index" type="index" label="序号" width="65" />
      <el-table-column v-else key="project-data-number" label="数据编号" min-width="120" fixed="left"><template #default="{row}">{{ projectValue(row,'external_data_no') }}</template></el-table-column>
      <el-table-column v-if="isVisible('platform')" :label="viewMode==='project' ? '平台' : '平台链接'" min-width="180"><template #default="{row}"><span v-if="viewMode==='project'">{{ row.platformName || host(row.platformUrl) }}</span><el-link v-else class="platform-link" type="primary" :href="row.platformUrl" target="_blank" rel="noopener noreferrer" :title="row.platformUrl">{{ row.platformUrl || '-' }}</el-link></template></el-table-column>
      <el-table-column v-if="viewMode==='assets' && isVisible('nickname')" prop="nickname" label="账号昵称" min-width="130"><template #default="{row}">{{ row.nickname || '-' }}</template></el-table-column>
      <el-table-column label="登录账号" min-width="190"><template #default="{row}">{{ row.loginAccount || '-' }}</template></el-table-column>
      <el-table-column label="密码" min-width="150"><template #default="{row}">{{ row.password || '-' }}</template></el-table-column>
      <el-table-column v-if="isVisible('person')" :label="viewMode==='project' ? '分配人员' : '标注员'" min-width="220"><template #default="{row}">
        <el-select
          :model-value="row.personId || ''"
          clearable
          filterable
          allow-create
          default-first-option
          :disabled="inlineSavingId===row.id||(!row.personId&&!assignmentReady(row))"
          :loading="inlineSavingId===row.id"
          :placeholder="assignmentPlaceholder(row)"
          :filter-method="captureTalentKeyword"
          @focus="beginTalentSearch"
          @change="commitInlineTalent(row,$event)"
        >
          <el-option v-for="item in talentsForRow(row)" :key="item.id" :label="talentOptionLabel(item)" :value="item.id" />
        </el-select>
      </template></el-table-column>
      <el-table-column v-if="viewMode==='project'" label="性别" width="90"><template #default="{row}">{{ row.personGender || '-' }}</template></el-table-column>
      <el-table-column v-if="viewMode==='project'" label="质检状态" min-width="120"><template #default="{row}">{{ projectValue(row,'quality_status') }}</template></el-table-column>
      <el-table-column v-if="viewMode==='project'" label="价格" min-width="100"><template #default="{row}">{{ projectValue(row,'price') }}</template></el-table-column>
      <el-table-column v-if="viewMode==='project'" label="错误点/问题" min-width="180" show-overflow-tooltip><template #default="{row}">{{ projectValue(row,'error_feedback') }}</template></el-table-column>
      <el-table-column v-if="viewMode==='project'" label="标红需反馈" min-width="180" show-overflow-tooltip><template #default="{row}">{{ projectValue(row,'highlight_feedback') }}</template></el-table-column>
      <el-table-column v-if="viewMode==='assets' && isVisible('project')" prop="projectName" label="当前项目" min-width="160"><template #default="{row}">{{ row.projectName || '-' }}</template></el-table-column>
      <el-table-column v-if="isVisible('language')" label="语言方向" min-width="160"><template #default="{row}">{{ row.languageLabels?.join('、') || '-' }}</template></el-table-column>
      <el-table-column v-if="viewMode==='assets' && isVisible('accountStatus')" label="账号状态" width="100"><template #default="{row}"><el-tag size="small" :type="statusTag(row.accountStatus)">{{ accountStatusLabels[row.accountStatus] || row.accountStatus }}</el-tag></template></el-table-column>
      <el-table-column v-if="viewMode==='assets' && isVisible('owner')" label="负责人" min-width="120"><template #default="{row}">{{ row.ownerName || '-' }}</template></el-table-column>
      <el-table-column v-if="viewMode==='assets' && isVisible('expiresOn')" prop="expiresOn" label="到期日" width="120"><template #default="{row}">{{ row.expiresOn || '-' }}</template></el-table-column>
      <template v-if="viewMode!=='assets'">
        <el-table-column v-for="field in visibleProjectCustomFields" :key="`assignment-view:${field.id}`" :label="field.fieldLabel" min-width="140" show-overflow-tooltip><template #default="{row}">{{ formatValue(row.assignmentCustomValues?.[field.id]) }}</template></el-table-column>
      </template>
      <el-table-column label="详情" width="90" fixed="right" align="center"><template #default="{row}">
        <BusinessDetailPopover :row="row" title="标注账号详情" :loading="assignmentLoading===row.id" @show="loadAssignments(row)">
          <template #content><el-descriptions :column="2" border size="small">
            <el-descriptions-item label="平台">{{ row.platformName || host(row.platformUrl) }}</el-descriptions-item><el-descriptions-item label="平台链接"><el-link v-if="row.platformUrl" type="primary" :href="row.platformUrl" target="_blank" rel="noopener noreferrer">{{ row.platformUrl }}</el-link><span v-else>-</span></el-descriptions-item>
            <el-descriptions-item label="账号昵称">{{ row.nickname || '-' }}</el-descriptions-item><el-descriptions-item label="账号来源">{{ sourceLabels[row.accountSource] || row.accountSource }}</el-descriptions-item>
            <el-descriptions-item label="登录账号">{{ row.loginAccount || '-' }}</el-descriptions-item><el-descriptions-item label="密码">{{ row.password || '-' }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ row.ownerName || '-' }}</el-descriptions-item><el-descriptions-item label="账号状态">{{ accountStatusLabels[row.accountStatus] || row.accountStatus }}</el-descriptions-item>
            <el-descriptions-item label="标注员">{{ row.personName || '-' }}</el-descriptions-item><el-descriptions-item label="当前项目">{{ row.projectName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="语言方向">{{ row.languageLabels?.join('、') || '-' }}</el-descriptions-item><el-descriptions-item label="分配日期">{{ row.assignedOn || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ row.remarks || '-' }}</el-descriptions-item>
            <el-descriptions-item label="分配履历" :span="2"><el-table :data="assignmentCache[row.id] || []" size="small" max-height="260"><el-table-column prop="personName" label="标注员" /><el-table-column prop="projectName" label="项目" /><el-table-column prop="assignedOn" label="分配日期" width="110" /><el-table-column prop="releasedOn" label="释放日期" width="110"><template #default="scope">{{ scope.row.releasedOn || '使用中' }}</template></el-table-column></el-table></el-descriptions-item>
          </el-descriptions></template>
        </BusinessDetailPopover>
      </template></el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="120" fixed="right" align="center"><template #default="{row}"><PrimaryEditButton @click="openAccount(row)" /></template></el-table-column>
    </el-table>
    <div v-if="viewMode==='assets'" class="pagination"><el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[20,50,100]" layout="total, sizes, prev, pager, next, jumper" @current-change="reload" @size-change="pageSizeChanged" /></div>
  </el-card>

  <el-dialog v-model="platformDialog" :title="platformForm.id ? '编辑平台' : '新增平台'" width="min(680px, calc(100vw - 32px))" top="5vh" class="long-dialog" append-to-body>
    <el-form label-width="100px"><el-form-item label="平台名称"><el-input v-model="platformForm.platformName" /></el-form-item><el-form-item label="平台链接" required><el-input v-model="platformForm.platformUrl" /></el-form-item><el-form-item label="登录说明"><el-input v-model="platformForm.loginNotes" type="textarea" :rows="4" /></el-form-item><el-form-item label="启用"><el-switch v-model="platformForm.isActive" /></el-form-item></el-form>
    <template #footer><el-button @click="platformDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePlatform">保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="accountDialog" title="编辑账号" width="min(880px, calc(100vw - 32px))" top="5vh" class="long-dialog" append-to-body destroy-on-close @closed="cleanupAccountImageDrafts">
    <el-form label-width="110px"><el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="平台" required><el-select v-model="accountForm.platformId" style="width:100%"><el-option v-for="item in platforms" :key="item.id" :label="platformName(item)" :value="item.id" /></el-select></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="账号昵称"><el-input v-model="accountForm.nickname" /></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="登录账号"><el-input v-model="accountForm.loginAccount" autocomplete="off" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="密码"><el-input v-model="accountForm.password" type="text" autocomplete="off" /></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="所属项目"><el-select v-model="accountForm.projectId" clearable filterable style="width:100%" @change="accountFormProjectChanged"><el-option v-for="item in accountFormProjects" :key="item.id" :label="item.projectName || item.orderNo || '未命名'" :value="item.id" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="账号适用语言"><el-select v-model="accountForm.languageItemIds" multiple collapse-tags clearable :disabled="!accountForm.projectId" style="width:100%"><el-option v-for="item in accountFormLanguageItems" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="标注员"><el-select v-model="accountForm.personId" clearable filterable :disabled="!accountForm.personId&&(!accountForm.projectId||!accountForm.languageItemIds.length)" placeholder="选择未分配标注员" style="width:100%" @change="accountFormPersonChanged"><el-option v-for="item in talentsForRow(accountForm)" :key="item.id" :label="talentOptionLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="账号状态"><el-select v-model="accountForm.accountStatus" style="width:100%" :disabled="Boolean(accountForm.personId)"><el-option v-for="(label,value) in accountForm.personId?{assigned:'已分配'}:manualAccountStatusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="注册状态"><el-select v-model="accountForm.registrationStatus" style="width:100%"><el-option v-for="(label,value) in registrationStatusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="账号来源"><el-select v-model="accountForm.accountSource" style="width:100%"><el-option v-for="(label,value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="负责人" required><el-select v-model="accountForm.ownerId" filterable style="width:100%"><el-option v-for="item in users" :key="item.id" :label="userName(item)" :value="item.id" /></el-select></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="到期日"><el-date-picker v-model="accountForm.expiresOn" clearable value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col></el-row>
      <el-form-item label="备注"><el-input v-model="accountForm.remarks" type="textarea" :rows="3" /></el-form-item>
      <template v-if="accountForm.projectId && accountFormCustomFields.length"><el-divider content-position="left">项目账号字段</el-divider><AnnotationCustomFieldInputs ref="assignmentCustomFieldInputs" :fields="accountFormCustomFields" :values="accountForm.assignmentCustomValues" :project-id="accountForm.projectId" /></template>
    </el-form><template #footer><el-button @click="accountDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button></template>
  </el-dialog>

  <AccountImportDialog v-model="importVisible" :client-id="effectiveClientId" :project-id="projectId" :platforms="platforms" :language-items="languageItems" :users="users" :default-language-ids="assignmentLanguageItemId?[assignmentLanguageItemId]:[]" @imported="importCompleted" />

</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import * as clientApi from '@/api/clients'
import * as projectApi from '@/api/annotationProjects'
import * as talentApi from '@/api/talents'
import * as ops from '@/api/annotationOps'
import { getUsers } from '@/api/users'
import AnnotationCustomFieldInputs from '@/components/annotation/AnnotationCustomFieldInputs.vue'
import AnnotationCustomFieldImage from '@/components/annotation/AnnotationCustomFieldImage.vue'
import AccountImportDialog from '@/components/annotation/AccountImportDialog.vue'
import CustomFieldManager from '@/components/annotation/CustomFieldManager.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'

const emit=defineEmits(['focus-mode-change'])
const ProjectAccountSpreadsheet=defineAsyncComponent(()=>import('@/components/annotation/ProjectAccountSpreadsheet.vue'))
const PROJECT_SHEET_MAX_ROWS=500
const canWrite=hasPermission('annotation_accounts:write')

const clients=ref([]),projects=ref([]),platforms=ref([]),rows=ref([]),talents=ref([]),users=ref([]),projectCustomFields=ref([]),projectSpreadsheetRef=ref(null)
const route=useRoute()
const router=useRouter()
const clientId=ref(''),projectId=ref(''),assignmentLanguageItemId=ref(''),keyword=ref(''),loading=ref(false),saving=ref(false),clientSearchLoading=ref(false)
const accountTableRef=ref(null)
const currentUserId=localStorage.getItem('user_id')||''
const advancedVisible=ref(false),platformManagerVisible=ref(false),platformDialog=ref(false),accountDialog=ref(false),importVisible=ref(false),viewMode=ref('assets')
const sheetDirtyCount=ref(0)
const sheetSaveErrors=ref({})
const assignmentCache=reactive({}),assignmentLoading=ref(''),personProfileCache=reactive({}),personProfileLoadingId=ref('')
const occupancy=ref([]),inlineSavingId=ref(''),talentKeyword=ref('')
const pagination=reactive({page:1,limit:20,total:0})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:accountTableRef,pagination,deleteRow:(row)=>ops.deleteAccount(row.id),getLabel:(row)=>row.nickname||row.loginAccount||row.platformName||row.id,reload:()=>reload(),onDeleted:(row)=>{delete assignmentCache[row.id]},entityName:'标注账号'})
const {deleteMode:projectDeleteMode,deleting:projectDeleting,selectedRows:projectSelectedRows,enterDeleteMode:enterProjectDeleteMode,exitDeleteMode:exitProjectDeleteMode,handleDeleteSelectionChange:handleProjectDeleteSelectionChange,confirmBatchDelete:confirmProjectBatchDelete}=useBatchDelete({rows,deleteRow:(row)=>ops.deleteAccount(row.id),getLabel:(row)=>row.nickname||row.loginAccount||row.platformName||row.id,reload:()=>reload(),onDeleted:(row)=>{delete assignmentCache[row.id]},entityName:'项目账号'})
const filters=reactive({platformId:'',assignmentState:'',accountStatus:'',languageItemId:''})
const platformForm=reactive({id:'',clientId:'',platformName:'',platformUrl:'',loginNotes:'',isActive:true})
const accountForm=reactive({id:'',clientId:'',platformId:'',parentAccountId:null,ownerId:currentUserId,nickname:'',loginAccount:'',password:'',accountStatus:'available',registrationStatus:'unregistered',accountSource:'client_provided',expiresOn:null,remarks:'',customValues:{},assignmentCustomValues:{},personId:'',originalPersonId:'',projectId:'',originalProjectId:'',languageItemIds:[]})
const assignmentCustomFieldInputs=ref(null),accountFormCustomFields=ref([])
const accountStatusLabels={available:'可用',assigned:'已分配',suspended:'暂停',banned:'封禁',retired:'已退役'}
const manualAccountStatusLabels={available:'可用',suspended:'暂停',banned:'封禁',retired:'已退役'}
const registrationStatusLabels={unregistered:'未注册',registering:'注册中',registered:'已注册',registration_failed:'注册失败',disabled:'已停用',not_required:'无需注册'}
const sourceLabels={client_provided:'客户提供',self_registered:'自助注册',annotator_owned:'标注员自有'}
const talentStatusLabels={active:'活跃',standby:'待命',inactive:'停用'}
const baseTableColumns=[{key:'platform',label:'平台链接'},{key:'nickname',label:'账号昵称'},{key:'person',label:'标注员'},{key:'project',label:'当前项目'},{key:'language',label:'语言方向'},{key:'accountStatus',label:'账号状态'},{key:'owner',label:'负责人'},{key:'expiresOn',label:'到期日'}]
const assetTableColumns=computed(()=>baseTableColumns)
const projectTableColumns=computed(()=>[
  {key:'platform',label:'平台'},
  {key:'person',label:'分配人员'},
  {key:'language',label:'语言方向'},
  ...projectCustomFields.value.map(item=>({key:`assignment:${item.id}`,label:item.fieldLabel})),
])
const assetDefaults=computed(()=>['platform','nickname','person','language','accountStatus','owner'])
const projectDefaults=computed(()=>['platform','person','language',...projectCustomFields.value.map(item=>`assignment:${item.id}`)])
const projectSpreadsheetKey=computed(()=>`${projectId.value}:${projectCustomFields.value.map(item=>`${item.id}:${item.dataType}:${item.sequenceNo}`).join('|')}`)
const assetColumns=useTableColumns('annotation-account-library-v3',assetTableColumns,assetDefaults)
const projectColumns=useTableColumns('annotation-project-account-sheet-v2',projectTableColumns,projectDefaults)
const tableColumns=computed(()=>viewMode.value==='project'?projectTableColumns.value:assetTableColumns.value)
const visibleColumnKeys=computed({get:()=>viewMode.value==='project'?projectColumns.selectedKeys.value:assetColumns.selectedKeys.value,set:value=>{if(viewMode.value==='project')projectColumns.selectedKeys.value=value;else assetColumns.selectedKeys.value=value}})
const isVisible=key=>(viewMode.value==='project'?projectColumns:assetColumns).isVisible(key)
const resetColumns=()=>{(viewMode.value==='project'?projectColumns:assetColumns).reset()}
const visibleProjectCustomFields=computed(()=>projectCustomFields.value.filter(item=>isVisible(`assignment:${item.id}`)))
const projectField=key=>projectCustomFields.value.find(item=>item.fieldKey===key)
const projectValue=(row,key)=>{const field=projectField(key);return field?formatValue(row.assignmentCustomValues?.[field.id]):'-'}
const clientProjects=computed(()=>clientId.value?projects.value.filter(item=>item.clientId===clientId.value):projects.value)
const selectedProject=computed(()=>projects.value.find(item=>item.id===projectId.value))
const effectiveClientId=computed(()=>clientId.value||selectedProject.value?.clientId||'')
const languageItems=computed(()=>selectedProject.value?.languageItems||clientProjects.value.flatMap(item=>item.languageItems||[]))
const filterLanguageItems=computed(()=>selectedProject.value?.languageItems||clientProjects.value.flatMap(item=>item.languageItems||[]))
const accountFormProjects=computed(()=>accountForm.clientId?projects.value.filter(item=>item.clientId===accountForm.clientId):projects.value)
const accountFormLanguageItems=computed(()=>projects.value.find(item=>item.id===accountForm.projectId)?.languageItems||[])
const filteredTalents=computed(()=>{const keyword=talentKeyword.value.trim().toLocaleLowerCase();return keyword?talents.value.filter(item=>talentOptionLabel(item).toLocaleLowerCase().includes(keyword)):talents.value})
const advancedCount=computed(()=>Object.values(filters).filter(Boolean).length)
const sheetLocked=computed(()=>viewMode.value==='project'&&sheetDirtyCount.value>0)
let timer,controller,requestId=0,clientSearchTimer,clientSearchController,clientSearchRequestId=0
const host=url=>{try{return new URL(url).hostname}catch{return url||'未命名平台'}}
const platformName=item=>item.platformName||host(item.platformUrl)
const talentOptionLabel=item=>talentName(item)
const userName=item=>item.full_name||item.fullName||item.username||'-'
const formatValue=value=>Array.isArray(value)?value.join('、')||'-':value===true?'是':value===false?'否':value===null||value===undefined||value===''?'-':value
const show=value=>value===null||value===undefined||value===''?'-':Array.isArray(value)?value.join('、')||'-':value
const statusTag=value=>({available:'success',assigned:'primary',suspended:'warning',banned:'danger',retired:'info'}[value]||'info')
const importCompleted=async()=>{await Promise.all([loadProjectFields(),reload()])}
const addProjectSheetRow=()=>projectSpreadsheetRef.value?.focusNewRow()
const saveProjectSheetChanges=async changes=>{
  if(!changes.length)return
  sheetSaveErrors.value={}
  saving.value=true
  try{
    const response=await ops.batchSaveAccounts({clientId:effectiveClientId.value,rows:changes.map(({original,account,personId,languageItemIds,assignmentCustomValues,rowIndex})=>({
      rowKey:`project-sheet-${rowIndex}`,
      id:original?.id||null,
      account,
      personId:personId||null,projectId:projectId.value,languageItemIds,
      assignmentCustomValues,
    }))})
    const failed=(response.results||[]).filter(item=>!item.success)
    projectSpreadsheetRef.value?.applySaveResults?.(response.results||[])
    sheetSaveErrors.value=Object.fromEntries(failed.map(item=>[Number(String(item.rowKey||'').replace('project-sheet-','')),item.error||'保存失败']))
    if(failed.length)ElMessage.warning(`已保存 ${(response.results||[]).length-failed.length} 行，${failed.length} 行失败：${failed[0].error||'请检查数据'}`)
    else ElMessage.success(`已保存 ${changes.length} 行项目账号记录`)
    if(!failed.length)await reload()
  }catch(error){ElMessage.error(error.detail||error.message||'保存项目账号表失败')}
  finally{saving.value=false}
}
const sheetDirtyChanged=count=>{sheetDirtyCount.value=count;if(count)advancedVisible.value=false;else sheetSaveErrors.value={}}
// 项目既是进入“项目账号表”的上下文，也是账号预览的常用筛选条件。
// 选择项目后即使仍停留在预览视图，也必须把 projectId 传给列表和总数接口。
const buildFilters=()=>({clientId:clientId.value||undefined,keyword:keyword.value.trim()||undefined,...Object.fromEntries(Object.entries(filters).map(([key,value])=>[key,value||undefined])),projectId:projectId.value||undefined})
const loadProjectFields=async()=>{projectCustomFields.value=projectId.value?await ops.getCustomFields('account_assignment',projectId.value):[];const userKey=localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous';if(projectId.value&&!localStorage.getItem(`table-columns:annotation-project-account-sheet-v2:${userKey}`))projectColumns.reset()}
const handleProjectFieldsChanged=async()=>{await loadProjectFields();await nextTick();await projectSpreadsheetRef.value?.refreshColumns?.()}
const loadOccupancy=async()=>{occupancy.value=await ops.getAnnotatorOccupancy()}
const reload=async()=>{clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++requestId;loading.value=true;const query=buildFilters();const projectSheet=viewMode.value==='project';const skip=projectSheet?0:(pagination.page-1)*pagination.limit;const limit=projectSheet?PROJECT_SHEET_MAX_ROWS:pagination.limit;try{const [data,count]=await Promise.all([ops.getAccounts({skip,limit,...query},{signal:controller.signal}),ops.getAccountCount(query,{signal:controller.signal})]);if(current!==requestId)return;rows.value=Array.isArray(data)?data:[];pagination.total=count?.total||0;await loadOccupancy()}catch(error){if(current!==requestId||error?.code==='ERR_CANCELED')return;ElMessage.error(error.detail||'加载账号失败')}finally{if(current===requestId)loading.value=false}}
const loadPlatforms=async()=>{platforms.value=effectiveClientId.value?await ops.getPlatforms(effectiveClientId.value,{skip:0,limit:500}):[]}
const searchClients=query=>{
  clearTimeout(clientSearchTimer)
  clientSearchController?.abort()
  const current=++clientSearchRequestId
  const keyword=String(query||'').trim()
  if(!keyword){clients.value=[];clientSearchLoading.value=false;return}
  clientSearchTimer=setTimeout(async()=>{
    clientSearchController=new AbortController()
    clientSearchLoading.value=true
    try{
      const data=await clientApi.getClients({skip:0,limit:20,client_name:keyword},{signal:clientSearchController.signal})
      if(current===clientSearchRequestId)clients.value=Array.isArray(data)?data:[]
    }catch(error){
      if(current===clientSearchRequestId&&error?.code!=='ERR_CANCELED')ElMessage.error(error.detail||'搜索客户失败')
    }finally{
      if(current===clientSearchRequestId)clientSearchLoading.value=false
    }
  },400)
}
const queryNow=()=>{pagination.page=1;reload()}
const onKeyword=value=>{clearTimeout(timer);if(!value)return queryNow();timer=setTimeout(queryNow,400)}
const selectionChanged=()=>queryNow()
const syncAssignmentLanguage=()=>{
  const items=projects.value.find(item=>item.id===projectId.value)?.languageItems||[]
  assignmentLanguageItemId.value=items.length===1?items[0].id:''
}
const accountRouteQuery=(nextView=viewMode.value,nextProjectId=projectId.value)=>{
  const query={...route.query,section:'accounts'}
  if(nextProjectId)query.projectId=nextProjectId
  else delete query.projectId
  if(nextView==='project'&&nextProjectId)query.view='project'
  else delete query.view
  return query
}
const replaceAccountRoute=(nextView,nextProjectId)=>router.replace({name:'AnnotationProjectDetails',query:accountRouteQuery(nextView,nextProjectId)})
const projectSelectionChanged=async()=>{filters.languageItemId='';syncAssignmentLanguage();viewMode.value='assets';pagination.page=1;await Promise.all([loadPlatforms(),loadProjectFields()]);await reload();await replaceAccountRoute('assets',projectId.value)}
const enterProjectSheet=()=>{
  if(!projectId.value)return ElMessage.warning('请先选择标注项目')
  return replaceAccountRoute('project',projectId.value)
}
const switchProjectInSheet=async nextProjectId=>{
  if(!nextProjectId||nextProjectId===projectId.value)return
  const nextProject=projects.value.find(item=>item.id===nextProjectId)
  if(!nextProject)return ElMessage.error('未找到所选标注项目')
  await replaceAccountRoute('project',nextProject.id)
}
const returnToAssets=()=>replaceAccountRoute('assets',projectId.value)
const clearAdvanced=()=>{Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});queryNow()}
const changeClient=async()=>{projectId.value='';assignmentLanguageItemId.value='';viewMode.value='assets';projectCustomFields.value=[];Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});pagination.page=1;await loadPlatforms();await reload();await replaceAccountRoute('assets','')}
const resetFilters=async()=>{clientId.value='';clients.value=[];projectId.value='';assignmentLanguageItemId.value='';viewMode.value='assets';projectCustomFields.value=[];keyword.value='';Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});await loadPlatforms();queryNow();await replaceAccountRoute('assets','')}
const pageSizeChanged=()=>{pagination.page=1;reload()}
const talentName=item=>`${item.resourceCode||''} ${item.fullName||item.personName||''}`.trim()
const beginTalentSearch=()=>{talentKeyword.value=''}
const captureTalentKeyword=value=>{talentKeyword.value=value||''}
const assignmentContext=row=>{
  if(!row)return{projectId:'',languageItemIds:[]}
  const contextProjectId=row.personId&&row.projectId?row.projectId:(row.projectId||projectId.value)
  const project=projects.value.find(item=>item.id===contextProjectId)
  let languageItemIds=row.personId&&row.languageItemIds?.length?[...row.languageItemIds]:[]
  if(!languageItemIds.length&&assignmentLanguageItemId.value)languageItemIds=[assignmentLanguageItemId.value]
  if(!languageItemIds.length&&(project?.languageItems||[]).length===1)languageItemIds=[project.languageItems[0].id]
  return{projectId:contextProjectId,languageItemIds}
}
const languageSkillKey=item=>`${item.sourceLanguageId||''}:${item.targetLanguageId||''}`
const contextLanguageItems=row=>{
  const context=assignmentContext(row)
  const project=projects.value.find(item=>item.id===context.projectId)
  const selected=new Set(context.languageItemIds)
  return (project?.languageItems||[]).filter(item=>selected.has(item.id))
}
const isTalentEligible=(talent,row)=>{
  const selected=contextLanguageItems(row)
  if(!selected.length)return true
  const skills=new Set((talent.annotationLanguageSkills||[]).map(languageSkillKey))
  return selected.every(item=>skills.has(languageSkillKey(item)))
}
const talentsForRow=row=>filteredTalents.value.filter(item=>item.id===row.personId||(!isTalentOccupied(item,row)&&isTalentEligible(item,row)))
const isTalentOccupied=(talent,row)=>{
  return occupancy.value.some(item=>item.personId===talent.id&&item.accountId!==row.id)
}
const assignmentReady=row=>{const context=assignmentContext(row);return Boolean(context.projectId&&context.languageItemIds.length)}
const assignmentPlaceholder=row=>{
  if(row.personId)return '选择其他未分配人员，或清空解除绑定'
  if(!assignmentContext(row).projectId)return '请先选择分配项目'
  if(!assignmentContext(row).languageItemIds.length)return '请先选择账号适用语言'
  return '选择未分配人员，或输入新姓名后回车新增'
}
const accountBatchPayload=(row,personId,context)=>({
  clientId:row.clientId||effectiveClientId.value,
  rows:[{
    rowKey:row.id,
    id:row.id,
    account:{platformId:row.platformId,parentAccountId:row.parentAccountId||null,ownerId:row.ownerId||currentUserId||null,nickname:row.nickname||null,loginAccount:row.loginAccount||null,password:row.password||null,accountStatus:personId?'assigned':(row.accountStatus==='assigned'?'available':row.accountStatus),registrationStatus:row.registrationStatus,accountSource:row.accountSource,expiresOn:row.expiresOn||null,remarks:row.remarks||null,sequenceNo:row.sequenceNo||null,customValues:row.customValues||{}},
    personId:personId||null,
    projectId:context.projectId||null,
    languageItemIds:context.projectId?context.languageItemIds:[],
    assignmentCustomValues:row.assignmentCustomValues||{},
  }],
})
const syncAccountOccupancy=(accountId,personId,context)=>{
  occupancy.value=occupancy.value.filter(item=>item.accountId!==accountId)
  if(!personId)return
  occupancy.value.push(...context.languageItemIds.map(languageItemId=>({
    accountId,personId,projectId:context.projectId,languageItemId,
  })))
}
const inlinePersonChanged=async(row,personId)=>{
  const context=assignmentContext(row)
  if(personId&&(!context.projectId||!context.languageItemIds.length))return ElMessage.warning('请先在上方选择分配项目和账号适用语言')
  const talent=talents.value.find(item=>item.id===personId)
  if(personId&&(!isTalentEligible(talent,row)||isTalentOccupied(talent,row)))return ElMessage.warning('该标注员不具备当前语言能力，或已绑定其他有效账号')
  inlineSavingId.value=row.id
  try{
    const response=await ops.batchSaveAccounts(accountBatchPayload(row,personId,context))
    const result=response.results?.[0]
    if(!result?.success)throw new Error(result?.error||'绑定失败')
    Object.assign(row,result.account)
    syncAccountOccupancy(row.id,personId,context)
    delete assignmentCache[row.id]
    ElMessage.success(personId?'标注员已绑定':'已解除标注员绑定')
    await reload()
  }catch(error){ElMessage.error(error.detail||error.message||'绑定失败')}finally{inlineSavingId.value=''}
}
const exactTalentMatch=value=>{
  const normalized=String(value||'').trim().toLocaleLowerCase()
  if(!normalized)return null
  const matches=talents.value.filter(item=>[item.fullName,item.personName,item.resourceCode,talentName(item)].some(candidate=>String(candidate||'').trim().toLocaleLowerCase()===normalized))
  return matches.length===1?matches[0]:null
}
const createInlineTalent=async(row,fullName)=>{
  const context=assignmentContext(row)
  if(!context.projectId||!context.languageItemIds.length)return ElMessage.warning('请先在上方选择分配项目和账号适用语言')
  const skillMap=new Map(contextLanguageItems(row).map(item=>[languageSkillKey(item),{sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.targetLanguageId||null}]))
  if(!skillMap.size)return ElMessage.warning('当前项目没有可用的语言方向')
  inlineSavingId.value=row.id
  try{
    const created=await talentApi.createTalent({fullName,status:'standby',capabilities:[{capabilityType:'annotation',status:'active'}],annotationProfile:{},annotationLanguageSkills:[...skillMap.values()]})
    talents.value.push(created)
    talentKeyword.value=''
    await inlinePersonChanged(row,created.id)
  }catch(error){ElMessage.error(error.detail?.message||error.detail||'新增标注员失败')}finally{if(inlineSavingId.value===row.id)inlineSavingId.value=''}
}
const renameInlineTalent=async(row,fullName)=>{
  const current=talents.value.find(item=>item.id===row.personId)
  if(!current)return ElMessage.error('当前标注员不存在，请刷新后重试')
  if(current.fullName===fullName)return
  inlineSavingId.value=row.id
  try{
    const updated=await talentApi.patchTalentName(current.id,fullName)
    const index=talents.value.findIndex(item=>item.id===current.id)
    if(index>=0)talents.value.splice(index,1,{...talents.value[index],...updated})
    talentKeyword.value=''
    ElMessage.success('标注员姓名已修改')
    await reload()
  }catch(error){ElMessage.error(error.detail?.message||error.detail||'修改标注员姓名失败')}finally{inlineSavingId.value=''}
}
const commitInlineTalent=async(row,value)=>{
  const selected=talents.value.find(item=>item.id===value)
  if(!value||selected){talentKeyword.value='';return inlinePersonChanged(row,value)}
  const fullName=String(value).trim()
  if(!fullName)return
  if(row.personId)return renameInlineTalent(row,fullName)
  const matched=exactTalentMatch(fullName)
  if(matched)return inlinePersonChanged(row,matched.id)
  return createInlineTalent(row,fullName)
}
const draftPersonError=row=>{
  if(!row.personId)return ''
  const context=assignmentContext(row)
  if(!context.projectId||!context.languageItemIds.length)return '请先设置分配项目和账号适用语言'
  const talent=talents.value.find(item=>item.id===row.personId)
  if(!talent)return '所选标注员不存在'
  if(!isTalentEligible(talent,row))return '该标注员不具备当前语言方向能力'
  if(isTalentOccupied(talent,row))return '该标注员已绑定其他有效账号'
  return ''
}
const discardDrafts=async()=>{
  const unsavedCount=sheetDirtyCount.value
  if(unsavedCount){
    try{await ElMessageBox.confirm(`还有 ${unsavedCount} 行未保存，确定放弃这些修改？`,'未保存修改',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return false}
  }
  return true
}
const openPlatform=row=>{Object.assign(platformForm,{id:row?.id||'',clientId:effectiveClientId.value,platformName:row?.platformName||'',platformUrl:row?.platformUrl||'',loginNotes:row?.loginNotes||'',isActive:row?.isActive??true});platformDialog.value=true}
const savePlatform=async()=>{if(!platformForm.platformUrl.trim())return ElMessage.warning('请输入平台链接');saving.value=true;try{platformForm.id?await ops.updatePlatform(platformForm.id,platformForm):await ops.createPlatform(platformForm);platformDialog.value=false;ElMessage.success('平台已保存');await loadPlatforms();await reload()}catch(error){ElMessage.error(error.detail||'保存失败')}finally{saving.value=false}}
const removePlatform=async row=>{try{await ElMessageBox.confirm(`删除平台“${platformName(row)}”及其全部账号？`,'确认删除');await ops.deletePlatform(row.id);await loadPlatforms();await reload()}catch(error){if(!['cancel','close'].includes(error))ElMessage.error(error.detail||'删除失败')}}
const openAccount=async row=>{
  const resolvedProjectId=row.projectId||projectId.value||''
  try{
    const [platformRows,fieldRows]=await Promise.all([
      row.clientId?ops.getPlatforms(row.clientId,{skip:0,limit:500}):[],
      resolvedProjectId?ops.getCustomFields('account_assignment',resolvedProjectId):[],
    ])
    platforms.value=platformRows
    accountFormCustomFields.value=fieldRows
  }catch(error){return ElMessage.error(error.detail||'加载账号编辑数据失败')}
  const project=projects.value.find(item=>item.id===resolvedProjectId)
  const resolvedLanguages=row.languageItemIds?.length?[...row.languageItemIds]:(assignmentLanguageItemId.value?[assignmentLanguageItemId.value]:((project?.languageItems||[]).length===1?[project.languageItems[0].id]:[]))
  Object.assign(accountForm,{id:row.id,clientId:row.clientId||'',platformId:row.platformId,parentAccountId:row.parentAccountId||null,ownerId:row.ownerId||currentUserId,nickname:row.nickname||'',loginAccount:row.loginAccount||'',password:row.password||'',accountStatus:row.accountStatus||'available',registrationStatus:row.registrationStatus||'unregistered',accountSource:row.accountSource||'client_provided',expiresOn:row.expiresOn||null,remarks:row.remarks||'',customValues:{...(row.customValues||{})},assignmentCustomValues:{...(row.assignmentCustomValues||{})},personId:row.personId||'',originalPersonId:row.personId||'',projectId:resolvedProjectId,originalProjectId:row.projectId||'',languageItemIds:resolvedLanguages})
  accountDialog.value=true
}
const accountFormProjectChanged=async()=>{
  await assignmentCustomFieldInputs.value?.cleanupPending?.()
  accountForm.assignmentCustomValues={}
  try{accountFormCustomFields.value=accountForm.projectId?await ops.getCustomFields('account_assignment',accountForm.projectId):[]}
  catch(error){accountFormCustomFields.value=[];ElMessage.error(error.detail||'加载项目账号字段失败')}
  const items=accountFormLanguageItems.value
  accountForm.languageItemIds=items.length===1?[items[0].id]:[]
}
const accountFormPersonChanged=()=>{accountForm.accountStatus=accountForm.personId?'assigned':'available'}
const cleanupAccountImageDrafts=()=>assignmentCustomFieldInputs.value?.cleanupPending?.()
const saveAccount=async()=>{
  if(!accountForm.platformId)return ElMessage.warning('请选择平台')
  if(!accountForm.ownerId)return ElMessage.warning('请选择负责人')
  if(Boolean(accountForm.loginAccount)!==Boolean(accountForm.password)&&!accountForm.id)return ElMessage.warning('登录账号和密码必须同时填写')
  if(accountForm.personId&&(!accountForm.projectId||!accountForm.languageItemIds.length))return ElMessage.warning('当前账号缺少项目或语言方向，无法保存标注员绑定')
  if(accountForm.personId){const error=draftPersonError(accountForm);if(error)return ElMessage.warning(error)}
  saving.value=true
  try{
    const {clientId:formClientId,personId,originalPersonId,projectId:formProjectId,originalProjectId,languageItemIds,assignmentCustomValues,...formAccount}=accountForm
    const account={...formAccount,loginAccount:accountForm.loginAccount||null,password:accountForm.password||null,accountStatus:personId?'assigned':accountForm.accountStatus}
    const usesBatchSave=Boolean(personId||originalPersonId||formProjectId||originalProjectId||languageItemIds.length)
    if(usesBatchSave){
      const response=await ops.batchSaveAccounts({clientId:formClientId||effectiveClientId.value,rows:[{rowKey:accountForm.id,id:accountForm.id,account,personId:personId||null,projectId:formProjectId||null,languageItemIds,assignmentCustomValues}]})
      const result=response.results?.[0]
      if(!result?.success)throw new Error(result?.error||'账号绑定保存失败')
    }else await ops.updateAccount(accountForm.id,account)
    assignmentCustomFieldInputs.value?.markSaved?.()
    accountDialog.value=false;ElMessage.success('账号已保存');await reload()
  }catch(error){ElMessage.error(error.detail||error.message||'保存失败')}finally{saving.value=false}
}
const loadAssignments=async row=>{if(assignmentCache[row.id])return;assignmentLoading.value=row.id;try{assignmentCache[row.id]=await ops.getAccountAssignments(row.id)}catch(error){ElMessage.error(error.detail||'加载分配履历失败')}finally{assignmentLoading.value=''}}
const loadPersonProfile=async personId=>{if(personProfileCache[personId])return;personProfileLoadingId.value=personId;try{personProfileCache[personId]=await ops.getAccountPersonProfile(personId)}catch(error){ElMessage.error(error.detail||'加载标注员信息失败')}finally{personProfileLoadingId.value=''}}
const beforeUnload=event=>{if(!sheetDirtyCount.value)return;event.preventDefault();event.returnValue=''}
let routeContextReady=false
const applyRouteContext=async(query,{force=false}={})=>{
  if(query.section&&query.section!=='accounts')return
  const requestedProjectId=String(query.projectId||'')
  const requestedView=query.view==='project'?'project':'assets'
  const routeProject=requestedProjectId?projects.value.find(item=>String(item.id)===requestedProjectId):null
  if(requestedProjectId&&!routeProject){
    projectId.value=''
    viewMode.value='assets'
    assignmentLanguageItemId.value=''
    projectCustomFields.value=[]
    ElMessage.warning('未找到指定的标注项目，已返回账号预览')
    await replaceAccountRoute('assets','')
    await reload()
    return
  }
  if(requestedView==='project'&&!routeProject){
    viewMode.value='assets'
    ElMessage.warning('请先选择标注项目')
    await replaceAccountRoute('assets','')
    await reload()
    return
  }
  if(!force&&String(projectId.value||'')===requestedProjectId&&viewMode.value===requestedView)return
  const projectChanged=String(projectId.value||'')!==requestedProjectId
  exitProjectDeleteMode()
  if(routeProject){
    projectId.value=routeProject.id
    clientId.value=routeProject.clientId||''
    if(routeProject.clientId){
      try{const client=await clientApi.getClient(routeProject.clientId);clients.value=client?[client]:[]}
      catch(error){ElMessage.error(error.detail||'加载项目客户失败')}
    }
  }else{
    projectId.value=''
    assignmentLanguageItemId.value=''
    projectCustomFields.value=[]
  }
  viewMode.value=requestedView
  if(projectChanged){
    keyword.value=''
    Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''})
    sheetSaveErrors.value={}
  }
  syncAssignmentLanguage()
  pagination.page=1
  await Promise.all([loadPlatforms(),loadProjectFields()])
  await reload()
}
onBeforeRouteUpdate(async to=>{
  if(!sheetDirtyCount.value)return true
  const nextProjectId=String(to.query.projectId||'')
  const nextView=to.query.section==='accounts'&&to.query.view==='project'?'project':'assets'
  if(nextProjectId===String(projectId.value||'')&&nextView===viewMode.value)return true
  return await discardDrafts()
})
onBeforeRouteLeave(async()=>await discardDrafts())
watch(viewMode,value=>emit('focus-mode-change',value==='project'),{immediate:true})
watch(()=>[route.query.section,route.query.projectId,route.query.view],()=>{if(routeContextReady&&route.query.section==='accounts')void applyRouteContext(route.query)})
onActivated(()=>{emit('focus-mode-change',viewMode.value==='project');if(routeContextReady&&route.query.section==='accounts')void applyRouteContext(route.query)})
onDeactivated(()=>emit('focus-mode-change',false))
onMounted(async()=>{const results=await Promise.allSettled([projectApi.getAnnotationProjects({skip:0,limit:500}),talentApi.getProjectTalentOptions('annotation'),getUsers({skip:0,limit:500})]);projects.value=results[0].status==='fulfilled'?results[0].value:[];talents.value=results[1].status==='fulfilled'?results[1].value:[];users.value=results[2].status==='fulfilled'&&Array.isArray(results[2].value)?results[2].value:[];routeContextReady=true;await applyRouteContext(route.query,{force:true})})
onMounted(()=>window.addEventListener('beforeunload',beforeUnload))
onBeforeUnmount(()=>{emit('focus-mode-change',false);clearTimeout(timer);clearTimeout(clientSearchTimer);controller?.abort();clientSearchController?.abort();window.removeEventListener('beforeunload',beforeUnload)})
</script>

<style scoped>
.header>.actions,.focus-header>.actions{flex-wrap:wrap;justify-content:flex-end}
.focus-header,.focus-header__title{display:flex;align-items:center}.focus-header{justify-content:space-between;gap:12px}.focus-header__title{min-width:0;gap:10px}.focus-header__project{display:flex;align-items:center;gap:8px;width:min(620px,48vw);min-width:420px}.focus-header__project .el-select{flex:1;min-width:0}.focus-header__title p{flex:none;margin:0;color:var(--el-text-color-secondary);font-size:12px;white-space:nowrap}.focus-header__divider{width:1px;height:28px;background:var(--el-border-color)}
.annotation-accounts--focus{display:flex;height:calc(100vh - 112px);min-height:0;flex-direction:column}.annotation-accounts--focus :deep(.el-card__header){flex:none;padding:6px 12px}.annotation-accounts--focus :deep(.el-card__body){display:flex;flex:1;min-height:0;overflow:hidden;flex-direction:column;padding:6px 10px 10px}.annotation-accounts--focus .filters--focus{flex:none;margin-bottom:4px}.annotation-accounts--focus .filters--focus .query-button{height:30px;min-height:30px;padding:5px 11px;font-size:13px;line-height:13px}.filters--focus .el-input{flex:1;max-width:520px}.annotation-accounts--focus .project-spreadsheet{flex:1;min-height:0}
.header,.actions,.filters,.panel-title,.platform-row,.advanced-actions,.assignment-language-field{display:flex;align-items:center}.header,.panel-title,.platform-row,.advanced-actions{justify-content:space-between}.header h2{margin:0}.header p{margin:4px 0 0;color:var(--el-text-color-secondary)}.actions,.filters{gap:8px}.filters{margin-bottom:16px;flex-wrap:wrap}.assignment-language-field{gap:6px}.language-help{color:var(--el-text-color-secondary);cursor:help}.platform-link{display:inline-flex;max-width:100%}.platform-link :deep(.el-link__inner){display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.platform-manager,.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.platform-row{gap:16px;padding:12px 0;border-top:1px solid var(--el-border-color-lighter)}.platform-info{min-width:0}.platform-info span{display:block;margin-top:4px;overflow:hidden;color:var(--el-text-color-secondary);text-overflow:ellipsis;white-space:nowrap}.advanced-title{margin-bottom:14px;font-weight:600}.detail-content{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.pagination{display:flex;justify-content:flex-end;margin-top:16px}:deep(.long-dialog){display:flex;max-height:90vh;overflow:hidden;flex-direction:column}:deep(.long-dialog .el-dialog__header),:deep(.long-dialog .el-dialog__footer){flex-shrink:0}:deep(.long-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:deep(.long-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
@media(max-width:768px){.header,.focus-header,.focus-header__title{align-items:flex-start;flex-direction:column;gap:12px}.focus-header__divider{display:none}.focus-header__project{align-items:flex-start;width:calc(100vw - 72px);min-width:0;flex-direction:column}.focus-header__project .el-select{width:100%}.annotation-accounts--focus{height:auto;min-height:calc(100vh - 96px)}.annotation-accounts--focus :deep(.el-card__body){overflow:visible}.pagination{overflow-x:auto;justify-content:flex-start}}
</style>

<style>
.account-advanced-popper{max-width:calc(100vw - 32px)}.account-detail-popper,.account-person-popper{max-width:calc(100vw - 32px)}.account-person-popper .person-detail-content{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.platform-manager-popper{max-width:calc(100vw - 32px)}
</style>
