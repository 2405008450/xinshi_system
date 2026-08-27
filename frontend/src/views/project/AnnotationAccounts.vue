<template>
  <el-card class="page-card annotation-accounts" :class="{ 'annotation-accounts--focus': viewMode === 'project' }">
    <template #header>
      <div v-if="viewMode === 'project'" class="focus-header">
        <div class="focus-header__title">
          <el-button :disabled="sheetLocked" @click="returnToAssets">返回账号资产</el-button>
          <span class="focus-header__divider" />
          <div>
            <h2>{{ selectedProject?.projectName || selectedProject?.orderNo || '项目账号表' }}</h2>
            <p>项目账号表 · 表格编辑模式</p>
          </div>
        </div>
        <div class="actions">
          <ProjectFieldSeeder :project-id="projectId" :fields="missingStandardProjectFields" :disabled="sheetLocked" @completed="loadProjectFields" />
          <CustomFieldManager table-code="account_assignment" :project-id="projectId" button-label="项目字段" :disabled="sheetLocked" @changed="loadProjectFields" />
          <el-button :disabled="sheetLocked||!effectiveClientId||!projectId||!platforms.length" @click="importVisible=true">导入</el-button>
          <el-button type="primary" :disabled="sheetLocked||!effectiveClientId" @click="enterCreateMode">新增账号</el-button>
        </div>
      </div>
      <div v-else class="header">
        <div><h2>标注账号资产库</h2><p>按客户长期维护平台账号，并保留标注员分配履历</p></div>
        <div class="actions">
          <el-radio-group v-model="viewMode" size="small" :disabled="editing||sheetLocked" @change="viewModeChanged"><el-radio-button value="assets">账号资产</el-radio-button><el-radio-button value="project" :disabled="!projectId">项目账号表</el-radio-button></el-radio-group>
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" @reset="resetColumns" />
          <CustomFieldManager table-code="account" button-label="账号字段" @changed="loadFields" />
          <el-popover v-model:visible="platformManagerVisible" trigger="click" placement="bottom-end" :width="560" popper-class="platform-manager-popper">
            <template #reference><el-button :disabled="!effectiveClientId||editing">平台管理</el-button></template>
            <div class="platform-manager">
              <div class="panel-title"><strong>客户平台</strong><el-button link type="primary" @click="openPlatform()">新增平台</el-button></div>
              <el-empty v-if="!platforms.length" description="暂无平台" :image-size="70" />
              <div v-for="item in platforms" :key="item.id" class="platform-row">
                <div class="platform-info"><strong>{{ platformName(item) }}</strong><span>{{ item.platformUrl }}</span></div>
                <div class="actions"><el-button link type="primary" @click="openPlatform(item)">编辑</el-button><el-button link type="danger" @click="removePlatform(item)">删除</el-button></div>
              </div>
            </div>
          </el-popover>
          <BatchDeleteToolbar v-if="!editing" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-tooltip v-if="!editing && !deleteMode" :disabled="Boolean(effectiveClientId)" content="所选项目尚未关联客户，请先在项目详情中完善客户信息" placement="bottom">
            <span class="disabled-button-wrapper"><el-button :disabled="sheetLocked||!effectiveClientId" @click="enterCreateMode">新增账号</el-button></span>
          </el-tooltip>
          <el-button v-if="!editing && !deleteMode" type="primary" :disabled="!effectiveClientId||!platforms.length" @click="enterEditMode">批量编辑</el-button>
          <el-button v-if="editing" @click="exitEditMode">退出编辑</el-button>
        </div>
      </div>
    </template>

    <div class="filters" :class="{ 'filters--focus': viewMode === 'project' }">
      <el-select v-if="viewMode === 'assets'" v-model="clientId" :disabled="editing||sheetLocked" filterable remote clearable :loading="clientSearchLoading" :remote-method="searchClients" placeholder="输入客户名称后联想" style="width:260px" @change="changeClient">
        <el-option v-for="item in clients" :key="item.id" :label="item.client_short_name || item.client_name" :value="item.id" />
      </el-select>
      <el-select v-if="viewMode === 'assets'" v-model="projectId" :disabled="editing||sheetLocked" clearable filterable placeholder="选择项目（选择后仍停留账号资产）" style="width:min(420px, calc(100vw - 32px))" @change="projectSelectionChanged">
        <el-option v-for="item in clientProjects" :key="item.id" :label="item.projectName || '未命名'" :value="item.id" />
      </el-select>
      <div v-if="viewMode === 'assets'" class="assignment-language-field">
        <el-select v-model="assignmentLanguageItemId" :disabled="editing||sheetLocked||!projectId" clearable filterable placeholder="账号适用语言（选择人员前必选）" style="width:250px">
          <el-option v-for="item in languageItems" :key="item.id" :label="item.display" :value="item.id" />
        </el-select>
        <el-tooltip content="表示该账号在所选项目中用于哪种语言或语言组合，选项来自“标注项目详情”。单语言项目会自动带出，多语言项目需人工选择。" placement="top"><el-icon class="language-help"><QuestionFilled /></el-icon></el-tooltip>
      </div>
      <el-input v-model="keyword" :disabled="editing||sheetLocked" clearable placeholder="平台、编号、姓名或昵称" style="width:280px" @input="onKeyword" @keyup.enter="queryNow" />
      <el-button type="primary" :disabled="editing||sheetLocked" @click="queryNow">查询</el-button><el-button :disabled="editing||sheetLocked" @click="resetFilters">重置</el-button>
      <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="account-advanced-popper">
        <template #reference><el-button :disabled="editing||sheetLocked">高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
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

    <div v-if="editing" class="sheet-toolbar">
      <el-button type="primary" :loading="saving" @click="saveDrafts">保存变更（{{ dirtyCount }}）</el-button>
      <el-input-number v-model="addRowCount" :min="1" :max="100" controls-position="right" style="width:105px" />
      <el-button @click="addDraftRows(addRowCount)">新增行</el-button>
      <el-button :disabled="!selectedDrafts.length" @click="duplicateSelectedRows">复制选中行</el-button>
      <el-button :disabled="!selectedDrafts.length" @click="copySelectedRows">复制为表格</el-button>
      <span class="sheet-tip">已有账号的凭据保持隐藏；留空表示不修改。</span>
      <span class="sheet-tip">Excel 粘贴列顺序：账号昵称、登录账号、密码、标注员</span>
    </div>

    <div v-if="editing" class="batch-defaults">
      <div class="batch-defaults-title"><strong>新增行默认值</strong><span>仅用于快速铺开新增行；表格内每个单元格仍可单独修改</span></div>
      <el-form label-position="top" class="batch-defaults-form">
        <el-form-item label="平台*"><el-select v-model="batchDefaults.platformId" filterable @change="syncBatchDefaults('platformId')"><el-option v-for="item in platforms" :key="item.id" :label="platformName(item)" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="项目"><el-select v-model="batchDefaults.projectId" :disabled="viewMode==='project'" clearable filterable @change="batchProjectChanged"><el-option v-for="item in clientProjects" :key="item.id" :label="item.projectName || '未命名'" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="语言方向"><el-select v-model="batchDefaults.languageItemIds" multiple collapse-tags clearable @change="syncBatchDefaults('languageItemIds')"><el-option v-for="item in batchLanguages" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item>
        <el-form-item v-if="viewMode==='assets'" label="账号来源"><el-select v-model="batchDefaults.accountSource" @change="syncBatchDefaults('accountSource')"><el-option v-for="(label,value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item v-if="viewMode==='assets'" label="负责人"><el-select v-model="batchDefaults.ownerId" filterable @change="syncBatchDefaults('ownerId')"><el-option v-for="item in users" :key="item.id" :label="userName(item)" :value="item.id" /></el-select></el-form-item>
        <el-form-item v-if="viewMode==='assets'" label="到期日"><el-date-picker v-model="batchDefaults.expiresOn" clearable value-format="YYYY-MM-DD" @change="syncBatchDefaults('expiresOn')" /></el-form-item>
      </el-form>
    </div>

    <div v-if="editing" class="sheet-wrap" @paste="handleGridPaste">
      <el-table ref="editTableRef" :data="editRows" border row-key="_rowKey" :row-class-name="draftRowClass" @selection-change="draftSelectionChanged">
        <el-table-column type="selection" width="46" fixed="left" />
        <el-table-column type="index" label="#" width="55" fixed="left" />
        <el-table-column label="平台*" min-width="180"><template #default="{row}"><el-select v-model="row.platformId" filterable @change="markDraft(row)"><el-option v-for="item in platforms" :key="item.id" :label="platformName(item)" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="账号昵称" min-width="180"><template #default="{row,$index}"><div :data-cell="`${$index}:nickname`"><el-input v-model="row.nickname" @focus="setActiveCell($index,'nickname')" @input="markDraft(row)" @keydown="gridKeydown($event,$index,'nickname')" /></div></template></el-table-column>
        <el-table-column label="登录账号" min-width="220"><template #default="{row,$index}"><div :data-cell="`${$index}:loginAccount`"><el-input v-model="row.loginAccount" autocomplete="off" @focus="setActiveCell($index,'loginAccount')" @input="markDraft(row)" @keydown="gridKeydown($event,$index,'loginAccount')" /></div></template></el-table-column>
        <el-table-column label="密码" min-width="220"><template #default="{row,$index}"><div :data-cell="`${$index}:password`"><el-input v-model="row.password" type="text" autocomplete="off" @focus="setActiveCell($index,'password')" @input="markDraft(row)" @keydown="gridKeydown($event,$index,'password')" /></div></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="项目" min-width="200"><template #default="{row}"><el-select v-model="row.projectId" clearable filterable @change="draftProjectChanged(row)"><el-option v-for="item in clientProjects" :key="item.id" :label="item.projectName || item.orderNo || '未命名'" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column label="账号适用语言" min-width="210"><template #default="{row}"><el-select v-model="row.languageItemIds" multiple collapse-tags clearable :disabled="!row.projectId" @change="markDraft(row)"><el-option v-for="item in draftLanguageItems(row)" :key="item.id" :label="item.display" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column label="标注员（选填）" min-width="220"><template #default="{row,$index}"><div :data-cell="`${$index}:personId`"><el-select v-model="row.personId" clearable filterable :disabled="!assignmentReady(row)" :placeholder="assignmentPlaceholder(row)" :filter-method="captureTalentKeyword" @focus="setActiveCell($index,'personId');beginTalentSearch()" @change="personChanged(row)"><el-option v-for="item in talentsForRow(row)" :key="item.id" :label="talentOptionLabel(item)" :value="item.id" /></el-select></div></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="账号状态" min-width="130"><template #default="{row}"><el-select v-model="row.accountStatus" :disabled="Boolean(row.personId)" @change="markDraft(row)"><el-option v-for="(label,value) in row.personId?{assigned:'已分配'}:manualAccountStatusLabels" :key="value" :label="label" :value="value" /></el-select></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="注册状态" min-width="150"><template #default="{row}"><el-select v-model="row.registrationStatus" @change="markDraft(row)"><el-option v-for="(label,value) in registrationStatusLabels" :key="value" :label="label" :value="value" /></el-select></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="账号来源" min-width="150"><template #default="{row}"><el-select v-model="row.accountSource" @change="markDraft(row)"><el-option v-for="(label,value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="负责人*" min-width="160"><template #default="{row}"><el-select v-model="row.ownerId" filterable @change="markDraft(row)"><el-option v-for="item in users" :key="item.id" :label="userName(item)" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="到期日" min-width="160"><template #default="{row}"><el-date-picker v-model="row.expiresOn" clearable value-format="YYYY-MM-DD" @change="markDraft(row)" /></template></el-table-column>
        <el-table-column v-if="viewMode==='assets'" label="备注" min-width="220"><template #default="{row}"><el-input v-model="row.remarks" type="textarea" :rows="1" @input="markDraft(row)" /></template></el-table-column>
        <template v-if="viewMode==='assets'">
        <el-table-column v-for="field in customFields" :key="`account-edit:${field.id}`" :label="field.fieldLabel" min-width="180">
          <template #default="{row}">
            <el-switch v-if="field.dataType==='boolean'" v-model="row.customValues[field.id]" @change="markDraft(row)" />
            <el-input-number v-else-if="field.dataType==='number'" v-model="row.customValues[field.id]" style="width:100%" @change="markDraft(row)" />
            <el-date-picker v-else-if="field.dataType==='date'||field.dataType==='datetime'" v-model="row.customValues[field.id]" :type="field.dataType==='datetime'?'datetime':'date'" :value-format="field.dataType==='datetime'?'YYYY-MM-DDTHH:mm:ss':'YYYY-MM-DD'" style="width:100%" @change="markDraft(row)" />
            <el-select v-else-if="field.dataType==='single_select'||field.dataType==='multi_select'" v-model="row.customValues[field.id]" :multiple="field.dataType==='multi_select'" clearable @change="markDraft(row)"><el-option v-for="option in field.options||[]" :key="option.value||option" :label="option.label||option" :value="option.value||option" /></el-select>
            <el-input v-else v-model="row.customValues[field.id]" @input="markDraft(row)" />
          </template>
        </el-table-column>
        </template>
        <template v-else>
        <el-table-column v-for="field in projectCustomFields" :key="`assignment-edit:${field.id}`" :label="field.fieldLabel" min-width="180">
          <template #default="{row}">
            <el-switch v-if="field.dataType==='boolean'" v-model="row.assignmentCustomValues[field.id]" @change="markDraft(row)" />
            <el-input-number v-else-if="field.dataType==='number'" v-model="row.assignmentCustomValues[field.id]" style="width:100%" @change="markDraft(row)" />
            <el-date-picker v-else-if="field.dataType==='date'||field.dataType==='datetime'" v-model="row.assignmentCustomValues[field.id]" :type="field.dataType==='datetime'?'datetime':'date'" :value-format="field.dataType==='datetime'?'YYYY-MM-DDTHH:mm:ss':'YYYY-MM-DD'" style="width:100%" @change="markDraft(row)" />
            <el-select v-else-if="field.dataType==='single_select'||field.dataType==='multi_select'" v-model="row.assignmentCustomValues[field.id]" :multiple="field.dataType==='multi_select'" clearable @change="markDraft(row)"><el-option v-for="option in field.options||[]" :key="option.value||option" :label="option.label||option" :value="option.value||option" /></el-select>
            <el-input v-else v-model="row.assignmentCustomValues[field.id]" @input="markDraft(row)" />
          </template>
        </el-table-column>
        </template>
        <el-table-column label="结果" width="90" fixed="right"><template #default="{row}"><el-tooltip v-if="row._error" :content="row._error" placement="left"><el-tag type="danger">失败</el-tag></el-tooltip><el-tag v-else-if="row._dirty" type="warning">待保存</el-tag><el-tag v-else type="success">已保存</el-tag></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button v-if="row._isNew" link type="danger" @click="removeDraft(row)">移除</el-button></template></el-table-column>
      </el-table>
    </div>

    <ProjectAccountSpreadsheet
      v-else-if="viewMode==='project'"
      focus-mode
      :rows="rows"
      :fields="projectCustomFields"
      :talents="talents"
      :project-name="selectedProject?.projectName || selectedProject?.orderNo || '项目账号表'"
      :loading="loading"
      :saving="saving"
      :total-rows="pagination.total"
      :max-rows="PROJECT_SHEET_MAX_ROWS"
      :save-errors="sheetSaveErrors"
      @save="saveProjectSheetChanges"
      @dirty-change="sheetDirtyChanged"
      @detail="openSheetDetail"
      @edit="openAccount"
    />

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
      <template v-if="viewMode==='assets'">
        <el-table-column v-for="field in visibleCustomFields" :key="`account-view:${field.id}`" :label="field.fieldLabel" min-width="120" show-overflow-tooltip><template #default="{row}">{{ formatValue(row.customValues?.[field.id]) }}</template></el-table-column>
      </template>
      <template v-else>
        <el-table-column v-for="field in visibleProjectCustomFields" :key="`assignment-view:${field.id}`" :label="field.fieldLabel" min-width="140" show-overflow-tooltip><template #default="{row}">{{ formatValue(row.assignmentCustomValues?.[field.id]) }}</template></el-table-column>
      </template>
      <el-table-column label="详情" width="90" fixed="right"><template #default="{row}">
        <el-popover trigger="click" placement="left" :width="760" title="标注账号详情" popper-class="account-detail-popper" @show="loadAssignments(row)">
          <template #reference><el-button link type="primary">查看详情</el-button></template>
          <div class="detail-content"><el-descriptions :column="2" border size="small">
            <el-descriptions-item label="平台">{{ row.platformName || host(row.platformUrl) }}</el-descriptions-item><el-descriptions-item label="平台链接"><el-link v-if="row.platformUrl" type="primary" :href="row.platformUrl" target="_blank" rel="noopener noreferrer">{{ row.platformUrl }}</el-link><span v-else>-</span></el-descriptions-item>
            <el-descriptions-item label="账号昵称">{{ row.nickname || '-' }}</el-descriptions-item><el-descriptions-item label="账号来源">{{ sourceLabels[row.accountSource] || row.accountSource }}</el-descriptions-item>
            <el-descriptions-item label="登录账号">{{ row.loginAccount || '-' }}</el-descriptions-item><el-descriptions-item label="密码">{{ row.password || '-' }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ row.ownerName || '-' }}</el-descriptions-item><el-descriptions-item label="账号状态">{{ accountStatusLabels[row.accountStatus] || row.accountStatus }}</el-descriptions-item>
            <el-descriptions-item label="标注员">{{ row.personName || '-' }}</el-descriptions-item><el-descriptions-item label="当前项目">{{ row.projectName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="语言方向">{{ row.languageLabels?.join('、') || '-' }}</el-descriptions-item><el-descriptions-item label="分配日期">{{ row.assignedOn || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ row.remarks || '-' }}</el-descriptions-item>
          </el-descriptions><h4>分配履历</h4><el-table :data="assignmentCache[row.id] || []" size="small" max-height="260" v-loading="assignmentLoading===row.id"><el-table-column prop="personName" label="标注员" /><el-table-column prop="projectName" label="项目" /><el-table-column prop="assignedOn" label="分配日期" width="110" /><el-table-column prop="releasedOn" label="释放日期" width="110"><template #default="scope">{{ scope.row.releasedOn || '使用中' }}</template></el-table-column></el-table></div>
        </el-popover>
      </template></el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openAccount(row)">{{ viewMode==='project' ? '编辑项目记录' : '编辑' }}</el-button></template></el-table-column>
    </el-table>
    <div v-if="!editing && viewMode==='assets'" class="pagination"><el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[20,50,100]" layout="total, sizes, prev, pager, next, jumper" @current-change="reload" @size-change="pageSizeChanged" /></div>
  </el-card>

  <el-dialog v-model="platformDialog" :title="platformForm.id ? '编辑平台' : '新增平台'" width="min(680px, calc(100vw - 32px))" top="5vh" class="long-dialog" append-to-body>
    <el-form label-width="100px"><el-form-item label="平台名称"><el-input v-model="platformForm.platformName" /></el-form-item><el-form-item label="平台链接" required><el-input v-model="platformForm.platformUrl" /></el-form-item><el-form-item label="登录说明"><el-input v-model="platformForm.loginNotes" type="textarea" :rows="4" /></el-form-item><el-form-item label="启用"><el-switch v-model="platformForm.isActive" /></el-form-item></el-form>
    <template #footer><el-button @click="platformDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePlatform">保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="accountDialog" title="编辑账号" width="min(880px, calc(100vw - 32px))" top="5vh" class="long-dialog" append-to-body>
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
      <el-form-item label="备注"><el-input v-model="accountForm.remarks" type="textarea" :rows="3" /></el-form-item><AnnotationCustomFieldInputs :fields="customFields" :values="accountForm.customValues" />
      <template v-if="accountForm.projectId && projectCustomFields.length"><el-divider content-position="left">项目账号字段</el-divider><AnnotationCustomFieldInputs :fields="projectCustomFields" :values="accountForm.assignmentCustomValues" /></template>
    </el-form><template #footer><el-button @click="accountDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button></template>
  </el-dialog>

  <AccountImportDialog v-model="importVisible" :client-id="effectiveClientId" :project-id="projectId" :platforms="platforms" :language-items="languageItems" :users="users" :default-language-ids="assignmentLanguageItemId?[assignmentLanguageItemId]:[]" @imported="importCompleted" />

  <el-dialog v-model="sheetDetailVisible" title="项目账号记录详情" width="min(760px, calc(100vw - 32px))" top="5vh" class="long-dialog" append-to-body>
    <div v-if="sheetDetailRow" class="detail-content">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="平台">{{ sheetDetailRow.platformName || host(sheetDetailRow.platformUrl) }}</el-descriptions-item>
        <el-descriptions-item label="登录账号">{{ sheetDetailRow.loginAccount || '-' }}</el-descriptions-item>
        <el-descriptions-item label="密码">{{ sheetDetailRow.password || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分配人员">{{ sheetDetailRow.personName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ sheetDetailRow.personGender || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ sheetDetailRow.projectName || selectedProject?.projectName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="语言方向">{{ sheetDetailRow.languageLabels?.join('、') || '-' }}</el-descriptions-item>
        <el-descriptions-item v-for="field in projectCustomFields" :key="field.id" :label="field.fieldLabel">{{ formatValue(sheetDetailRow.assignmentCustomValues?.[field.id]) }}</el-descriptions-item>
      </el-descriptions>
      <h4>分配履历</h4>
      <el-table :data="assignmentCache[sheetDetailRow.id] || []" size="small" max-height="260" v-loading="assignmentLoading===sheetDetailRow.id">
        <el-table-column prop="personName" label="标注员" /><el-table-column prop="projectName" label="项目" /><el-table-column prop="assignedOn" label="分配日期" width="110" /><el-table-column prop="releasedOn" label="释放日期" width="110"><template #default="scope">{{ scope.row.releasedOn || '使用中' }}</template></el-table-column>
      </el-table>
    </div>
    <template #footer><el-button @click="sheetDetailVisible=false">关闭</el-button></template>
  </el-dialog>

</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import * as clientApi from '@/api/clients'
import * as projectApi from '@/api/annotationProjects'
import * as talentApi from '@/api/talents'
import * as ops from '@/api/annotationOps'
import { getUsers } from '@/api/users'
import AnnotationCustomFieldInputs from '@/components/annotation/AnnotationCustomFieldInputs.vue'
import AccountImportDialog from '@/components/annotation/AccountImportDialog.vue'
import CustomFieldManager from '@/components/annotation/CustomFieldManager.vue'
import ProjectFieldSeeder from '@/components/annotation/ProjectFieldSeeder.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useTableColumns } from '@/composables/useTableColumns'

const emit=defineEmits(['focus-mode-change'])
const ProjectAccountSpreadsheet=defineAsyncComponent(()=>import('@/components/annotation/ProjectAccountSpreadsheet.vue'))
const PROJECT_SHEET_MAX_ROWS=500

const clients=ref([]),projects=ref([]),platforms=ref([]),rows=ref([]),talents=ref([]),users=ref([]),customFields=ref([]),projectCustomFields=ref([])
const route=useRoute()
const clientId=ref(''),projectId=ref(''),assignmentLanguageItemId=ref(''),keyword=ref(''),loading=ref(false),saving=ref(false),clientSearchLoading=ref(false)
const editing=ref(false),editRows=ref([]),selectedDrafts=ref([]),editTableRef=ref(null),accountTableRef=ref(null)
const addRowCount=ref(1),activeCell=reactive({row:0,key:'loginAccount'})
const currentUserId=localStorage.getItem('user_id')||''
const batchDefaults=reactive({platformId:'',projectId:'',languageItemIds:[],accountSource:'client_provided',ownerId:currentUserId,expiresOn:null})
const advancedVisible=ref(false),platformManagerVisible=ref(false),platformDialog=ref(false),accountDialog=ref(false),importVisible=ref(false),viewMode=ref('assets')
const sheetDirtyCount=ref(0)
const sheetSaveErrors=ref({})
const sheetDetailVisible=ref(false),sheetDetailRow=ref(null)
const assignmentCache=reactive({}),assignmentLoading=ref(''),personProfileCache=reactive({}),personProfileLoadingId=ref('')
const occupancy=ref([]),inlineSavingId=ref(''),talentKeyword=ref('')
const pagination=reactive({page:1,limit:20,total:0})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:accountTableRef,pagination,deleteRow:(row)=>ops.deleteAccount(row.id),getLabel:(row)=>row.nickname||row.loginAccount||row.platformName||row.id,reload:()=>reload(),onDeleted:(row)=>{delete assignmentCache[row.id]},entityName:'标注账号'})
const filters=reactive({platformId:'',assignmentState:'',accountStatus:'',languageItemId:''})
const platformForm=reactive({id:'',clientId:'',platformName:'',platformUrl:'',loginNotes:'',isActive:true})
const accountForm=reactive({id:'',clientId:'',platformId:'',parentAccountId:null,ownerId:currentUserId,nickname:'',loginAccount:'',password:'',accountStatus:'available',registrationStatus:'unregistered',accountSource:'client_provided',expiresOn:null,remarks:'',customValues:{},assignmentCustomValues:{},personId:'',originalPersonId:'',projectId:'',originalProjectId:'',languageItemIds:[]})
const today=()=>new Date().toISOString().slice(0,10)
const accountStatusLabels={available:'可用',assigned:'已分配',suspended:'暂停',banned:'封禁',retired:'已退役'}
const manualAccountStatusLabels={available:'可用',suspended:'暂停',banned:'封禁',retired:'已退役'}
const registrationStatusLabels={unregistered:'未注册',registering:'注册中',registered:'已注册',registration_failed:'注册失败',disabled:'已停用',not_required:'无需注册'}
const sourceLabels={client_provided:'客户提供',self_registered:'自助注册',annotator_owned:'标注员自有'}
const talentStatusLabels={active:'活跃',standby:'待命',inactive:'停用'}
const baseTableColumns=[{key:'platform',label:'平台链接'},{key:'nickname',label:'账号昵称'},{key:'person',label:'标注员'},{key:'project',label:'当前项目'},{key:'language',label:'语言方向'},{key:'accountStatus',label:'账号状态'},{key:'owner',label:'负责人'},{key:'expiresOn',label:'到期日'}]
const standardProjectFieldTemplates=[
  {fieldKey:'external_data_no',fieldLabel:'数据编号',dataType:'text'},
  {fieldKey:'quality_status',fieldLabel:'质检状态',dataType:'text'},
  {fieldKey:'price',fieldLabel:'价格',dataType:'number'},
  {fieldKey:'error_feedback',fieldLabel:'错误点/问题',dataType:'text'},
  {fieldKey:'highlight_feedback',fieldLabel:'标红需反馈',dataType:'text'},
]
const projectStandardFieldKeys=new Set(standardProjectFieldTemplates.map(item=>item.fieldKey))
const assetTableColumns=computed(()=>[...baseTableColumns,...customFields.value.map(item=>({key:`custom:${item.id}`,label:item.fieldLabel}))])
const extraProjectCustomFields=computed(()=>projectCustomFields.value.filter(item=>!projectStandardFieldKeys.has(item.fieldKey)))
const projectTableColumns=computed(()=>[
  {key:'platform',label:'平台'},
  {key:'person',label:'分配人员'},
  {key:'language',label:'语言方向'},
  ...extraProjectCustomFields.value.map(item=>({key:`assignment:${item.id}`,label:item.fieldLabel})),
])
const assetDefaults=computed(()=>['platform','nickname','person','language','accountStatus','owner'])
const projectDefaults=computed(()=>['platform','person','language',...extraProjectCustomFields.value.map(item=>`assignment:${item.id}`)])
const assetColumns=useTableColumns('annotation-account-library-v3',assetTableColumns,assetDefaults)
const projectColumns=useTableColumns('annotation-project-account-sheet-v2',projectTableColumns,projectDefaults)
const tableColumns=computed(()=>viewMode.value==='project'?projectTableColumns.value:assetTableColumns.value)
const visibleColumnKeys=computed({get:()=>viewMode.value==='project'?projectColumns.selectedKeys.value:assetColumns.selectedKeys.value,set:value=>{if(viewMode.value==='project')projectColumns.selectedKeys.value=value;else assetColumns.selectedKeys.value=value}})
const isVisible=key=>(viewMode.value==='project'?projectColumns:assetColumns).isVisible(key)
const resetColumns=()=>{(viewMode.value==='project'?projectColumns:assetColumns).reset()}
const visibleCustomFields=computed(()=>customFields.value.filter(item=>isVisible(`custom:${item.id}`)))
const visibleProjectCustomFields=computed(()=>extraProjectCustomFields.value.filter(item=>isVisible(`assignment:${item.id}`)))
const missingStandardProjectFields=computed(()=>standardProjectFieldTemplates.filter(template=>!projectCustomFields.value.some(field=>field.fieldKey===template.fieldKey)))
const projectField=key=>projectCustomFields.value.find(item=>item.fieldKey===key)
const projectValue=(row,key)=>{const field=projectField(key);return field?formatValue(row.assignmentCustomValues?.[field.id]):'-'}
const clientProjects=computed(()=>clientId.value?projects.value.filter(item=>item.clientId===clientId.value):projects.value)
const selectedProject=computed(()=>projects.value.find(item=>item.id===projectId.value))
const effectiveClientId=computed(()=>clientId.value||selectedProject.value?.clientId||'')
const languageItems=computed(()=>selectedProject.value?.languageItems||clientProjects.value.flatMap(item=>item.languageItems||[]))
const filterLanguageItems=computed(()=>selectedProject.value?.languageItems||clientProjects.value.flatMap(item=>item.languageItems||[]))
const batchLanguages=computed(()=>projects.value.find(item=>item.id===batchDefaults.projectId)?.languageItems||[])
const accountFormProjects=computed(()=>accountForm.clientId?projects.value.filter(item=>item.clientId===accountForm.clientId):projects.value)
const accountFormLanguageItems=computed(()=>projects.value.find(item=>item.id===accountForm.projectId)?.languageItems||[])
const filteredTalents=computed(()=>{const keyword=talentKeyword.value.trim().toLocaleLowerCase();return keyword?talents.value.filter(item=>talentOptionLabel(item).toLocaleLowerCase().includes(keyword)):talents.value})
const advancedCount=computed(()=>Object.values(filters).filter(Boolean).length)
const accountEditStatusLabels=computed(()=>accountForm.accountStatus==='assigned'?{assigned:'已分配'}:manualAccountStatusLabels)
const dirtyCount=computed(()=>editRows.value.filter(row=>row._dirty).length)
const sheetLocked=computed(()=>viewMode.value==='project'&&sheetDirtyCount.value>0)
const batchDefaultsSummary=computed(()=>{
  const platform=platforms.value.find(item=>item.id===batchDefaults.platformId)
  const project=projects.value.find(item=>item.id===batchDefaults.projectId)
  const owner=users.value.find(item=>item.id===batchDefaults.ownerId)
  return [platform&&platformName(platform),project&&(project.projectName||project.orderNo),sourceLabels[batchDefaults.accountSource],owner&&userName(owner),batchDefaults.expiresOn].filter(Boolean).join(' / ')||'请先设置本批次统一字段'
})
let timer,controller,requestId=0,clientSearchTimer,clientSearchController,clientSearchRequestId=0
const host=url=>{try{return new URL(url).hostname}catch{return url||'未命名平台'}}
const platformName=item=>item.platformName||host(item.platformUrl)
const talentOptionLabel=item=>talentName(item)
const userName=item=>item.full_name||item.fullName||item.username||'-'
const formatValue=value=>Array.isArray(value)?value.join('、'):value===true?'是':value===false?'否':value??'-'
const show=value=>value===null||value===undefined||value===''?'-':Array.isArray(value)?value.join('、')||'-':value
const statusTag=value=>({available:'success',assigned:'primary',suspended:'warning',banned:'danger',retired:'info'}[value]||'info')
const importCompleted=async()=>{await Promise.all([loadProjectFields(),reload()])}
const saveProjectSheetChanges=async changes=>{
  if(!changes.length)return
  sheetSaveErrors.value={}
  saving.value=true
  try{
    const response=await ops.batchSaveAccounts({clientId:effectiveClientId.value,rows:changes.map(({original,personId,assignmentCustomValues,rowIndex})=>({
      rowKey:`project-sheet-${rowIndex}`,
      id:original.id,
      account:{
        platformId:original.platformId,parentAccountId:original.parentAccountId||null,ownerId:original.ownerId||currentUserId||null,
        nickname:original.nickname||null,loginAccount:null,password:null,accountStatus:personId?'assigned':(original.accountStatus==='assigned'?'available':original.accountStatus),
        registrationStatus:original.registrationStatus,accountSource:original.accountSource,expiresOn:original.expiresOn||null,
        remarks:original.remarks||null,sequenceNo:original.sequenceNo||null,customValues:original.customValues||{},
      },
      personId:personId||null,projectId:projectId.value,languageItemIds:original.languageItemIds?.length?original.languageItemIds:(assignmentLanguageItemId.value?[assignmentLanguageItemId.value]:[]),
      assignmentCustomValues,
    }))})
    const failed=(response.results||[]).filter(item=>!item.success)
    sheetSaveErrors.value=Object.fromEntries(failed.map(item=>[Number(String(item.rowKey||'').replace('project-sheet-','')),item.error||'保存失败']))
    if(failed.length)ElMessage.warning(`已保存 ${(response.results||[]).length-failed.length} 行，${failed.length} 行失败：${failed[0].error||'请检查数据'}`)
    else ElMessage.success(`已保存 ${changes.length} 行项目账号记录`)
    if(!failed.length)await reload()
  }catch(error){ElMessage.error(error.detail||error.message||'保存项目账号表失败')}
  finally{saving.value=false}
}
const sheetDirtyChanged=count=>{sheetDirtyCount.value=count;if(count)advancedVisible.value=false;else sheetSaveErrors.value={}}
// 项目既是进入“项目账号表”的上下文，也是账号资产列表的常用筛选条件。
// 选择项目后即使仍停留在资产视图，也必须把 projectId 传给列表和总数接口。
const buildFilters=()=>({clientId:clientId.value||undefined,keyword:keyword.value.trim()||undefined,...Object.fromEntries(Object.entries(filters).map(([key,value])=>[key,value||undefined])),projectId:projectId.value||undefined})
const loadFields=async()=>{customFields.value=await ops.getCustomFields('account',null)}
const loadProjectFields=async()=>{projectCustomFields.value=projectId.value?await ops.getCustomFields('account_assignment',projectId.value):[];const userKey=localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous';if(projectId.value&&!localStorage.getItem(`table-columns:annotation-project-account-sheet-v2:${userKey}`))projectColumns.reset()}
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
const projectSelectionChanged=async()=>{filters.languageItemId='';syncAssignmentLanguage();viewMode.value='assets';pagination.page=1;await Promise.all([loadPlatforms(),loadProjectFields()]);await reload()}
const viewModeChanged=async value=>{if(value==='project'&&!projectId.value){viewMode.value='assets';return ElMessage.warning('请先选择项目')}pagination.page=1;await loadProjectFields();await reload()}
const returnToAssets=async()=>{viewMode.value='assets';await viewModeChanged('assets')}
const clearAdvanced=()=>{Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});queryNow()}
const changeClient=async()=>{projectId.value='';assignmentLanguageItemId.value='';viewMode.value='assets';projectCustomFields.value=[];Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});pagination.page=1;await loadPlatforms();await reload()}
const resetFilters=async()=>{clientId.value='';clients.value=[];projectId.value='';assignmentLanguageItemId.value='';viewMode.value='assets';projectCustomFields.value=[];keyword.value='';Object.assign(filters,{platformId:'',assignmentState:'',accountStatus:'',languageItemId:''});await loadPlatforms();queryNow()}
const pageSizeChanged=()=>{pagination.page=1;reload()}
const newRowKey=()=>globalThis.crypto?.randomUUID?.()||`draft-${Date.now()}-${Math.random().toString(16).slice(2)}`
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
  const persisted=occupancy.value.some(item=>item.personId===talent.id&&item.accountId!==row.id)
  const drafted=editing.value&&editRows.value.some(item=>{
    if(item._rowKey===row._rowKey||item.personId!==talent.id)return false
    return true
  })
  return persisted||drafted
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
const existingRowSummary=row=>[row.platformName||host(row.platformUrl),row.projectName,sourceLabels[row.accountSource],row.expiresOn].filter(Boolean).join(' / ')||'-'
const makeDraft=(row={},secret={})=>({
  ...row,_rowKey:row.id||newRowKey(),_isNew:!row.id,_dirty:!row.id,_error:'',
  platformId:row.platformId||platforms.value[0]?.id||'',nickname:row.nickname||'',
  loginAccount:secret.loginAccount??row.loginAccount??'',password:secret.password??row.password??'',
  personId:row.personId||'',projectId:row.projectId||'',languageItemIds:[...(row.languageItemIds||[])],
  accountStatus:row.accountStatus||'available',
  registrationStatus:row.registrationStatus||'unregistered',accountSource:row.accountSource||'client_provided',ownerId:row.ownerId||currentUserId,
  expiresOn:row.expiresOn||null,remarks:row.remarks||'',customValues:{...(row.customValues||{})},
  assignmentCustomValues:{...(row.assignmentCustomValues||{})},
  _previousPersonId:row.personId||'',
})
const markDraft=row=>{row._dirty=true;row._error=''}
const draftSelectionChanged=value=>{selectedDrafts.value=value}
const setActiveCell=(row,key)=>{activeCell.row=row;activeCell.key=key}
const draftRowClass=({row})=>row._error?'row-error':row._dirty?'row-dirty':''
const editableKeys=['nickname','loginAccount','password','personId']
const focusGridCell=async(row,key)=>{await nextTick();document.querySelector(`[data-cell="${row}:${key}"] input, [data-cell="${row}:${key}"] textarea`)?.focus()}
const gridKeydown=(event,row,key)=>{
  if(!['Tab','Enter'].includes(event.key))return
  event.preventDefault()
  const column=editableKeys.indexOf(key),step=event.shiftKey?-1:1
  let targetColumn=column+step,targetRow=row
  if(targetColumn>=editableKeys.length){targetColumn=0;targetRow++}
  if(targetColumn<0){targetColumn=editableKeys.length-1;targetRow--}
  if(targetRow>=editRows.value.length)addDraftRows(1)
  if(targetRow>=0)focusGridCell(targetRow,editableKeys[targetColumn])
}
const addDraftRows=count=>{
  for(let index=0;index<count;index++){
    editRows.value.push(makeDraft({
      platformId:batchDefaults.platformId,projectId:batchDefaults.projectId,
      languageItemIds:[...batchDefaults.languageItemIds],accountSource:batchDefaults.accountSource,
      ownerId:batchDefaults.ownerId||currentUserId,expiresOn:batchDefaults.expiresOn,personId:'',accountStatus:'available',
    }))
  }
}
const removeDraft=row=>{editRows.value=editRows.value.filter(item=>item._rowKey!==row._rowKey)}
const duplicateSelectedRows=()=>{
  selectedDrafts.value.forEach(row=>editRows.value.push(makeDraft({
    ...row,id:null,_rowKey:null,platformId:batchDefaults.platformId,projectId:batchDefaults.projectId,
    languageItemIds:[...batchDefaults.languageItemIds],
    accountSource:batchDefaults.accountSource,ownerId:batchDefaults.ownerId||currentUserId,expiresOn:batchDefaults.expiresOn,
    personId:'',accountStatus:'available',
  })))
  ElMessage.success(`已复制 ${selectedDrafts.value.length} 行，标注员已清空，请重新选择后保存`)
}
const labelFor=(key,value)=>key==='personId'?talentName(talents.value.find(item=>item.id===value)||{}):value??''
const copySelectedRows=async()=>{
  const content=selectedDrafts.value.map(row=>editableKeys.map(key=>labelFor(key,row[key],row)).join('\t')).join('\n')
  try{await navigator.clipboard.writeText(content);ElMessage.success(`已复制 ${selectedDrafts.value.length} 行`)}catch{ElMessage.error('复制失败，请手工复制')}
}
const applyPastedValue=(row,key,value)=>{
  const text=String(value??'').trim()
  if(key==='personId'){
    const previous=row.personId
    if(!text)row.personId=''
    else{
      const normalized=text.toLocaleLowerCase()
      const matches=talents.value.filter(item=>[item.resourceCode,item.fullName,item.personName,talentName(item)].some(candidate=>String(candidate||'').trim().toLocaleLowerCase()===normalized))
      if(matches.length!==1)throw new Error(matches.length?'标注员匹配结果不唯一':`无法匹配标注员“${text}”`)
      row.personId=matches[0].id
      const error=draftPersonError(row)
      if(error){row.personId=previous;throw new Error(error)}
    }
    row._previousPersonId=row.personId
    row.accountStatus=row.personId?'assigned':'available'
  }else row[key]=text
  markDraft(row)
}
const handleGridPaste=event=>{
  const text=event.clipboardData?.getData('text/plain')
  if(!text)return
  event.preventDefault()
  const matrix=text.replace(/\r/g,'').split('\n');if(matrix.at(-1)==='')matrix.pop()
  const startColumn=Math.max(0,editableKeys.indexOf(activeCell.key))
  while(editRows.value.length<activeCell.row+matrix.length)addDraftRows(1)
  matrix.forEach((line,rowOffset)=>line.split('\t').forEach((value,columnOffset)=>{
    const key=editableKeys[startColumn+columnOffset],row=editRows.value[activeCell.row+rowOffset]
    if(!key||!row)return
    try{applyPastedValue(row,key,value)}catch(error){row._error=`${key}：${error.message}`;row._dirty=true}
  }))
}
const syncBatchDefaults=key=>{
  editRows.value.filter(row=>row._isNew).forEach(row=>{
    row[key]=Array.isArray(batchDefaults[key])?[...batchDefaults[key]]:batchDefaults[key]
    markDraft(row)
  })
}
const batchProjectChanged=()=>{
  const items=projects.value.find(item=>item.id===batchDefaults.projectId)?.languageItems||[]
  batchDefaults.languageItemIds=items.length===1?[items[0].id]:[]
  syncBatchDefaults('projectId');syncBatchDefaults('languageItemIds')
}
const draftLanguageItems=row=>projects.value.find(item=>item.id===row.projectId)?.languageItems||[]
const draftProjectChanged=row=>{
  const items=draftLanguageItems(row)
  row.languageItemIds=items.length===1?[items[0].id]:[]
  row._error=''
  markDraft(row)
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
const draftRowError=row=>{
  if(!row.platformId)return '请选择平台'
  if(!row.ownerId)return '请选择负责人'
  if(row._isNew&&Boolean(row.loginAccount)!==Boolean(row.password))return '新增账号的登录账号和密码必须同时填写'
  return draftPersonError(row)
}
const personChanged=row=>{
  const error=draftPersonError(row)
  if(error){row.personId=row._previousPersonId||'';row.accountStatus=row.personId?'assigned':'available';return ElMessage.warning(error)}
  const context=assignmentContext(row)
  if(row.personId){row.projectId=context.projectId;row.languageItemIds=[...context.languageItemIds]}
  row._previousPersonId=row.personId
  row.accountStatus=row.personId?'assigned':'available'
  markDraft(row)
}
const enterEditMode=async()=>{
  loading.value=true
  try{
    editRows.value=rows.value.map(row=>makeDraft(row,{loginAccount:row.loginAccount,password:row.password}))
    Object.assign(batchDefaults,{platformId:platforms.value[0]?.id||'',projectId:projectId.value||'',languageItemIds:assignmentLanguageItemId.value?[assignmentLanguageItemId.value]:[],accountSource:'client_provided',ownerId:currentUserId,expiresOn:null})
    editing.value=true
  }catch(error){ElMessage.error(error.detail||'进入批量编辑失败')}finally{loading.value=false}
}
const enterCreateMode=async()=>{
  if(!effectiveClientId.value)return ElMessage.warning('请先选择已关联客户的标注项目')
  if(!platforms.value.length){
    ElMessage.info('该客户尚未配置标注平台，请先新增平台；平台保存后即可新增账号')
    openPlatform()
    return
  }
  await enterEditMode()
  if(!editing.value)return
  const newRowIndex=editRows.value.length
  addDraftRows(1)
  await nextTick()
  focusGridCell(newRowIndex,'nickname')
}
const discardDrafts=async()=>{
  const unsavedCount=dirtyCount.value+sheetDirtyCount.value
  if(unsavedCount){
    try{await ElMessageBox.confirm(`还有 ${unsavedCount} 行未保存，确定放弃这些修改？`,'未保存修改',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return false}
  }
  return true
}
const exitEditMode=async()=>{if(!await discardDrafts())return;editing.value=false;editRows.value=[];selectedDrafts.value=[];await reload()}
const saveDrafts=async()=>{
  const drafts=editRows.value.filter(row=>row._dirty)
  if(!drafts.length)return ElMessage.info('没有需要保存的修改')
  drafts.forEach(row=>{row._error=''})
  let invalid=0
  drafts.forEach(row=>{
    const error=draftRowError(row)
    if(error){row._error=error;invalid++;return}
    if(row.personId){const context=assignmentContext(row);row.projectId=context.projectId;row.languageItemIds=[...context.languageItemIds]}
  })
  if(invalid)return ElMessage.warning(`${invalid} 行标注员绑定存在冲突，请修正后再保存`)
  saving.value=true
  try{
    const response=await ops.batchSaveAccounts({clientId:effectiveClientId.value,rows:drafts.map(row=>({
      rowKey:row._rowKey,id:row.id||null,
      account:{platformId:row.platformId,parentAccountId:row.parentAccountId||null,ownerId:row.ownerId||currentUserId||null,nickname:row.nickname||null,loginAccount:row.loginAccount||null,password:row.password||null,accountStatus:row.personId?'assigned':row.accountStatus,registrationStatus:row.registrationStatus,accountSource:row.accountSource,expiresOn:row.expiresOn||null,remarks:row.remarks||null,sequenceNo:row.sequenceNo||null,customValues:row.customValues||{}},
      personId:row.personId||null,projectId:row.projectId||null,languageItemIds:row.languageItemIds||[],assignmentCustomValues:row.assignmentCustomValues||{},
    }))})
    let succeeded=0,failed=0
    ;(response.results||[]).forEach(result=>{
      const row=editRows.value.find(item=>item._rowKey===result.rowKey);if(!row)return
      if(result.success){Object.assign(row,result.account,{id:result.account.id,_isNew:false,_dirty:false,_error:'',loginAccount:row.loginAccount,password:row.password});succeeded++}
      else{row._error=result.error||'保存失败';failed++}
    })
    if(failed)ElMessage.warning(`已保存 ${succeeded} 行，${failed} 行需要修正`)
    else{ElMessage.success(`已保存 ${succeeded} 行`);editing.value=false;editRows.value=[];await reload()}
  }catch(error){ElMessage.error(error.detail||'批量保存失败')}finally{saving.value=false}
}
const openPlatform=row=>{Object.assign(platformForm,{id:row?.id||'',clientId:effectiveClientId.value,platformName:row?.platformName||'',platformUrl:row?.platformUrl||'',loginNotes:row?.loginNotes||'',isActive:row?.isActive??true});platformDialog.value=true}
const savePlatform=async()=>{if(!platformForm.platformUrl.trim())return ElMessage.warning('请输入平台链接');saving.value=true;try{platformForm.id?await ops.updatePlatform(platformForm.id,platformForm):await ops.createPlatform(platformForm);platformDialog.value=false;ElMessage.success('平台已保存');await loadPlatforms();await reload()}catch(error){ElMessage.error(error.detail||'保存失败')}finally{saving.value=false}}
const removePlatform=async row=>{try{await ElMessageBox.confirm(`删除平台“${platformName(row)}”及其全部账号？`,'确认删除');await ops.deletePlatform(row.id);await loadPlatforms();await reload()}catch(error){if(!['cancel','close'].includes(error))ElMessage.error(error.detail||'删除失败')}}
const openAccount=async row=>{
  try{platforms.value=row.clientId?await ops.getPlatforms(row.clientId,{skip:0,limit:500}):[]}catch(error){return ElMessage.error(error.detail||'加载客户平台失败')}
  const resolvedProjectId=row.projectId||projectId.value||''
  const project=projects.value.find(item=>item.id===resolvedProjectId)
  const resolvedLanguages=row.languageItemIds?.length?[...row.languageItemIds]:(assignmentLanguageItemId.value?[assignmentLanguageItemId.value]:((project?.languageItems||[]).length===1?[project.languageItems[0].id]:[]))
  Object.assign(accountForm,{id:row.id,clientId:row.clientId||'',platformId:row.platformId,parentAccountId:row.parentAccountId||null,ownerId:row.ownerId||currentUserId,nickname:row.nickname||'',loginAccount:row.loginAccount||'',password:row.password||'',accountStatus:row.accountStatus||'available',registrationStatus:row.registrationStatus||'unregistered',accountSource:row.accountSource||'client_provided',expiresOn:row.expiresOn||null,remarks:row.remarks||'',customValues:{...(row.customValues||{})},assignmentCustomValues:{...(row.assignmentCustomValues||{})},personId:row.personId||'',originalPersonId:row.personId||'',projectId:resolvedProjectId,originalProjectId:row.projectId||'',languageItemIds:resolvedLanguages})
  accountDialog.value=true
}
const accountFormProjectChanged=()=>{
  const items=accountFormLanguageItems.value
  accountForm.languageItemIds=items.length===1?[items[0].id]:[]
}
const accountFormPersonChanged=()=>{accountForm.accountStatus=accountForm.personId?'assigned':'available'}
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
    accountDialog.value=false;ElMessage.success('账号已保存');await reload()
  }catch(error){ElMessage.error(error.detail||error.message||'保存失败')}finally{saving.value=false}
}
const loadAssignments=async row=>{if(assignmentCache[row.id])return;assignmentLoading.value=row.id;try{assignmentCache[row.id]=await ops.getAccountAssignments(row.id)}catch(error){ElMessage.error(error.detail||'加载分配履历失败')}finally{assignmentLoading.value=''}}
const openSheetDetail=async row=>{sheetDetailRow.value=row;sheetDetailVisible.value=true;await loadAssignments(row)}
const loadPersonProfile=async personId=>{if(personProfileCache[personId])return;personProfileLoadingId.value=personId;try{personProfileCache[personId]=await ops.getAccountPersonProfile(personId)}catch(error){ElMessage.error(error.detail||'加载标注员信息失败')}finally{personProfileLoadingId.value=''}}
const beforeUnload=event=>{if(!dirtyCount.value&&!sheetDirtyCount.value)return;event.preventDefault();event.returnValue=''}
onBeforeRouteLeave(async()=>await discardDrafts())
watch(viewMode,value=>emit('focus-mode-change',value==='project'),{immediate:true})
onActivated(()=>emit('focus-mode-change',viewMode.value==='project'))
onDeactivated(()=>emit('focus-mode-change',false))
onMounted(async()=>{const results=await Promise.allSettled([projectApi.getAnnotationProjects({skip:0,limit:500}),talentApi.getProjectTalentOptions('annotation'),getUsers({skip:0,limit:500}),loadFields()]);projects.value=results[0].status==='fulfilled'?results[0].value:[];talents.value=results[1].status==='fulfilled'?results[1].value:[];users.value=results[2].status==='fulfilled'&&Array.isArray(results[2].value)?results[2].value:[];const routeProject=projects.value.find(item=>String(item.id)===String(route.query.projectId||''));if(routeProject?.clientId){clientId.value=routeProject.clientId;projectId.value=routeProject.id;viewMode.value='assets';syncAssignmentLanguage();try{const client=await clientApi.getClient(routeProject.clientId);clients.value=client?[client]:[]}catch(error){ElMessage.error(error.detail||'加载项目客户失败')}await Promise.all([loadPlatforms(),loadProjectFields()])}await reload()})
onMounted(()=>window.addEventListener('beforeunload',beforeUnload))
onBeforeUnmount(()=>{emit('focus-mode-change',false);clearTimeout(timer);clearTimeout(clientSearchTimer);controller?.abort();clientSearchController?.abort();window.removeEventListener('beforeunload',beforeUnload)})
</script>

<style scoped>
.header>.actions,.focus-header>.actions{flex-wrap:wrap;justify-content:flex-end}
.focus-header,.focus-header__title{display:flex;align-items:center}.focus-header{justify-content:space-between;gap:16px}.focus-header__title{min-width:0;gap:12px}.focus-header__title h2{max-width:min(720px,45vw);margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:18px}.focus-header__title p{margin:2px 0 0;color:var(--el-text-color-secondary);font-size:12px}.focus-header__divider{width:1px;height:30px;background:var(--el-border-color)}
.annotation-accounts--focus :deep(.el-card__header){padding:10px 14px}.annotation-accounts--focus :deep(.el-card__body){padding:10px 12px 12px}.filters--focus{margin-bottom:8px}.filters--focus .el-input{flex:1;max-width:520px}
.project-sheet-context{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px;padding:12px 16px;border:1px solid var(--el-color-primary-light-7);border-radius:8px;background:var(--el-color-primary-light-9)}
.project-sheet-context__label{margin-right:10px;color:var(--el-text-color-secondary);font-size:13px}.project-sheet-context__meta{display:flex;align-items:center;gap:10px;color:var(--el-text-color-secondary);font-size:13px}
.header,.actions,.filters,.panel-title,.platform-row,.advanced-actions,.sheet-toolbar,.assignment-language-field{display:flex;align-items:center}.header,.panel-title,.platform-row,.advanced-actions{justify-content:space-between}.header h2{margin:0}.header p{margin:4px 0 0;color:var(--el-text-color-secondary)}.actions,.filters,.sheet-toolbar{gap:8px}.disabled-button-wrapper{display:inline-flex}.filters{margin-bottom:16px;flex-wrap:wrap}.assignment-language-field{gap:6px}.language-help{color:var(--el-text-color-secondary);cursor:help}.sheet-toolbar{margin-bottom:12px;flex-wrap:wrap}.inline-person-editor{display:flex;align-items:center;gap:4px}.inline-person-editor .el-select{min-width:0;flex:1}.platform-link{display:inline-flex;max-width:100%}.platform-link :deep(.el-link__inner){display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.batch-defaults{margin-bottom:14px;padding:14px;border:1px solid var(--el-border-color);border-radius:6px;background:var(--el-fill-color-lighter)}.batch-defaults-title{display:flex;align-items:center;gap:12px;margin-bottom:10px}.batch-defaults-title span,.sheet-tip,.common-summary{color:var(--el-text-color-secondary);font-size:12px}.batch-defaults-form{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:12px}.batch-defaults-form :deep(.el-form-item){margin-bottom:0}.batch-defaults-form :deep(.el-select),.batch-defaults-form :deep(.el-date-editor){width:100%}.sheet-wrap{width:100%;overflow:hidden}.platform-manager,.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.platform-row{gap:16px;padding:12px 0;border-top:1px solid var(--el-border-color-lighter)}.platform-info{min-width:0}.platform-info span{display:block;margin-top:4px;overflow:hidden;color:var(--el-text-color-secondary);text-overflow:ellipsis;white-space:nowrap}.advanced-title{margin-bottom:14px;font-weight:600}.detail-content{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.pagination{display:flex;justify-content:flex-end;margin-top:16px}:deep(.row-dirty td.el-table__cell){background:var(--el-color-warning-light-9)}:deep(.row-error td.el-table__cell){background:var(--el-color-danger-light-9)}:deep(.long-dialog){display:flex;max-height:90vh;overflow:hidden;flex-direction:column}:deep(.long-dialog .el-dialog__header),:deep(.long-dialog .el-dialog__footer){flex-shrink:0}:deep(.long-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:deep(.long-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
@media(max-width:1200px){.batch-defaults-form{grid-template-columns:repeat(3,minmax(160px,1fr))}}@media(max-width:768px){.header,.focus-header,.focus-header__title,.project-sheet-context,.project-sheet-context__meta{align-items:flex-start;flex-direction:column;gap:12px}.focus-header__divider{display:none}.focus-header__title h2{max-width:calc(100vw - 72px)}.batch-defaults-form{grid-template-columns:1fr}.pagination{overflow-x:auto;justify-content:flex-start}}
</style>

<style>
.account-advanced-popper{max-width:calc(100vw - 32px)}.account-detail-popper,.account-person-popper{max-width:calc(100vw - 32px)}.account-person-popper .person-detail-content{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.platform-manager-popper{max-width:calc(100vw - 32px)}
</style>
