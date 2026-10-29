<template>
  <el-card class="common-page-card talent-card compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">{{ pageTitle }}</span>
          <span class="page-subtitle">人员基础资料统一维护，专业能力按需启用</span>
        </div>
        <div class="header-actions">
          <TalentResourceTools @saved="pathRecordSaved" />
          <el-button v-if="!deleteMode" @click="openDuplicateReview()">同名核重</el-button>
          <TableColumnSettings :settings-key="`talent-pool:${isRecruitmentPool ? 'recruitment' : (capabilityType || 'all')}`" v-model="settingsVisibleColumnKeys" :columns="settingsColumns" :column-count="2" @reset="resetColumns" />
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite && !deleteMode" type="primary" title="左键新增，右键快速登记" @click="openCreate" @contextmenu.prevent.stop="openQuickCreate">新增人才</el-button>
        </div>
      </div>
    </template>

    <TalentResourceNav />

    <AppForm :inline="true" :model="search" class="search-form project-list-search-form">
      <div class="project-list-primary-filters">
        <el-form-item label="关键词" class="project-list-keyword-filter">
          <el-input v-model="search.keyword" clearable :placeholder="canViewContacts ? '姓名、编号、电话或邮箱' : '姓名或编号'" @input="handleTextInput" @keyup.enter="searchNow" />
        </el-form-item>
        <el-form-item label="状态" class="project-list-status-filter">
          <el-select v-model="search.status" multiple collapse-tags :max-collapse-tags="1" clearable placeholder="全部状态" @change="searchNow">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item class="project-list-search-actions">
        <el-button type="primary" @click="searchNow">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" popper-class="talent-advanced-popper" @clear="clearAdvanced" @reset="resetSearch">
          <CompactFilterGrid :fields="talentAdvancedFilterFields" :model="search" @update="updateConfiguredFilter" @text-input="handleConfiguredTextInput" @change="searchNow" @enter="searchNow" />
          <div v-if="!isRecruitmentPool" class="performance-sort-controls">
            <label>
              <span>评分排序字段</span>
              <el-select v-model="performanceSortField" clearable placeholder="默认按最近更新" size="small" @change="handlePerformanceSortChange">
                <el-option v-for="item in performanceSortOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </label>
            <label>
              <span>排序方式</span>
              <el-select v-model="performanceSortDirection" :disabled="!performanceSortField" size="small" @change="handlePerformanceSortChange">
                <el-option label="从高到低" value="desc" />
                <el-option label="从低到高" value="asc" />
              </el-select>
            </label>
          </div>
        </AdvancedFilterPopover>
      </el-form-item>
    </AppForm>

    <el-table ref="talentTableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
<OrderedTableColumns :settings-key="`talent-pool:${isRecruitmentPool ? 'recruitment' : (capabilityType || 'all')}`">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="index" label="序号" width="64" align="center" fixed="left" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :fixed="column.key==='resourceCode'?'left':undefined" :show-overflow-tooltip="column.tooltip !== false">
        <template #header>
          <ConfiguredColumnHeaderFilter v-if="headerFilterDefinition(column.key)" :definition="headerFilterDefinition(column.key)" :model="search" :model-value="search[headerFilterDefinition(column.key).key]" @update:model-value="search[headerFilterDefinition(column.key).key]=$event" @update-field="updateConfiguredFilter" @text-input="handleConfiguredTextInput" @change="searchNow" @enter="searchNow" @clear="searchNow">
            <template #label><ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" /><span v-else>{{ column.label }}</span></template>
          </ConfiguredColumnHeaderFilter>
          <template v-else><ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" /><span v-else>{{ column.label }}</span></template>
        </template>
        <template #default="{ row }">
          <el-button v-if="column.key === 'resourceCode'" type="primary" link class="business-clickable-cell" @click.stop="openTalentDetail(row)">{{ row.resourceCode || '未生成编号' }}</el-button>
          <el-popover v-else-if="column.key === 'fullName'" trigger="click" placement="left" :width="760" :title="`${displayTalentName(row, '人才')} 姓名与联系方式`" popper-class="talent-detail-popper" @show="loadDetail(row.id)">
            <template #reference>
              <span class="talent-name-cell" @click.stop>
                <el-button type="primary" link class="talent-name-link business-clickable-cell" :title="`${displayTalentName(row)}（点击查看详情）`">{{ displayTalentName(row) }}</el-button>
                <el-tag v-if="row.nameDuplicate" :type="row.nameReviewState === 'different' ? 'info' : 'warning'" size="small" class="duplicate-review-link" title="点击进入同名核重，比较资料并确认身份" @click.stop="openDuplicateReview(row)">{{ row.nameReviewState === 'different' ? '同名·已区分' : '同名' }}</el-tag>
              </span>
            </template>
            <TalentDetailContent v-loading="detailLoadingId === row.id" :detail="detailFor(row)" section="identity" />
          </el-popover>
          <el-popover v-else-if="summarySection(column.key)" trigger="click" placement="left" :width="760" :title="`${displayTalentName(row, '人才')} ${column.label}`" popper-class="talent-detail-popper" @show="loadDetail(row.id)">
            <template #reference><el-button type="primary" link class="business-clickable-cell" :title="summaryHover(column.key,row)" @click.stop>{{ tableDisplay(column,row) }}</el-button></template>
            <TalentDetailContent v-loading="detailLoadingId === row.id" :detail="detailFor(row)" :section="summarySection(column.key)" />
          </el-popover>
          <el-popover v-else-if="column.key === 'overallRating'" trigger="click" placement="left" :width="760" :title="`${displayTalentName(row, '人才')} 综合表现`" popper-class="talent-detail-popper" @show="loadDetail(row.id)">
            <template #reference><el-button type="primary" link class="business-clickable-cell performance-summary-cell" title="点击查看完整综合表现" @click.stop>{{ overallPerformanceSummary(row) }}</el-button></template>
            <TalentDetailContent v-loading="detailLoadingId === row.id" :detail="detailFor(row)" section="performance" />
          </el-popover>
          <TalentProjectSituationPopover
            v-else-if="column.key === 'projectSituation'"
            :person-id="row.id"
            :person-name="displayTalentName(row, '人才')"
            :summary="row.projectSituation"
          />
          <div v-else-if="column.key === 'capabilityTypes'" class="tag-list"><el-tag v-for="item in row.capabilityTypes" :key="item" size="small">{{ capabilityLabel(item) }}</el-tag><span v-if="!row.capabilityTypes?.length">-</span></div>
          <el-tag v-else-if="column.key === 'annotationWillingness' && row.annotationWillingness" :type="annotationWillingnessType(row.annotationWillingness)" size="small">{{ annotationWillingnessLabel(row.annotationWillingness) }}</el-tag>
          <span v-else-if="column.key === 'annotationWillingness'">-</span>
          <el-dropdown
            v-else-if="column.key === 'status' && canWrite"
            trigger="click"
            :disabled="statusSavingIds.has(row.id)"
            @command="(command) => changeStatus(row, command)"
          >
            <el-tag
              :type="statusType(row.status)"
              size="small"
              class="status-switch-tag"
              :class="{ 'is-updating': statusSavingIds.has(row.id) }"
            >
              <span class="status-switch-text">{{ statusLabel(row.status) }}</span>
              <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
            </el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="item in statusOptions"
                  :key="item.value"
                  :command="item.value"
                  :disabled="item.value === row.status || statusSavingIds.has(row.id)"
                >
                  <span class="status-option-row">
                    <el-tag :type="statusType(item.value)" size="small" effect="plain">{{ item.label }}</el-tag>
                    <el-icon v-if="item.value === row.status" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tag v-else-if="column.key === 'status'" :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          <el-tag v-else-if="column.key === 'duplicateReviewRequired' && row.duplicateReviewRequired" type="warning" size="small">待核重</el-tag>
          <span v-else-if="column.key === 'duplicateReviewRequired'">-</span>
          <SensitiveContactValue v-else-if="contactColumnKeys.has(column.key)" :value="row[column.key]" :restricted="row.contactRestricted === true" />
          <span v-else>{{ tableDisplay(column, row) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <div v-if="canWrite" class="action-buttons">
            <PrimaryEditButton @click="openEdit(row)" />
          </div>
        </template>
      </el-table-column>
    </OrderedTableColumns>
</el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @current-change="fetchData" @size-change="handleSizeChange" />

    <DraggableFormDialog v-model="detailVisible" width="min(1120px, calc(100vw - 32px))" top="5vh" class="talent-detail-dialog" destroy-on-close>
      <template #header><span class="talent-detail-title" @mousedown.stop>{{ selectedDetail.resourceCode || '人才' }} · {{ displayTalentName(selectedDetail) }} 详情</span></template>
      <TalentDetailContent v-loading="detailLoadingId===selectedDetail.id" :detail="detailFor(selectedDetail)" :projects="projectCache[selectedDetail.id] || []" :projects-loading="projectsLoading" :projects-error="projectsError" :show-performance="!isRecruitmentPool" :show-annotation-willingness="!isRecruitmentPool" in-dialog @reload-projects="loadFullDetail(selectedDetail)" />
      <template #footer><el-button @click="detailVisible=false">关闭</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="editorVisible" width="min(1120px, calc(100vw - 32px))" top="5vh" class="talent-editor-dialog" :before-close="beforeEditorClose" :close-on-click-modal="!saving" :close-on-press-escape="!saving" @open="onEditorOpened" @closed="onEditorClosed">
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          :inert="saving"
          v-model="fieldSearchKeyword"
          :title="editorTitle"
          subtitle="按业务分区填写，带 * 的项目为必填项"
          :fetch-suggestions="fetchFieldSuggestions"
          placeholder="搜索人才表单字段，如出生日期"
          @select="locateDialogField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="editorBodyRef" class="talent-editor-body" :inert="saving" :aria-busy="saving">
        <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" class="talent-editor-form"><el-tabs v-model="resumeTab"><el-tab-pane label="中文简历" name="zh"><CollapsibleSections :reset-key="editorSectionsKey">
        <template #actions><TalentResumeYear v-model="form.resumeProfile.resumeYear" field-path="resumeProfile.resumeYear" /></template>
        <el-collapse-item  name="editor-section-1" data-section-key="editor-section-1" title="姓名与身份"><div class="form-section">
          <div class="form-section-header name-section-header">
            <div><h3><span class="required-mark">*</span> 姓名与身份</h3><div class="section-hint">中文姓名、外文姓名、昵称、其他名字至少填写一项</div></div>
            <el-button text type="primary" :aria-expanded="nameFieldsExpanded" @click="nameFieldsExpanded=!nameFieldsExpanded">{{ nameFieldsExpanded ? '收起姓名' : '展开姓名' }}</el-button>
          </div>
          <el-collapse-transition>
            <div v-show="nameFieldsExpanded">
              <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="中文姓名" prop="nameGroup"><el-input v-model="form.chineseName" @input="validateNameGroupField" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="外文姓名"><el-input v-model="form.englishName" @input="validateNameGroupField" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="昵称"><el-input v-model="form.nickname" @input="validateNameGroupField" /></el-form-item></el-col></el-row>
              <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="其他名字"><el-input v-model="otherNamesText" type="textarea" :autosize="{minRows:1,maxRows:4}" placeholder="直接输入，多个名字可换行填写" @input="validateNameGroupField" /></el-form-item></el-col></el-row>
            </div>
          </el-collapse-transition>
          <el-row v-if="canViewContacts" :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="身份证号码" prop="identityNumber"><el-input v-model="form.identityNumber" maxlength="50" placeholder="请输入身份证号码" /></el-form-item></el-col></el-row>
          <div v-if="!nameFieldsExpanded" class="name-collapsed-summary">当前显示名：{{ preferredFormName || '尚未填写' }}<span v-if="filledNameCount">（已填写 {{ filledNameCount }} 项）</span></div>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="人才编号"><ReadonlyField :model-value="form.resourceCode" source="auto" placeholder="保存后自动生成" tooltip="人才编号由系统自动生成，可选中复制" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="档案状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col v-if="!isRecruitmentPool" :xs="24" :md="8"><el-form-item label="标注意愿"><el-select v-model="form.annotationWillingness" clearable placeholder="请选择低、中或高" style="width:100%"><el-option v-for="item in willingnessOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col></el-row>
          <el-form-item v-if="!isRecruitmentPool" label="专业能力" prop="capabilityTypes"><el-checkbox-group v-model="form.capabilityTypes"><el-checkbox value="written_translation">笔译</el-checkbox><el-checkbox value="interpretation">口译</el-checkbox><el-checkbox value="annotation">标注</el-checkbox></el-checkbox-group></el-form-item>
        </div></el-collapse-item>
        <el-collapse-item name="editor-section-2" data-section-key="editor-section-2" title="联系方式"><div class="form-section"><h3>联系方式</h3>
          <el-alert v-if="!canViewContacts" title="可录入联系方式，但无权查看已保存的内容；编辑时留空保留原值，填写新值将替换原值。" type="info" :closable="false" show-icon />
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="手机"><el-input v-model="form.primaryPhone" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="备用电话"><el-input v-model="form.secondaryPhone" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="微信"><el-input v-model="form.wechat" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="邮箱"><el-input v-model="form.primaryEmail" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="备用邮箱"><el-input v-model="form.secondaryEmail" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="WhatsApp"><el-input v-model="form.whatsapp" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="Skype"><el-input v-model="form.skype" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="Line"><el-input v-model="form.line" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="其他"><el-input v-model="form.otherContact" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="可联系时段" prop="contactAvailability"><el-select v-model="form.contactAvailability" clearable placeholder="请选择可联系时段" style="width:100%"><el-option v-for="item in contactAvailabilityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><small class="wechat-account-hint">按人才所在地时区填写</small></el-form-item></el-col></el-row>
        </div></el-collapse-item>
        <el-collapse-item  name="editor-section-3" data-section-key="editor-section-3" title="基本信息"><div class="form-section"><h3>基本信息</h3>
          <el-row :gutter="16"><el-col :xs="24" :md="12">
            <el-form-item label="所在微信" prop="wechatAccounts">
              <CompanyWechatAccountSelect v-model="form.wechatAccounts" include-deleted />
              <small class="wechat-account-hint">删除标记表示对应渠道有删友情况，账号名称仍保留；取消“已删微信/企微”会将关联开拓记录对应渠道恢复为“已添加”。</small>
            </el-form-item>
          </el-col></el-row>
          <el-row :gutter="16">
            <el-col :xs="24" :md="16"><el-form-item label="所在企微小群" prop="wechatGroups"><el-input v-model="form.wechatGroups" type="textarea" :autosize="{minRows:2,maxRows:5}" maxlength="4000" show-word-limit placeholder="一行填写一个企微小群名称" /></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="企微小群状态"><ReadonlyField :model-value="form.wecomSmallGroupStatus || (form.id ? '尚未关联开拓记录' : '关联开拓记录后自动带出')" source="auto" tooltip="自动读取资源开拓中企微小群的最新状态，请在资源开拓中维护" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :xs="24" :md="16"><el-form-item label="所在企微大群" prop="wecomLargeGroups"><el-input v-model="form.wecomLargeGroups" type="textarea" :autosize="{minRows:2,maxRows:5}" maxlength="4000" show-word-limit placeholder="一行填写一个企微大群名称" /></el-form-item></el-col>
            <el-col :xs="24" :md="8"><el-form-item label="企微大群状态"><ReadonlyField :model-value="form.wecomLargeGroupStatus || (form.id ? '尚未关联开拓记录' : '关联开拓记录后自动带出')" source="auto" tooltip="自动读取资源开拓中企微大群的最新状态，请在资源开拓中维护" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="来源" prop="registrationSource"><el-input v-model="form.registrationSource" maxlength="255" placeholder="例如：2609资源整合行动" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="性别"><el-select v-model="form.gender" clearable placeholder="请选择性别" style="width:100%"><el-option v-for="item in genderOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="出生年月"><el-date-picker v-model="form.birthYearMonth" type="month" value-format="YYYY-MM" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="年龄" prop="reportedAge"><ReadonlyField v-if="form.birthYearMonth || form.birthDate" :model-value="calculatedAge" source="auto" tooltip="根据出生年月自动计算" /><el-input-number v-else v-model="form.reportedAge" :min="0" :max="120" :precision="0" controls-position="right" placeholder="登记年龄" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="合作形式"><el-select v-model="form.cooperationType" clearable style="width:100%"><el-option v-for="item in cooperationOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="国籍"><el-input v-model="form.nationality" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="民族"><el-input v-model="form.ethnicity" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="身高"><el-input v-model="form.height" placeholder="例如：175cm" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="容貌"><el-input v-model="form.appearance" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="职业状态"><el-select v-model="form.employmentStatus" clearable style="width:100%"><el-option v-for="item in employmentOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="16"><el-form-item label="具体说明"><el-input v-model="form.employmentDetail" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="视力" prop="eyesight"><el-input v-model="form.eyesight" maxlength="255" placeholder="可填写裸眼、矫正视力或左右眼情况" /></el-form-item></el-col></el-row>
          <el-row v-if="form.employmentStatus==='student'" :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="学习阶段"><el-input v-model="form.studentStage" placeholder="例如：本科" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="入学年份"><el-input-number v-model="form.enrollmentYear" :min="1900" :max="2200" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="学制"><el-input-number v-model="form.programDurationYears" :min="1" :max="15" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="当前年级"><ReadonlyField :model-value="studentGrade" source="auto" tooltip="默认按每年9月进入下一学年" /></el-form-item></el-col></el-row>
        </div></el-collapse-item>
        <el-collapse-item  name="editor-section-4" data-section-key="editor-section-4" title="区域信息"><div class="form-section"><h3>区域信息</h3><el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="籍贯" prop="ancestralHome"><el-input v-model="form.ancestralHome" maxlength="255" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="主要成长地"><el-input v-model="form.nativePlace" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="目前所在地"><el-input v-model="form.residenceAddress" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="时区" prop="residenceTimezone"><el-select v-model="form.residenceTimezone" clearable filterable placeholder="例如 UTC+8" style="width:100%"><el-option v-for="item in talentTimezoneOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col></el-row></div></el-collapse-item>

        <el-collapse-item  name="editor-section-5" data-section-key="editor-section-5" title="学历信息"><div class="form-section"><h3>学历信息</h3>
          <el-form-item label="最高学历"><el-select v-model="form.highestEducation" clearable style="width:100%"><el-option v-for="item in educationOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        </div></el-collapse-item>

        <el-collapse-item  name="editor-section-6" data-section-key="editor-section-6" title="语言情况与证书"><div class="form-section"><h3>语言情况与证书</h3>
          <el-alert title="新建人才默认添加“汉语 / Chinese”为母语，请按实际情况调整。" type="info" :closable="false" show-icon />
          <div v-for="(item,index) in form.languageSkills" :key="item._key || item.id" class="sub-record" data-dialog-field-search-group><span data-dialog-field-search-group-title>语言记录 {{index+1}}</span>
            <el-row :gutter="12"><el-col :xs="24" :md="8"><el-form-item label="语言"><el-select v-model="item.languageId" filterable :filter-method="filterTalentLanguages" @visible-change="visible=>!visible&&(languageKeyword='')" style="width:100%"><el-option v-for="language in filteredLanguages" :key="language.id" :label="languageDisplay(language)" :value="language.id" /></el-select></el-form-item></el-col><el-col :xs="24" :md="5"><el-form-item label="类型"><el-select v-model="item.role" @change="normalizeLanguagePriorities" style="width:100%"><el-option v-for="option in languageRoleOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="4"><el-form-item label="顺序"><el-input-number v-model="item.priority" :min="0" :max="9" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="5"><el-form-item label="熟悉程度"><el-select v-model="item.proficiency" clearable style="width:100%"><el-option v-for="option in proficiencyOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="口音"><el-input v-model="item.accent" maxlength="255" placeholder="该语言的口音" /></el-form-item></el-col><el-col :xs="24" :md="2"><el-button type="danger" link @click="removeLanguage(index)">删除</el-button></el-col></el-row>
          </div>
          <el-button @click="addLanguage">添加语言</el-button>
          <el-divider />
          <div v-for="(item,index) in form.certificates" :key="item._key || item.id" class="sub-record"><el-row :gutter="12"><el-col :xs="24" :md="5"><el-form-item label="证书类型"><el-select v-model="item.certificateType" style="width:100%"><el-option label="外语类" value="language" /><el-option label="其他类" value="other" /></el-select></el-form-item></el-col><el-col :xs="24" :md="7"><el-form-item label="证书名称"><el-input v-model="item.name" /></el-form-item></el-col><el-col :xs="24" :md="5"><el-form-item label="发证机构"><el-input v-model="item.issuer" /></el-form-item></el-col><el-col :xs="24" :md="5"><el-form-item label="是否发来"><el-switch v-model="item.materialReceived" /></el-form-item></el-col><el-col :xs="24" :md="2"><el-button type="danger" link @click="removeCertificate(index)">删除</el-button></el-col></el-row></div>
          <el-button @click="addCertificate">添加证书</el-button>
        </div></el-collapse-item>

        <el-collapse-item name="editor-education-experience" data-section-key="editor-education-experience" title="教育经历"><div class="form-section"><h3>教育经历</h3><ResumeExperienceGrid v-model="form.educationExperiences" prop-prefix="educationExperiences" education canonical-education group-title="教育经历" /></div></el-collapse-item>
        <el-collapse-item name="editor-internships" data-section-key="editor-internships" title="实习经历"><div class="form-section"><h3>实习经历</h3><ResumeExperienceGrid v-model="form.resumeProfile.internships" prop-prefix="resumeProfile.internships" group-title="实习经历" /></div></el-collapse-item>
        <el-collapse-item name="editor-section-7" data-section-key="editor-section-7" title="工作经验"><div class="form-section"><h3>工作经验</h3>
          <el-collapse-item v-for="group in resumeWorkGroups" :key="group.key" :name="`editor-work-${group.key}`" :data-section-key="`editor-work-${group.key}`" :title="group.label"><ResumeExperienceGrid v-model="form.resumeProfile[group.key]" :prop-prefix="`resumeProfile.${group.key}`" :group-title="group.label" :interpretation="group.key=== 'interpretation'" :annotation="group.key=== 'annotation'" /></el-collapse-item>
        </div></el-collapse-item>
        <el-collapse-item v-if="!isRecruitmentPool" name="editor-section-8" data-section-key="editor-section-8" title="综合表现"><div v-if="!isRecruitmentPool" class="form-section performance-form-section">
          <h3>综合表现</h3>
          <el-row :gutter="16">
            <el-col :xs="24" :md="8"><el-form-item label="人才分级" prop="talentGrade"><el-select v-model="form.talentGrade" style="width:100%"><el-option v-for="item in talentGradeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><TalentEvaluationMeta :evaluation="form" group-key="talent_grade" editing /></el-form-item></el-col>
          </el-row>
          <div class="performance-form-grid">
            <div class="performance-form-item" data-dialog-field-search-group>
              <h4 data-dialog-field-search-group-title>配合度</h4><TalentEvaluationMeta :evaluation="form" group-key="cooperation" editing />
              <el-form-item label="等级"><el-select v-model="form.cooperationLevel" clearable placeholder="高/中/低" style="width:100%"><el-option v-for="item in performanceLevelOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
              <el-form-item label="说明"><el-input v-model="form.cooperationNote" type="textarea" :rows="2" /></el-form-item>
            </div>
            <div class="performance-form-item" data-dialog-field-search-group>
              <h4 data-dialog-field-search-group-title>守时度</h4><TalentEvaluationMeta :evaluation="form" group-key="punctuality" editing />
              <el-form-item label="等级"><el-select v-model="form.punctualityLevel" clearable placeholder="高/中/低" style="width:100%"><el-option v-for="item in performanceLevelOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
              <el-form-item label="说明"><el-input v-model="form.punctualityNote" type="textarea" :rows="2" /></el-form-item>
            </div>
          </div>
          <el-collapse-item  name="editor-section-9" data-section-key="editor-section-9" title="标注"><div class="performance-domain" data-dialog-field-search-group>
            <h4 data-dialog-field-search-group-title>标注</h4><el-form-item label="上传样音"><TalentMediaSamples :person-id="form.id" category="annotation_sample" :attachments="form.attachments" v-model:pending="queuedAttachments.annotation_sample" editable @remove="removeSavedAttachment" /></el-form-item>
          <div class="performance-form-item performance-form-item--overall" data-dialog-field-search-group>
            <h5 data-dialog-field-search-group-title>总体评价</h5><TalentEvaluationMeta :evaluation="form" group-key="overall" editing />
            <el-row :gutter="16">
              <el-col :xs="24" :md="6"><el-form-item label="总体评分"><el-input-number v-model="form.overallScore" :min="1" :max="10" :step="1" :precision="0" controls-position="right" placeholder="1-10分" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="18"><el-form-item label="具体评价"><el-input v-model="form.overallRating" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
          </div>
          <div class="performance-form-grid">
            <div v-for="item in performanceScoreEditors" :key="item.scoreKey" class="performance-form-item" data-dialog-field-search-group>
              <h5 data-dialog-field-search-group-title>{{ item.label }}</h5><TalentEvaluationMeta :evaluation="form" :group-key="item.auditKey" editing />
              <el-form-item label="总体评分"><el-input-number v-model="form[item.scoreKey]" :min="1" :max="10" :step="1" :precision="0" controls-position="right" placeholder="1-10分" style="width:100%" /></el-form-item>
              <el-form-item label="具体评价"><el-input v-model="form[item.evaluationKey]" type="textarea" :rows="2" /></el-form-item>
            </div>
          </div>
          </div></el-collapse-item>
          <el-collapse-item  name="editor-section-10" data-section-key="editor-section-10" title="口译"><div class="performance-domain" data-dialog-field-search-group>
            <h4 data-dialog-field-search-group-title>口译</h4><el-form-item label="上传样音"><TalentMediaSamples :person-id="form.id" category="interpretation_sample" :attachments="form.attachments" v-model:pending="queuedAttachments.interpretation_sample" editable @remove="removeSavedAttachment" /></el-form-item><TalentEvaluationMeta :evaluation="form" group-key="interpretation" editing />
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="口译员评级" prop="interpretationRating"><el-select v-model="form.interpretationRating" clearable placeholder="请选择一星至六星" style="width:100%"><el-option v-for="item in interpretationRatingOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><small class="performance-rating-hint">{{ interpretationRatingHint }}</small></el-form-item></el-col>
              <el-col :xs="24" :md="16"><el-form-item label="说明" prop="interpretationRatingNote" data-dialog-field-search-aliases="口译说明 口译员评级说明"><el-input v-model="form.interpretationRatingNote" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="口译领域" prop="interpretationDomains"><el-input v-model="form.interpretationDomains" type="textarea" :rows="2" /></el-form-item>
          </div></el-collapse-item>
          <el-collapse-item  name="editor-section-11" data-section-key="editor-section-11" title="笔译"><div class="performance-domain" data-dialog-field-search-group>
            <h4 data-dialog-field-search-group-title>笔译</h4><el-form-item label="常用CAT经验" prop="resumeProfile.catTools"><el-select v-model="form.resumeProfile.catTools" multiple filterable allow-create default-first-option placeholder="选择常用CAT工具，可补充其他工具"><el-option v-for="item in catToolOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><TalentEvaluationMeta :evaluation="form" group-key="written_translation" editing />
            <el-row :gutter="16">
              <el-col :xs="24" :md="6"><el-form-item label="总体评价" prop="writtenTranslationScore" data-dialog-field-search-aliases="笔译评分 笔译总体评价"><el-input-number v-model="form.writtenTranslationScore" :min="1" :max="10" :step="1" :precision="0" controls-position="right" placeholder="1-10分" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="18"><el-form-item label="具体评价" prop="writtenTranslationEvaluation" data-dialog-field-search-aliases="笔译具体评价"><el-input v-model="form.writtenTranslationEvaluation" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
          </div></el-collapse-item>
        </div></el-collapse-item>
        <el-collapse-item v-if="!isRecruitmentPool && hasCapability('written_translation')" name="editor-section-12" data-section-key="editor-section-12" title="笔译能力"><div v-if="!isRecruitmentPool && hasCapability('written_translation')" class="form-section"><h3>笔译能力</h3><TalentEvaluationMeta :evaluation="form" group-key="written_profile" editing />
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="语种方向"><el-input v-model="form.writtenProfile.languages" placeholder="例如：中英、中日" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="翻译方向"><el-input v-model="form.writtenProfile.direction" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="质量评分"><el-input v-model="form.writtenProfile.qualityScore" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="领域技能"><el-select v-model="form.writtenProfile.domainSkills" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="默认优先级"><el-input-number v-model="form.writtenProfile.defaultPriority" :min="0" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="日产接单数"><el-input-number v-model="form.writtenProfile.dailyAcceptCount" :min="0" style="width:100%" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="时速"><el-input-number v-model="form.writtenProfile.hourlySpeed" :min="0" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="日产能"><el-input-number v-model="form.writtenProfile.dailyWordCapacity" :min="0" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="云编辑"><el-switch v-model="form.writtenProfile.canCloudEdit" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="审校"><el-switch v-model="form.writtenProfile.canRevision" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="可用时段"><el-input v-model="form.writtenProfile.availableTimeSlot" /></el-form-item></el-col><el-col :xs="24" :md="16"><el-form-item label="排班备注"><el-input v-model="form.writtenProfile.scheduleRemarks" /></el-form-item></el-col></el-row>
        </div></el-collapse-item>
        <el-collapse-item v-if="!isRecruitmentPool && hasCapability('interpretation')" name="editor-section-13" data-section-key="editor-section-13" title="口译能力"><div v-if="!isRecruitmentPool && hasCapability('interpretation')" class="form-section"><h3>口译能力</h3><TalentEvaluationMeta :evaluation="form" group-key="interpretation_profile" editing />
          <el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="语种方向"><el-input v-model="form.interpretationProfile.languages" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="翻译方向"><el-input v-model="form.interpretationProfile.direction" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="口译等级"><el-select v-model="form.interpretationProfile.interpretationLevel" clearable style="width:100%"><el-option label="初级" value="初级" /><el-option label="中级" value="中级" /><el-option label="高级" value="高级" /></el-select></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="口译方式"><el-select v-model="form.interpretationProfile.interpretationModes" multiple style="width:100%"><el-option label="同传" value="simultaneous" /><el-option label="交传" value="consecutive" /></el-select></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="领域技能"><el-select v-model="form.interpretationProfile.domainSkills" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="质量评分"><el-input v-model="form.interpretationProfile.qualityScore" /></el-form-item></el-col></el-row>
          <el-form-item label="评价概述"><el-input v-model="form.interpretationProfile.evaluationSummary" type="textarea" :rows="2" /></el-form-item>
        </div></el-collapse-item>
        <el-collapse-item v-if="!isRecruitmentPool && hasCapability('annotation')" name="editor-section-14" data-section-key="editor-section-14" title="标注能力"><div v-if="!isRecruitmentPool && hasCapability('annotation')" class="form-section">
          <h3>标注能力</h3><TalentEvaluationMeta :evaluation="form" group-key="annotation_profile" editing />
          <el-form-item label="语言方向"><LanguageDirectionsEditor v-model="form.annotationLanguageSkills" /></el-form-item>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="任务类型"><el-select v-model="form.annotationProfile.taskTypes" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="数据模态"><el-select v-model="form.annotationProfile.dataModalities" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="工具经验"><el-select v-model="form.annotationProfile.tools" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="质量评分"><el-input v-model="form.annotationProfile.qualityScore" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="日产能"><el-input-number v-model="form.annotationProfile.dailyCapacity" :min="0" style="width:100%" /></el-form-item></el-col></el-row>
          <el-form-item label="领域技能"><el-select v-model="form.annotationProfile.domainSkills" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item>
          <el-form-item label="标注备注"><el-input v-model="form.annotationProfile.remarks" type="textarea" :rows="2" /></el-form-item>
        </div></el-collapse-item>
        <el-collapse-item  name="editor-section-15" data-section-key="editor-section-15" title="招聘职业档案"><div class="form-section"><h3>招聘职业档案</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="行业"><el-select v-model="form.careerProfile.industries" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="职能"><el-select v-model="form.careerProfile.functions" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="岗位"><el-select v-model="form.careerProfile.jobTitles" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col></el-row><el-row :gutter="16"><el-col :xs="24" :md="6"><el-form-item label="工作年限"><el-input-number v-model="form.careerProfile.yearsExperience" :min="0" :precision="1" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="期望地点"><el-select v-model="form.careerProfile.preferredLocations" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="6"><el-form-item label="期望薪资"><el-input v-model="form.careerProfile.expectedSalary" /></el-form-item></el-col></el-row><el-form-item label="职业概述"><el-input v-model="form.careerProfile.summary" type="textarea" :rows="2" /></el-form-item></div></el-collapse-item>
        <el-collapse-item v-if="canViewContacts" name="editor-settlement" data-section-key="editor-settlement" title="商务与结算"><div class="form-section"><h3>商务与结算</h3><TalentSettlementEditor :model-value="form.settlement" /></div></el-collapse-item>
        <el-collapse-item  name="editor-section-16" data-section-key="editor-section-16" title="照片与音频"><div class="form-section"><h3>照片与音频</h3>
          <el-row :gutter="16"><el-col v-for="category in talentPhotoCategories" :key="category.value" :xs="24" :md="12"><el-form-item :label="category.label"><div><el-upload v-model:file-list="queuedAttachments[category.value]" :auto-upload="false" multiple accept=".jpg,.jpeg,.png,.webp" :on-change="file=>queueAttachment(category.value,file)" :on-remove="file=>unqueueAttachment(category.value,file)"><el-button>选择{{category.label}}</el-button><template #tip><div class="el-upload__tip">JPG、PNG、WebP，单个不超过10MB，每类最多10张</div></template></el-upload><div class="attachment-list"><el-tag v-for="item in form.attachments.filter(item=>item.category===category.value)" :key="item.id" closable @close="removeSavedAttachment(item)">{{ item.originalName }}</el-tag></div></div></el-form-item></el-col></el-row>
          <el-form-item v-if="form.attachments.some(item=>item.category==='photo')" label="未分类照片（历史）"><div class="attachment-list"><el-tag v-for="item in form.attachments.filter(item=>item.category==='photo')" :key="item.id" closable @close="removeSavedAttachment(item)">{{item.originalName}}</el-tag></div></el-form-item>
          <el-form-item label="音频"><div><el-upload v-model:file-list="queuedAttachments.audio" :auto-upload="false" multiple accept=".mp3,.wav,.m4a,.aac,.ogg" :on-change="file=>queueAttachment('audio',file)" :on-remove="file=>unqueueAttachment('audio',file)"><el-button>选择音频</el-button><template #tip><div class="el-upload__tip">MP3、WAV、M4A、AAC、OGG，单个不超过100MB</div></template></el-upload><div class="attachment-list"><el-tag v-for="item in form.attachments.filter(item=>item.category==='audio')" :key="item.id" closable @close="removeSavedAttachment(item)">{{item.originalName}}</el-tag></div></div></el-form-item>
        </div></el-collapse-item>
        <el-collapse-item  name="editor-section-17" data-section-key="editor-section-17" title="其他资料"><div class="form-section"><h3>其他资料</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="简历路径"><el-input v-model="form.resumePath" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="首次联系"><el-date-picker v-model="form.firstContactDate" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="兼容联系方式"><el-input v-model="form.contactInfo" /></el-form-item></el-col></el-row><el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="2" /></el-form-item></div></el-collapse-item>
        </CollapsibleSections></el-tab-pane><el-tab-pane label="英文简历 / English" name="en"><LocalizedResumeEditor v-if="resumeTab==='en'" v-model="form.resumeProfile.versions.en" locale="en" prop-prefix="resumeProfile.versions.en" /></el-tab-pane><el-tab-pane label="外文简历" name="foreign"><el-form-item label="简历语言 / Resume language"><el-select v-model="foreignResumeLocale" filterable><el-option v-for="language in foreignResumeLanguages" :key="language.value" :label="language.label" :value="language.value" /></el-select></el-form-item><LocalizedResumeEditor v-if="resumeTab==='foreign'" :key="foreignResumeLocale" v-model="form.resumeProfile.versions[foreignResumeLocale]" :locale="foreignResumeLocale" :prop-prefix="`resumeProfile.versions.${foreignResumeLocale}`" /></el-tab-pane></el-tabs></AppForm>
      </div>
      <template #footer>
        <div class="talent-editor-footer">
          <div v-if="canContinueCreate" class="talent-batch-options">
            <el-checkbox v-model="keepBatchInfo" :disabled="saving">沿用本批公共信息</el-checkbox>
            <span class="section-hint">仅沿用：来源、所在微信、所在企微小群、所在企微大群</span>
          </div>
          <div class="talent-editor-actions">
            <el-button :disabled="saving" @click="editorVisible=false">取消</el-button>
            <el-button type="primary" :loading="saving && !continuingSave" :disabled="saving" @click="submit(false)">保存</el-button>
            <el-button v-if="canContinueCreate" :loading="saving && continuingSave" :disabled="saving" @click="submit(true)">保存并继续新增</el-button>
          </div>
        </div>
      </template>
    </DraggableFormDialog>
    <TalentQuickRegisterDialog ref="quickRegisterRef" :create="talentClient.create" @saved="fetchData" @open-existing="openTalentDetail" />
  </el-card>
</template>

<script setup>
import { talentTableColumns as tableColumns, talentDefaultColumns as defaultColumnKeys } from "@/utils/talentTableColumns"
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import { matchesSearch, searchTerms } from '@/utils/searchMatching'

import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox } from 'element-plus'
import { CaretBottom, Check } from '@element-plus/icons-vue'
import * as talentApi from '@/api/talents'
import { talentStatusOptions, talentStatusLabel, talentStatusType } from '@/utils/talentStatus'
import CollapsibleSections from '@/components/common/CollapsibleSections.vue'
import TalentResumeYear from './components/TalentResumeYear.vue'
import TalentEvaluationMeta from './components/TalentEvaluationMeta.vue'
import { evaluationSnapshot } from '@/utils/talentEvaluationAudit'
import TalentSettlementEditor from './components/TalentSettlementEditor.vue'
import TalentMediaSamples from './components/TalentMediaSamples.vue'
import { emptySettlement, settlementForm } from '@/utils/talentSettlement'
import { talentGradeOptions } from '@/utils/talentGrade'
import { interpretationRatingOptions, interpretationRatingHint, interpretationRatingLabel } from '@/utils/talentPerformance'
import { talentTimezoneOptions } from '@/utils/talentTimezones'
import { contactAvailabilityOptions, contactAvailabilityLabel } from '@/utils/talentContactAvailability'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {talentPhotoCategories,validTalentPhoto} from '@/utils/talentPhotoCategories'
import TalentQuickRegisterDialog from './components/TalentQuickRegisterDialog.vue'
import ResumeExperienceGrid from './components/ResumeExperienceGrid.vue'
import LocalizedResumeEditor from './components/LocalizedResumeEditor.vue'
import {foreignResumeLanguages} from '@/utils/talentResumeLocales'
import {catToolOptions,educationDegreeOptions,emptyResumeProfile,resumeProfileForm,educationFormRows,ensureResumeVersion} from '@/utils/talentResumeProfile'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import LanguageDirectionsEditor from '@/components/common/LanguageDirectionsEditor.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import CompanyWechatAccountSelect from '@/components/common/CompanyWechatAccountSelect.vue'
import { normalizeWechatAccounts, formatWechatAccounts, sameWechatAccounts } from '@/utils/companyWechatAccounts'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
import TalentResourceNav from '@/views/resource/components/TalentResourceNav.vue'
import TalentResourceTools from '@/views/resource/components/TalentResourceTools.vue'
import TalentDetailContent from '@/views/resource/components/TalentDetailContent.vue'
import TalentProjectSituationPopover from '@/views/resource/components/TalentProjectSituationPopover.vue'
import { getProjectLanguages, searchProjectLanguages } from '@/api/projectLanguages'
import { useTableColumns } from '@/composables/useTableColumns'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useFormDraft } from '@/composables/useFormDraft'
import { hasPermission, isSuperAdmin } from '@/utils/permission'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'
import { countTalentNames, getTalentDisplayName } from '@/utils/talentNames'
import { normalizeForeignLanguagePriorities } from '@/utils/talentLanguageSkills'
import { focusFormTarget } from '@/utils/formNavigation'

const route = useRoute()
function pathRecordSaved(id) { delete detailCache[id]; delete projectCache[id]; void fetchData() }
const router = useRouter()
function duplicateNameKey(value) { const normalized = String(value || '').replace(/\s+/g, ' ').trim(); return (normalized.replace(/(?:\s*[(（][^()（）]*[)）]\s*)+$/, '').trim() || normalized).toLowerCase() }
function openDuplicateReview(row) { router.push({ name: 'TalentDuplicateReview', query: { return: route.fullPath, ...(row ? { name: duplicateNameKey(row.fullName) } : {}) } }) }
const pageTitle = computed(() => route.meta.title || '人才总库')
const capabilityType = computed(() => route.meta.capabilityType || '')
const isRecruitmentPool = computed(() => route.meta.talentApiScope === 'recruitment')
const canViewContacts = computed(() => isSuperAdmin())
const quickRegisterRef=ref()
function openQuickCreate(){
  if(!canWrite.value)return
  if(!canViewContacts.value){ElMessage.warning('当前账号没有联系方式录入权限');return}
  if(isRecruitmentPool.value){ElMessage.info('请在人才总库使用快速登记');return}
  quickRegisterRef.value?.open()
}
const canWrite = computed(() => isRecruitmentPool.value
  ? hasPermission(['recruitment_talents:write'])
  : hasPermission(['talents:write','translators:write']))
const talentClient = computed(() => isRecruitmentPool.value ? {
  list: talentApi.getRecruitmentTalents,
  count: talentApi.getRecruitmentTalentCount,
  detail: talentApi.getRecruitmentTalent,
  projects: talentApi.getRecruitmentTalentProjects,
  create: talentApi.createRecruitmentTalent,
  update: talentApi.updateRecruitmentTalent,
  patchStatus: talentApi.patchRecruitmentTalentStatus,
  delete: talentApi.deleteRecruitmentTalent
} : {
  page: talentApi.getTalentPage,
  list: talentApi.getTalents,
  count: talentApi.getTalentCount,
  detail: talentApi.getTalent,
  projects: talentApi.getTalentProjects,
  create: talentApi.createTalent,
  update: talentApi.updateTalent,
  patchStatus: talentApi.patchTalentStatus,
  delete: talentApi.deleteTalent
})
const cooperationOptions = ['全职','兼职','自由职业','外包']
const capabilityLabels = {written_translation:'笔译',interpretation:'口译',annotation:'标注'}
const capabilityLabel = value => capabilityLabels[value] || value
const capabilityText = values => values?.length ? values.map(capabilityLabel).join('、') : '-'
const displayTalentName = (talent, fallback = '-') => getTalentDisplayName(talent, fallback)
const statusOptions = talentStatusOptions
const genderOptions = ['男','女','未知','不便透露'].map(value => ({value,label:value}))
const employmentOptions=[{value:'student',label:'在校学生'},{value:'employed',label:'在职'},{value:'freelance',label:'自由职业'},{value:'seeking',label:'待业/求职中'},{value:'retired',label:'已退休'},{value:'other',label:'其他'}]
const educationOptions=[{value:'high_school_or_below',label:'高中及以下'},{value:'secondary_vocational',label:'中专/职高'},{value:'associate',label:'专科'},{value:'bachelor',label:'本科'},{value:'master',label:'硕士研究生'},{value:'doctor',label:'博士研究生'},{value:'other',label:'其他'}]
const resumeWorkGroups=[{key:'annotation',label:'标注类经验'},{key:'interpretation',label:'口译经验'},{key:'translation',label:'笔译经验'},{key:'other',label:'其他经验'}]
const educationLevelOptions=educationDegreeOptions
const languageRoleOptions=[{value:'native',label:'母语'},{value:'foreign',label:'外语'},{value:'dialect_ethnic',label:'方言/民族语言'}]
const proficiencyOptions=[{value:'very_familiar',label:'非常熟悉'},{value:'familiar',label:'熟悉'},{value:'basic',label:'基础交流'},{value:'listening_mainly',label:'听懂为主'},{value:'listening_only',label:'仅能听懂'}]
const performanceLevelOptions=[{value:'high',label:'高'},{value:'medium',label:'中'},{value:'low',label:'低'}]
const willingnessOptions=[{value:'low',label:'低'},{value:'medium',label:'中'},{value:'high',label:'高'}]
const performanceScoreEditors=[
  {label:'音频标注表现',auditKey:'audio_annotation',scoreKey:'audioAnnotationScore',evaluationKey:'audioAnnotationEvaluation'},
  {label:'非音频标注表现',auditKey:'non_audio_annotation',scoreKey:'nonAudioAnnotationScore',evaluationKey:'nonAudioAnnotationEvaluation'},
  {label:'采集表现',auditKey:'collection',scoreKey:'collectionScore',evaluationKey:'collectionEvaluation'},
]
const performanceSortOptions=[
  {value:'overall_score',label:'标注总体评分'},
  {value:'audio_annotation_score',label:'音频标注评分'},
  {value:'non_audio_annotation_score',label:'非音频标注评分'},
  {value:'collection_score',label:'采集评分'},
]
const statusLabel = talentStatusLabel
const statusType = talentStatusType
const annotationWillingnessLabel = value => willingnessOptions.find(item => item.value === value)?.label || value || '-'
const annotationWillingnessType = value => ({high:'success',medium:'warning',low:'info'}[value] || 'info')
const display = value => value === null || value === undefined || value === '' ? '-' : Array.isArray(value) ? (value.join('、') || '-') : value
const ageOf = value => {if(!value)return '-';const birth=new Date(`${value}T00:00:00`);if(Number.isNaN(birth.getTime()))return '-';const now=new Date();let age=now.getFullYear()-birth.getFullYear();if(now.getMonth()<birth.getMonth()||(now.getMonth()===birth.getMonth()&&now.getDate()<birth.getDate()))age--;return age>=0?`${age}岁`:'-'}
const formatDateTime = value => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}年${pad(date.getMonth()+1)}月${pad(date.getDate())}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
const tableDisplay = (column, row) => {
  if (column.key === 'interpretationRating') return interpretationRatingLabel(row.interpretationRating)
  if (column.key === 'writtenTranslationScore') return row.writtenTranslationScore == null ? '-' : `${row.writtenTranslationScore}分`
  if (column.key === 'contactAvailability') return contactAvailabilityLabel(row.contactAvailability)
  if (column.key === 'employmentStatus') return employmentOptions.find(item => item.value === row.employmentStatus)?.label || display(row.employmentStatus)
  if (column.key === 'regionSummary') return row.residenceAddress || row.nativePlace || row.ancestralHome || '-'
  if (column.key === 'educationSummary') return row.educationSummary || '-'
  if (column.key === 'languageSummary') return row.languageSummary || '-'
  if (column.key === 'age') return row.currentAge == null ? '-' : `${row.currentAge}岁`
  if (column.key === 'yearsExperience') return row.yearsExperience === null || row.yearsExperience === undefined ? '-' : `${row.yearsExperience}年`
  if (column.type === 'datetime') return formatDateTime(row[column.key])
  if (column.key === 'wechatAccount') return formatWechatAccounts(row.wechatAccounts, row.wechatAccount) || '-'
  return display(row[column.key])
}
const overallPerformanceSummary = row => {
  const score = row.overallScore == null ? '' : `${row.overallScore}分`
  const evaluation = String(row.overallRating || '').trim()
  const summary = evaluation.length > 24 ? `${evaluation.slice(0,24)}…` : evaluation
  return [score, summary].filter(Boolean).join(' · ') || '-'
}
const summarySectionMap={regionSummary:'region',educationSummary:'education',languageSummary:'language'}
const summarySection=key=>summarySectionMap[key]||''
const summaryHover=(key,row)=>({regionSummary:[row.ancestralHome,row.nativePlace,row.residenceAddress].filter(Boolean).join(' · '),educationSummary:row.highestEducation,languageSummary:row.languageSummary}[key]||'点击查看详情')

const ProfileDescription = defineComponent({props:{profile:Object,type:String},setup(props){const items=computed(()=>{const p=props.profile||{};if(props.type==='written')return [['语种方向',p.languages],['翻译方向',p.direction],['领域技能',p.domainSkills],['质量评分',p.qualityScore],['默认优先级',p.defaultPriority],['日产接单数',p.dailyAcceptCount],['时速',p.hourlySpeed],['日产能',p.dailyWordCapacity],['可用时段',p.availableTimeSlot],['排班备注',p.scheduleRemarks],['云编辑',p.canCloudEdit===true?'支持':p.canCloudEdit===false?'不支持':'-'],['审校',p.canRevision===true?'支持':p.canRevision===false?'不支持':'-']];if(props.type==='interpretation')return [['语种方向',p.languages],['翻译方向',p.direction],['口译等级',p.interpretationLevel],['口译方式',(p.interpretationModes||[]).map(v=>v==='simultaneous'?'同传':'交传').join('、')],['领域技能',p.domainSkills],['质量评分',p.qualityScore],['评价概述',p.evaluationSummary]];if(props.type==='annotation')return [['任务类型',p.taskTypes],['数据模态',p.dataModalities],['工具经验',p.tools],['领域技能',p.domainSkills],['质量评分',p.qualityScore],['日产能',p.dailyCapacity],['备注',p.remarks]];return [['行业',p.industries],['职能',p.functions],['岗位',p.jobTitles],['工作年限',p.yearsExperience],['期望地点',p.preferredLocations],['期望薪资',p.expectedSalary],['职业概述',p.summary]]});return()=>h(ElDescriptions,{column:2,border:true,size:'small'},()=>items.value.map(([label,value])=>h(ElDescriptionsItem,{label},()=>display(value))))}})


const legacyDefaultColumnKeys=[
  ['fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','overallRating','projectSituation','status','duplicateReviewRequired'],
  ['fullName','gender','nationality','employmentStatus','regionSummary','educationSummary','languageSummary','capabilityTypes','overallRating','projectSituation','status','duplicateReviewRequired'],
  ['fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','status','duplicateReviewRequired'],
  ['fullName','basicSummary','regionSummary','educationSummary','languageSummary','capabilityTypes','overallRating','status','duplicateReviewRequired'],
  ['resourceCode','fullName','capabilityTypes','languageDirections','industries','status','cooperationType','primaryPhone','primaryEmail','duplicateReviewRequired'],
  ['resourceCode','fullName','capabilityTypes','languageDirections','industries','yearsExperience','status','cooperationType','primaryPhone','primaryEmail','duplicateReviewRequired']
]

const contactColumnKeys=new Set(['primaryPhone','primaryEmail','identityNumber'])
const {selectedKeys:visibleColumnKeys,isVisible,reset:resetColumns}=useTableColumns('resource-talents-v4',tableColumns,defaultColumnKeys,{legacyDefaultKeys:legacyDefaultColumnKeys,keyAliases:{regionSummary:['ancestralHome','nativePlace','residenceAddress']}})
const availableToCurrentPool=item=>!isRecruitmentPool.value||(!item.performance&&!item.talentManaged)
const settingsColumns=computed(()=>tableColumns.filter(item=>item.key!=='resourceCode'&&availableToCurrentPool(item)))
const settingsVisibleColumnKeys=computed({
  get:()=>visibleColumnKeys.value.filter(key=>settingsColumns.value.some(item=>item.key===key)),
  set:value=>{const hidden=visibleColumnKeys.value.filter(key=>!settingsColumns.value.some(item=>item.key===key));visibleColumnKeys.value=[...value,...hidden]},
})
const visibleColumns=computed(()=>tableColumns.filter(item=>(item.key==='resourceCode'||isVisible(item.key))&&availableToCurrentPool(item)))
const rows=ref([]);const loading=ref(false);const detailLoadingId=ref(null);const detailCache=reactive({});const projectCache=reactive({});const pagination=reactive({page:1,limit:10,total:0});const advancedVisible=ref(false);const statusSavingIds=ref(new Set())
const talentTableRef=ref(null)
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:talentTableRef,pagination,deleteRow:(row)=>talentClient.value.delete(row.id),getLabel:(row)=>row.fullName||row.resourceCode||row.id,reload:()=>fetchData(),onDeleted:(row)=>{delete detailCache[row.id];delete projectCache[row.id]},entityName:'人才档案'})
const search=reactive({keyword:'',status:'',cooperationType:'',industryKeyword:'',reviewRequired:null})
const talentFilterFields=[
  {key:'resourceCode',label:'人才编号',type:'text'},{key:'fullName',label:'姓名',type:'text'},
  {key:'regionSummary',label:'区域信息',type:'text',placeholder:'筛选籍贯、主要成长地或目前所在地'},
  {key:'educationSummary',label:'学历信息',type:'text',placeholder:'筛选最高学历、院校或专业'},
  {key:'languageSummary',label:'语言与证书',type:'text',placeholder:'筛选语言、证书或颁发机构'},
  {key:'educationLevel',label:'经历学历层次',type:'select',options:educationLevelOptions},
  {key:'educationInstitution',label:'院校',type:'text'},
  {key:'educationMajor',label:'专业',type:'text'},
  {key:'educationInstitutionCategory',label:'院校分类',type:'text'},
  {key:'educationMajorCategory',label:'专业分类',type:'text'},
  {key:'educationGraduationYear',label:'毕业年份',type:'number-range',wide:true,min:1900,max:2200,precision:0},
  {key:'educationMinorMajor',label:'辅修专业',type:'text'},
  {key:'educationDegreeName',label:'学位名称',type:'text'},
  {key:'languageRole',label:'语言角色',type:'select',options:languageRoleOptions},
  {key:'languageProficiency',label:'熟悉程度',type:'select',options:proficiencyOptions},
  {key:'certificateType',label:'证书类型',type:'select',options:[{value:'language',label:'外语类证书'},{value:'other',label:'其他类证书'}]},
  {key:'certificateName',label:'证书名称',type:'text'},
  {key:'certificateLanguage',label:'证书语言',type:'text'},
  {key:'certificateIssuer',label:'颁发机构',type:'text'},
  {key:'capabilityTypes',label:'专业能力',type:'select',options:Object.entries(capabilityLabels).map(([value,label])=>({value,label}))},
  {key:'annotationWillingness',label:'标注意愿',type:'select',options:willingnessOptions,talentManaged:true},
  {key:'languageDirections',label:'语种方向',type:'text'},{key:'annotationLanguageDirections',label:'标注语言方向',type:'text'},
  {key:'industries',label:'行业',type:'text'},{key:'jobTitles',label:'岗位',type:'text'},
  {key:'yearsExperience',label:'工作年限',type:'number-range',wide:true,min:0},
  {key:'status',label:'状态',type:'select',options:statusOptions},{key:'cooperationType',label:'合作形式',type:'select',options:cooperationOptions},
  {key:'primaryPhone',label:'主要电话',type:'text'},{key:'primaryEmail',label:'主要邮箱',type:'text'},
  {key:'gender',label:'性别',type:'select',options:genderOptions},{key:'age',label:'年龄',type:'number-range',wide:true,min:0,max:120},
  {key:'identityNumber',label:'身份证号码',type:'text'},{key:'eyesight',label:'视力',type:'text'},
  {key:'employmentStatus',label:'职业状态',type:'select',options:employmentOptions},{key:'highestEducation',label:'最高学历',type:'select',options:educationOptions},
  {key:'registrationSource',label:'来源',type:'text'},
  {key:'resumePathRegistered',label:'路径登记',type:'boolean',options:[{value:true,label:'有'},{value:false,label:'无'}],placeholder:'全部'},
  {key:'wechatAccount',label:'所在微信',type:'text'},
  {key:'wechatGroups',label:'所在企微小群',type:'text'},
  {key:'wecomLargeGroups',label:'所在企微大群',type:'text'},
  {key:'contactAvailability',label:'可联系时段',type:'select',options:contactAvailabilityOptions},
  {key:'residenceTimezone',label:'时区',type:'select',options:talentTimezoneOptions},
  {key:'ancestralHome',label:'籍贯',type:'text'},
  {key:'nativePlace',label:'主要成长地',type:'text'},{key:'residenceAddress',label:'目前所在地',type:'text'},
  {key:'dialects',label:'掌握方言',type:'text'},{key:'dialectRegions',label:'方言区域',type:'text'},
  {key:'nationality',label:'国籍',type:'text'},
  {key:'overallRating',label:'标注总体评价',type:'text',performance:true},
  {key:'interpretationRating',label:'口译员评级',type:'number-range',wide:true,min:1,max:6,precision:0,performance:true},
  {key:'interpretationRatingNote',label:'口译说明',type:'text',performance:true},
  {key:'interpretationDomains',label:'口译领域',type:'text',performance:true},
  {key:'writtenTranslationScore',label:'笔译总体评价',type:'number-range',wide:true,min:1,max:10,precision:0,performance:true},
  {key:'writtenTranslationEvaluation',label:'笔译具体评价',type:'text',performance:true},
  {key:'projectSituation',label:'项目情况',type:'text',placeholder:'筛选项目名称或订单号'},
  {key:'overallScore',label:'标注总体评分',type:'number-range',wide:true,min:1,max:10,precision:0,performance:true},
  {key:'audioAnnotationScore',label:'音频标注评分',type:'number-range',wide:true,min:1,max:10,precision:0,performance:true},
  {key:'nonAudioAnnotationScore',label:'非音频标注评分',type:'number-range',wide:true,min:1,max:10,precision:0,performance:true},
  {key:'collectionScore',label:'采集评分',type:'number-range',wide:true,min:1,max:10,precision:0,performance:true},
  {key:'languageSkills',label:'语言能力',type:'text'},{key:'certificateReceived',label:'证书已收到',type:'boolean'},
  {key:'firstContactDate',label:'首次联系时间',type:'date-range',wide:true},{key:'updatedAt',label:'最近更新',type:'date-range',wide:true},
  {key:'operatorName',label:'操作人',type:'text'},{key:'operatedAt',label:'操作时间',type:'date-range',wide:true},
  {key:'duplicateReviewRequired',label:'核重状态',type:'boolean'},
].filter(item=>canViewContacts.value||!contactColumnKeys.has(item.key))
Object.assign(search,createFilterModel(talentFilterFields),{keyword:''})
const talentAdvancedFilterFields=computed(()=>talentFilterFields.filter((item)=>item.key!=='status'&&availableToCurrentPool(item)))
const activeTalentFilterFields=computed(()=>talentFilterFields.filter(availableToCurrentPool))
const advancedCount=computed(()=>countActiveFilters(search,talentAdvancedFilterFields.value))
const groupedFilterKeys = {
  regionSummary: ['regionSummary','ancestralHome','nativePlace','residenceAddress'],
  educationSummary: ['educationSummary','highestEducation','educationLevel','educationInstitution','educationMajor','educationInstitutionCategory','educationMajorCategory','educationGraduationYear','educationMinorMajor','educationDegreeName'],
  languageSummary: ['languageSummary','languageSkills','languageRole','languageProficiency','dialects','certificateType','certificateName','certificateLanguage','certificateIssuer','certificateReceived'],
}
const groupedHeaderFilters = Object.fromEntries(Object.entries(groupedFilterKeys).map(([key, keys]) => [key, {
  key, label: talentFilterFields.find(field => field.key === key).label, type: 'group', headerWidth: 480,
  fields: keys.map(fieldKey => {
    const field = talentFilterFields.find(item => item.key === fieldKey)
    return { ...field, groupLabel: fieldKey === key ? '综合关键词' : fieldKey === 'residenceAddress' ? '目前所在地' : field.label }
  }),
}]))
const headerFilterDefinition=(key)=>groupedHeaderFilters[key]||talentFilterFields.find((item)=>item.key===key&&availableToCurrentPool(item))||null
const performanceSortField=ref('')
const performanceSortDirection=ref('desc')
let timer=null;let controller=null;let sequence=0
const params=()=>({keyword:search.keyword.trim()||undefined,capability_type:capabilityType.value||undefined,field_filters:serializeFieldFilters(search,activeTalentFilterFields.value),sort:!isRecruitmentPool.value&&performanceSortField.value?`${performanceSortField.value}_${performanceSortDirection.value}`:undefined})
async function fetchData(){controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;try{const filters=params();const client=talentClient.value;const listParams={...filters,skip:(pagination.page-1)*pagination.limit,limit:pagination.limit};if(client.page){const page=await client.page(listParams,{signal:controller.signal});if(current!==sequence)return;rows.value=page?.items||[];pagination.total=page?.total||0}else{const [list,count]=await Promise.all([client.list(listParams,{signal:controller.signal}),client.count(filters,{signal:controller.signal})]);if(current!==sequence)return;rows.value=list||[];pagination.total=count?.total||0}}catch(error){if(error.code!=='ERR_CANCELED'&&current===sequence)ElMessage.error(error.detail||'网络异常，人才列表未刷新，请检查网络后重试')}finally{if(current===sequence)loading.value=false}}
function searchNow(){exitDeleteMode();clearTimeout(timer);pagination.page=1;fetchData()}function handleTextInput(value){clearTimeout(timer);if(!value?.trim())return searchNow();timer=setTimeout(searchNow,400)}function updateConfiguredFilter(key,value){search[key]=value}function handleConfiguredTextInput(value){handleTextInput(value)}function handlePerformanceSortChange(){if(!performanceSortField.value)performanceSortDirection.value='desc';searchNow()}function resetSearch(){search.keyword='';performanceSortField.value='';performanceSortDirection.value='desc';resetFilterModel(search,talentFilterFields);searchNow()}function clearAdvanced(){resetFilterModel(search,talentAdvancedFilterFields.value);searchNow()}function handleSizeChange(){pagination.page=1;fetchData()}
async function loadDetail(id,force=false){if(!force&&detailCache[id])return detailCache[id];detailLoadingId.value=id;try{detailCache[id]=await talentClient.value.detail(id);return detailCache[id]}catch(error){ElMessage.error(error.detail||'加载人才详情失败')}finally{detailLoadingId.value=null}}
const detailFor=row=>detailCache[row.id]||row
const detailVisible=ref(false),selectedDetail=ref({}),projectsLoading=ref(false),projectsError=ref('')
async function openTalentDetail(row){selectedDetail.value=row;detailVisible.value=true;await loadFullDetail(row)}
async function loadFullDetail(row){projectsLoading.value=true;projectsError.value='';const id=row.id;try{const [,projects]=await Promise.all([loadDetail(id,true),talentClient.value.projects(id)]);projectCache[id]=projects}catch(error){if(selectedDetail.value.id===id)projectsError.value=error.detail||'项目情况加载失败，请重试'}finally{if(selectedDetail.value.id===id)projectsLoading.value=false}}

function setStatusSaving(id,saving){const next=new Set(statusSavingIds.value);if(saving)next.add(id);else next.delete(id);statusSavingIds.value=next}
async function changeStatus(row,value){if(!value||value===row.status)return;setStatusSaving(row.id,true);try{const updated=await talentClient.value.patchStatus(row.id,value);Object.assign(row,updated);if(detailCache[row.id])detailCache[row.id]={...detailCache[row.id],...updated};ElMessage.success('人才状态已更新');if(search.status?.length&&!search.status.includes(updated.status))await fetchData()}catch(error){ElMessage.error(getLocalizedErrorMessage(error,'人才状态更新失败'))}finally{setStatusSaving(row.id,false)}}

const birthDateParts=value=>{const match=String(value||'').match(/^(\d{4})-(\d{2})-(\d{2})/);return match?{year:Number(match[1]),month:Number(match[2]),day:Number(match[3])}:null}
const calculateAge=value=>{const parts=birthDateParts(value);if(!parts)return null;const now=new Date();let age=now.getFullYear()-parts.year;if(now.getMonth()+1<parts.month||(now.getMonth()+1===parts.month&&now.getDate()<parts.day))age--;return age>=0?age:null}
const formatDate=(year,month,day)=>`${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`
const birthDateFromAge=(age,currentBirthDate)=>{
  const numericAge=Number(age)
  if(!Number.isInteger(numericAge)||numericAge<0||numericAge>120)return null
  const now=new Date(),existing=birthDateParts(currentBirthDate)
  const month=existing?.month||now.getMonth()+1
  const requestedDay=existing?.day||now.getDate()
  const birthdayPassed=month<now.getMonth()+1||(month===now.getMonth()+1&&requestedDay<=now.getDate())
  const year=now.getFullYear()-numericAge-(birthdayPassed?0:1)
  const lastDay=new Date(year,month,0).getDate()
  return formatDate(year,month,Math.min(requestedDay,lastDay))
}
const handleBirthDateChange=value=>{form.age=calculateAge(value)}
const handleAgeChange=value=>{form.birthDate=value===null||value===undefined?null:birthDateFromAge(value,form.birthDate)}
const emptyForm=()=>({
  id:null,resourceCode:'',registrationSource:'',wechatAccount:'',wechatAccounts:[],wechatAccountsOriginal:[],wechatAccountsRevision:1,wechatGroups:'',fullName:'',nameGroup:'',chineseName:'',englishName:'',nickname:'',otherNames:[],cooperationType:'',
  contactInfo:'',primaryPhone:'',secondaryPhone:'',primaryEmail:'',secondaryEmail:'',otherContact:'',wechat:'',whatsapp:'',skype:'',line:'',contactAvailability:null,wecomLargeGroups:'',wecomSmallGroupStatus:null,wecomLargeGroupStatus:null,residenceTimezone:null,
  resumePath:'',gender:'',birthDate:null,birthYearMonth:null,reportedAge:null,ancestralHome:'',nativePlace:'',residenceAddress:'',dialects:[],dialectRegions:[],height:'',appearance:'',
  nationality:'',ethnicity:'',employmentStatus:null,employmentDetail:'',studentStage:'',enrollmentYear:null,programDurationYears:null,studentGradeOverride:'',highestEducation:null,
  annotationExperience:'',interpretationExperience:'',translationExperience:'',otherExperience:'',annotationWillingness:null,educationExperiences:[],languageSkills:[],certificates:[],attachments:[],
  identityNumber:'',eyesight:'',settlement:emptySettlement(),resumeProfile:emptyResumeProfile(),evaluationMeta:{},evaluationOriginal:evaluationSnapshot({}),talentGrade:'pending',overallScore:null,overallRating:'',cooperationLevel:null,cooperationNote:'',punctualityLevel:null,punctualityNote:'',
  audioAnnotationScore:null,audioAnnotationEvaluation:'',nonAudioAnnotationScore:null,nonAudioAnnotationEvaluation:'',collectionScore:null,collectionEvaluation:'',
  interpretationRating:null,interpretationRatingNote:'',interpretationDomains:'',writtenTranslationScore:null,writtenTranslationEvaluation:'',
  firstContactDate:null,remarks:'',status:'standby',capabilityTypes:capabilityType.value?[capabilityType.value]:[],
  writtenProfile:{languages:'',direction:'',domainSkills:[],qualityScore:'',defaultPriority:0,dailyAcceptCount:null,hourlySpeed:null,dailyWordCapacity:null,canCloudEdit:null,canRevision:null,availableTimeSlot:'',scheduleRemarks:''},
  interpretationProfile:{languages:'',direction:'',interpretationLevel:null,interpretationModes:[],domainSkills:[],qualityScore:'',evaluationSummary:''},
  annotationProfile:{taskTypes:[],dataModalities:[],tools:[],domainSkills:[],qualityScore:'',dailyCapacity:null,remarks:''},annotationLanguageSkills:[],
  careerProfile:{industries:[],functions:[],jobTitles:[],yearsExperience:null,preferredLocations:[],expectedSalary:'',summary:''},
})
const form=reactive(emptyForm())
const otherNamesText=computed({get:()=>form.otherNames.join('\n'),set:value=>{form.otherNames=String(value||'').split(/\r?\n/)}})
const resumeTab=ref('zh'),foreignResumeLocale=ref('ar')
watch([resumeTab,foreignResumeLocale],()=>{if(resumeTab.value!=='zh')ensureResumeVersion(form.resumeProfile,resumeTab.value==='en'?'en':foreignResumeLocale.value)},{flush:'sync'});const formRef=ref(null);const editorVisible=ref(false);const saving=ref(false);const editorTitle=ref('新增人才');const nameFieldsExpanded=ref(true)
const keepBatchInfo = ref(false)
const continuingSave = ref(false)
// 新增中途附件失败时 form.id 已存在，仍保留本次新增流程的操作入口。
const creatingTalent = ref(false)
const canContinueCreate = computed(() => route.name === 'Talents' && creatingTalent.value)
const preferredFormName=computed(()=>getTalentDisplayName(form,''));const filledNameCount=computed(()=>countTalentNames(form))
const validateNameGroup=(_rule,_value,callback)=>filledNameCount.value?callback():callback(new Error('中文姓名、外文姓名、昵称或其他名字至少填写一项'))
// 导入的待核实档案可能尚未确认专业能力，编辑时允许保留空值。
const rules=computed(()=>({interpretationRating:[{type:'integer',min:1,max:6,message:'请选择一星至六星',trigger:'change'}],writtenTranslationScore:[{type:'integer',min:1,max:10,message:'笔译总体评价须为1至10分',trigger:'change'}],wechatAccounts:[{type:'array',max:100,message:'所在微信最多选择100项',trigger:'change'}],nameGroup:[{validator:validateNameGroup,trigger:['blur','change']}],capabilityTypes:[{type:'array',required:!form.id,min:form.id?0:1,message:'请至少选择一项专业能力',trigger:'change'}]}));const hasCapability=type=>form.capabilityTypes.includes(type)
const validateNameGroupField=()=>nextTick(()=>formRef.value?.validateField('nameGroup').catch(()=>{}))
const languages=ref([])
const languageKeyword=ref('')
const languageSearchResults=ref([])
const queuedAttachments=reactive({photo:[],id_photo:[],life_photo:[],audio:[],annotation_sample:[],interpretation_sample:[]})
const recordKey=()=>`${Date.now()}-${Math.random().toString(36).slice(2)}`
const languageDisplay=item=>[item.nameZh||item.label,item.nameEn,item.code].filter(Boolean).join(' / ')
const normalizeLanguageSearch=value=>String(value||'').toLocaleLowerCase().replace(/[\s_./()（）·-]+/g,'')
const filteredLanguages=computed(()=>{const keyword=searchTerms(languageKeyword.value).map(normalizeLanguageSearch).join(' ');if(!keyword)return languages.value;if(languageSearchResults.value.length)return languageSearchResults.value;return languages.value.filter(item=>matchesSearch(normalizeLanguageSearch([item.label,item.nameZh,item.nameEn,item.code,...(item.aliases||[]),...(item.shortcuts||[])].join('|')),keyword))})
let languageSearchTimer=null
const filterTalentLanguages=value=>{languageKeyword.value=value||'';languageSearchResults.value=[];clearTimeout(languageSearchTimer);if(String(value||'').trim().length<2)return;languageSearchTimer=setTimeout(async()=>{try{languageSearchResults.value=await searchProjectLanguages(value,50)}catch{languageSearchResults.value=[]}},250)}
const calculatedAge=computed(()=>{const match=String(form.birthYearMonth||'').match(/^(\d{4})-(\d{2})$/);if(!match)return '';const now=new Date();return now.getFullYear()-Number(match[1])-(now.getMonth()+1<Number(match[2])?1:0)})
const studentGrade=computed(()=>{if(form.employmentStatus!=='student'||!form.enrollmentYear)return '';if(form.studentGradeOverride)return form.studentGradeOverride;const now=new Date();const academicYear=now.getMonth()+1>=9?now.getFullYear():now.getFullYear()-1;const grade=academicYear-Number(form.enrollmentYear)+1;if(grade<1)return '未入学';if(form.programDurationYears&&grade>form.programDurationYears)return '已超过预计学制';return `大${grade}`})
const addLanguage=()=>form.languageSkills.push({id:null,_key:recordKey(),languageId:'',role:'dialect_ethnic',priority:0,proficiency:null,remarks:'',sortOrder:form.languageSkills.length})
const removeLanguage=index=>form.languageSkills.splice(index,1)
const normalizeLanguagePriorities=()=>normalizeForeignLanguagePriorities(form.languageSkills).forEach((item,index)=>{form.languageSkills[index].priority=item.priority})
const addCertificate=()=>form.certificates.push({id:null,_key:recordKey(),certificateType:'language',name:'',languageId:null,issuer:'',certificateNo:'',issuedOn:null,materialReceived:false,remarks:'',sortOrder:form.certificates.length})
const removeCertificate=index=>form.certificates.splice(index,1)
const queueAttachment=(category,file)=>{
  if(!file?.raw)return
  if(talentPhotoCategories.some(item=>item.value===category)){
    const selected=queuedAttachments[category]
    const count=form.attachments.filter(item=>item.category===category).length+selected.length+(selected.some(item=>item.uid===file.uid)?0:1)
    if(!validTalentPhoto(file.raw)||count>10){unqueueAttachment(category,file);ElMessage.warning(count>10?'每类照片最多10张':'请选择不超过10MB的 JPG、PNG 或 WebP 照片');return}
  }
  if(!queuedAttachments[category].some(item=>item.uid===file.uid))queuedAttachments[category].push(file)
}
const unqueueAttachment=(category,file)=>{queuedAttachments[category]=queuedAttachments[category].filter(item=>item.uid!==file.uid)}
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'talent',form,createDefault:emptyForm,formRef})
const editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField:locateDialogFieldBase,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const locateDialogField=async item=>{if(['中文姓名','外文姓名','昵称','其他名字'].includes(item?.searchLabel))nameFieldsExpanded.value=true;await nextTick();return locateDialogFieldBase(item)}
const blankToNull=value=>typeof value==='string'&&!value.trim()?null:value
const cleanWrittenProfile=p=>p?{...p,languages:blankToNull(p.languages),direction:blankToNull(p.direction),qualityScore:blankToNull(p.qualityScore),availableTimeSlot:blankToNull(p.availableTimeSlot),scheduleRemarks:blankToNull(p.scheduleRemarks)}:null
const cleanInterpretationProfile=p=>p?{...p,languages:blankToNull(p.languages),direction:blankToNull(p.direction),interpretationLevel:blankToNull(p.interpretationLevel),qualityScore:blankToNull(p.qualityScore),evaluationSummary:blankToNull(p.evaluationSummary)}:null
const cleanAnnotationProfile=p=>p?{...p,qualityScore:blankToNull(p.qualityScore),remarks:blankToNull(p.remarks)}:null
const cleanCareerProfile=p=>p?{...p,expectedSalary:blankToNull(p.expectedSalary),summary:blankToNull(p.summary)}:null
const contactPayloadKeys=['identityNumber','contactInfo','primaryPhone','secondaryPhone','primaryEmail','secondaryEmail','otherContact','wechat','whatsapp','skype','line']
const talentManagedPayloadKeys=['interpretationDomains','interpretationRating','interpretationRatingNote','writtenTranslationScore','writtenTranslationEvaluation','annotationWillingness','talentGrade','overallScore','overallRating','cooperationLevel','cooperationNote','punctualityLevel','punctualityNote','audioAnnotationScore','audioAnnotationEvaluation','nonAudioAnnotationScore','nonAudioAnnotationEvaluation','collectionScore','collectionEvaluation']
function resetForm() {
  resumeTab.value='zh'
  Object.assign(form, emptyForm())
  nameFieldsExpanded.value = true
  queuedAttachments.photo = []
  queuedAttachments.id_photo = []
  queuedAttachments.life_photo = []
  queuedAttachments.audio = []
  queuedAttachments.annotation_sample = []
  queuedAttachments.interpretation_sample = []

  clearTimeout(languageSearchTimer)
  languageKeyword.value = ''
  languageSearchResults.value = []
  formRef.value?.clearValidate()
  clearFieldSearch()
}
function initializeCreateForm(batchInfo = {}) {
  resetForm()
  Object.assign(form, batchInfo)
  const chinese = languages.value.find(item => item.code === 'zh-CN')
  if (chinese) form.languageSkills.push({ id: null, _key: recordKey(), languageId: chinese.id, role: 'native', priority: 1, proficiency: 'very_familiar', remarks: '', sortOrder: 0 })
  creatingTalent.value = true
  editorTitle.value = '新增人才'
}
const editorSectionsKey=ref(0)
async function onEditorOpened() {
  resumeTab.value='zh'
  editorSectionsKey.value++
  await nextTick()
  const scrollBody = editorBodyRef.value?.closest('.el-dialog__body')
  if (scrollBody) scrollBody.scrollTop = 0
}
function beforeEditorClose(done) { if (!saving.value) done() }
function onEditorClosed() {
  pauseDraft()
  resetForm()
  keepBatchInfo.value = false
  creatingTalent.value = false
}
async function openCreate() {
  keepBatchInfo.value = false
  initializeCreateForm()
  editorVisible.value = true
  await beginDraft('create')
}
function fromDetail(d){if(d.contactRestricted)d={...d,...Object.fromEntries(contactPayloadKeys.map(key=>[key,'']))};const base=emptyForm();const inferredChinese=!d.chineseName&&!d.englishName&&/[\u3400-\u9fff]/.test(d.fullName||'')?d.fullName:'';const inferredEnglish=!d.chineseName&&!d.englishName&&!inferredChinese?d.fullName:'';return {...base,...d,settlement:settlementForm(d.settlement),resumeProfile:resumeProfileForm(d.resumeProfile,d),evaluationOriginal:evaluationSnapshot(d),id:d.id,wechatAccounts:normalizeWechatAccounts(d.wechatAccounts,d.wechatAccount),wechatAccountsOriginal:normalizeWechatAccounts(d.wechatAccounts,d.wechatAccount),wechatAccountsRevision:d.wechatAccountsRevision||1,chineseName:d.chineseName||inferredChinese,englishName:d.englishName||inferredEnglish,birthYearMonth:d.birthYearMonth||String(d.birthDate||'').slice(0,7)||null,capabilityTypes:d.capabilityTypes||[],educationExperiences:educationFormRows(d.educationExperiences||[],d.resumeProfile?.educationPeriods),languageSkills:normalizeForeignLanguagePriorities(d.languageSkills||[]).map(item=>({...item,expectedAccent:item.accent||'',_key:recordKey()})),certificates:(d.certificates||[]).map(item=>({...item,_key:recordKey()})),attachments:d.attachments||[],writtenProfile:{...base.writtenProfile,...(d.writtenProfile||{})},interpretationProfile:{...base.interpretationProfile,...(d.interpretationProfile||{})},annotationProfile:{...base.annotationProfile,...(d.annotationProfile||{})},annotationLanguageSkills:(d.annotationLanguageSkills||[]).map(item=>({sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.targetLanguageId||null})),careerProfile:{...base.careerProfile,...(d.careerProfile||{})}}}
async function openEdit(row){const detail=await loadDetail(row.id,true);if(!detail)return;if(detail.archivedIntoId){ElMessage.info('此档案已归档，请打开保留档案');return}pauseDraft();resetForm();creatingTalent.value=false;keepBatchInfo.value=false;Object.assign(form,fromDetail(detail));nameFieldsExpanded.value=true;editorTitle.value=`编辑人才：${displayTalentName(detail,'人才')}`;editorVisible.value=true;await beginDraft(`edit:${detail.id}`)}
const cleanChild=item=>Object.fromEntries(Object.entries(item).filter(([key])=>key!=='_key'&&key!=='languageLabel'))
const payload=(allowDuplicate=false)=>{
  const result={
    resourceCode:form.resourceCode||null,
    resumeProfile:JSON.parse(JSON.stringify(form.resumeProfile)),
    identityNumber:form.identityNumber?.trim()||null,eyesight:form.eyesight?.trim()||null,
    registrationSource:form.registrationSource||null,
    wechatGroups:form.wechatGroups?.trim()||null,
    wecomLargeGroups:form.wecomLargeGroups?.trim()||null,
    contactAvailability:form.contactAvailability||null,
    residenceTimezone:form.residenceTimezone||null,
    reportedAge:form.reportedAge??null,
    fullName:[form.chineseName,form.englishName,form.nickname,...(form.otherNames||[]),form.fullName].find(value=>String(value||'').trim())||'',
    chineseName:form.chineseName||null,englishName:form.englishName||null,nickname:form.nickname||null,otherNames:form.otherNames||[],cooperationType:form.cooperationType||null,
    contactInfo:form.contactInfo||null,primaryPhone:form.primaryPhone||null,secondaryPhone:form.secondaryPhone||null,primaryEmail:form.primaryEmail||null,secondaryEmail:form.secondaryEmail||null,
    otherContact:form.otherContact||null,wechat:form.wechat||null,whatsapp:form.whatsapp||null,skype:form.skype||null,line:form.line||null,resumePath:form.resumePath||null,
    gender:form.gender||null,birthDate:blankToNull(form.birthDate),birthYearMonth:blankToNull(form.birthYearMonth),ancestralHome:form.ancestralHome||null,nativePlace:form.nativePlace||null,residenceAddress:form.residenceAddress||null,
    dialects:form.dialects||[],dialectRegions:form.dialectRegions||[],height:form.height||null,appearance:form.appearance||null,nationality:form.nationality||null,ethnicity:form.ethnicity||null,
    employmentStatus:form.employmentStatus||null,employmentDetail:form.employmentDetail||null,studentStage:form.studentStage||null,enrollmentYear:form.enrollmentYear,
    programDurationYears:form.programDurationYears,studentGradeOverride:form.studentGradeOverride||null,highestEducation:form.highestEducation||null,
    annotationExperience:form.annotationExperience||null,interpretationExperience:form.interpretationExperience||null,translationExperience:form.translationExperience||null,otherExperience:form.otherExperience||null,annotationWillingness:form.annotationWillingness||null,
    educationExperiences:form.educationExperiences.map((item,index)=>({...cleanChild(item),sortOrder:index})),
    languageSkills:normalizeForeignLanguagePriorities(form.languageSkills.filter(item=>item.languageId)).map((item,index)=>({...cleanChild(item),sortOrder:index})),
    certificates:form.certificates.filter(item=>item.name?.trim()).map((item,index)=>({...cleanChild(item),sortOrder:index})),
    talentGrade:form.talentGrade||'pending',overallScore:form.overallScore,overallRating:form.overallRating||null,cooperationLevel:form.cooperationLevel||null,cooperationNote:form.cooperationNote||null,
    punctualityLevel:form.punctualityLevel||null,punctualityNote:form.punctualityNote||null,audioAnnotationScore:form.audioAnnotationScore,
    audioAnnotationEvaluation:form.audioAnnotationEvaluation||null,nonAudioAnnotationScore:form.nonAudioAnnotationScore,
    nonAudioAnnotationEvaluation:form.nonAudioAnnotationEvaluation||null,collectionScore:form.collectionScore,collectionEvaluation:form.collectionEvaluation||null,
    interpretationRating:form.interpretationRating,interpretationRatingNote:form.interpretationRatingNote||null,interpretationDomains:form.interpretationDomains||null,writtenTranslationScore:form.writtenTranslationScore,writtenTranslationEvaluation:form.writtenTranslationEvaluation||null,
    firstContactDate:blankToNull(form.firstContactDate),remarks:form.remarks||null,status:form.status,allowDuplicate,
    capabilities:form.capabilityTypes.map(capabilityType=>({capabilityType,status:'active'})),
    writtenProfile:hasCapability('written_translation')?cleanWrittenProfile(form.writtenProfile):null,
    interpretationProfile:hasCapability('interpretation')?cleanInterpretationProfile(form.interpretationProfile):null,
    annotationProfile:hasCapability('annotation')?cleanAnnotationProfile(form.annotationProfile):null,
    annotationLanguageSkills:hasCapability('annotation')?form.annotationLanguageSkills.map(item=>({sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.targetLanguageId||null})):[],
    careerProfile:cleanCareerProfile(form.careerProfile),
  }
  if(canViewContacts.value)result.settlement=JSON.parse(JSON.stringify(form.settlement))
  // 无查看权限时只提交实际录入的联系方式，留空交由后端保留原值。
  if(!canViewContacts.value)contactPayloadKeys.forEach(key=>{if(!String(result[key]||'').trim())delete result[key]})
  // 未修改账号时不提交快照，避免保存备注时覆盖另一页刚同步的账号或状态。
  if (!form.id || !sameWechatAccounts(form.wechatAccounts, form.wechatAccountsOriginal)) {
    result.wechatAccounts = normalizeWechatAccounts(form.wechatAccounts)
    if (form.id) result.wechatAccountsRevision = form.wechatAccountsRevision
  }
  if(isRecruitmentPool.value)talentManagedPayloadKeys.forEach(key=>delete result[key])
  return result
}
async function savePayload(allowDuplicate=false){const client=talentClient.value;return form.id?client.update(form.id,payload(allowDuplicate)):client.create(payload(allowDuplicate))}
async function flushQueuedAttachments(personId) {
  for (const category of ['photo', 'id_photo', 'life_photo', 'audio', 'interpretation_sample', 'annotation_sample']) {
    while (queuedAttachments[category].length) {
      const item = queuedAttachments[category][0]
      item.status='uploading';item.percentage=0
      let attachment
      try{attachment=await talentApi.uploadTalentAttachment(personId,category,item.raw,null,{timeout:300000,onUploadProgress:event=>{if(event.total)item.percentage=Math.round(event.loaded/event.total*100)}})}catch(error){item.status='fail';throw error}
      // 每上传成功一项就出队，失败重试时不重复上传已经成功的文件。
      queuedAttachments[category].shift()
      if (attachment?.id) form.attachments.push(attachment)
    }
  }
}
async function removeSavedAttachment(item){try{await ElMessageBox.confirm(`确认删除附件“${item.originalName}”？`,'删除附件',{type:'warning'});await talentApi.deleteTalentAttachment(form.id,item.id);form.attachments=form.attachments.filter(value=>value.id!==item.id);delete detailCache[form.id];ElMessage.success('附件已删除')}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'删除附件失败')}}
async function submit(continueCreating = false) {
  if (saving.value) return
  saving.value = true
  continuingSave.value = continueCreating && canContinueCreate.value
  let invalidForm = false
  let focusNextName = false
  let attachmentStage = false
  let invalidAnnotation = false
  try {
    if (!filledNameCount.value) { nameFieldsExpanded.value = true; await nextTick() }
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) { invalidForm = true; return }
    if (hasCapability('annotation')) {
      let message = ''
      if (form.annotationLanguageSkills.some(item => !item.sourceLanguageId)) message = '请选择完整的标注语言方向'
      else if (form.annotationLanguageSkills.some(item => item.directionType === 'translation' && !item.targetLanguageId)) message = '翻译类标注必须选择目标语种'
      else {
        const keys = form.annotationLanguageSkills.map(item => `${item.sourceLanguageId}:${item.targetLanguageId || ''}`)
        if (new Set(keys).size !== keys.length) message = '标注语言方向不能重复'
      }
      if (message) {
        ElMessage.warning(message)
        invalidAnnotation = true
        return
      }
    }
    let saved
    try {
      saved = await savePayload()
    } catch (error) {
      const detail = error.rawDetail
      if (detail?.code !== 'duplicate_talent') throw error
      const first = detail.duplicates?.[0]
      let openExisting = false
      try {
        await ElMessageBox.confirm(`发现联系方式相同的人才“${first?.fullName || first?.full_name || '未知'}”。打开已有档案，还是仍然新建？`, '疑似重复人才', {
          confirmButtonText: '打开已有档案', cancelButtonText: '仍然新建', distinguishCancelAndClose: true, type: 'warning',
        })
        openExisting = true
      } catch (action) {
        if (action !== 'cancel') return
        saved = await savePayload(true)
      }
      if (openExisting) {
        // 直接切换编辑内容，不关闭弹窗，避免 closed 回调清空刚载入的档案。
        if (first) await openEdit(first)
        return
      }
    }
    // 档案已落库：后续附件失败也必须使用同一 ID 更新，不能再次创建。
    form.id = saved.id
    form.resourceCode = saved.resourceCode || form.resourceCode
    form.wechatAccounts = normalizeWechatAccounts(saved.wechatAccounts, saved.wechatAccount)
    form.wechatAccountsOriginal = [...form.wechatAccounts]
    form.wechatAccountsRevision = saved.wechatAccountsRevision || 1
    if(saved.settlement)form.settlement.revision=saved.settlement.revision
    if(saved.resumeProfile)form.resumeProfile.revision=saved.resumeProfile.revision
    delete detailCache[saved.id]
    attachmentStage = true
    await flushQueuedAttachments(saved.id)
    attachmentStage = false
    const savedName = displayTalentName(saved, preferredFormName.value || '人才')
    const batchInfo = keepBatchInfo.value ? {
      registrationSource: form.registrationSource,
      wechatAccounts: [...form.wechatAccounts],
      wechatGroups: form.wechatGroups,
      wecomLargeGroups: form.wecomLargeGroups,
    } : {}
    clearDraft()
    if (continuingSave.value) {
      initializeCreateForm(batchInfo)
      await beginDraft('create')
      focusNextName = true
      ElMessage.success(`已保存人才：${savedName}，可继续新增`)
    } else {
      editorVisible.value = false
      ElMessage.success('人才档案已保存')
    }
    // 列表查询自行提示刷新错误，不影响本次保存成功的结果。
    void fetchData()
  } catch (error) {
    await formRef.value?.applyServerErrors?.(error)
    if (error !== false && error !== 'cancel' && error !== 'close') {
      ElMessage.error(attachmentStage
        ? `人才档案已保存，附件未全部上传，请重试保存：${error.detail || '附件上传失败'}`
        : error.detail || '保存失败')
    }
  } finally {
    saving.value = false
    continuingSave.value = false
    await nextTick()
    if (invalidForm) await formRef.value?.locateFirstError()
    if (invalidAnnotation) {
      // 解锁后复用公共字段导航，避免只提示而无法定位错误。
      let matches = []
      fetchFieldSuggestions('语言方向', items => { matches = items })
      if (matches[0]) await locateDialogField(matches[0])
    }
    if (focusNextName) {
      await onEditorOpened()
      focusFormTarget(editorBodyRef.value?.querySelector('.el-form-item'))
    }
  }
}
async function showLinkedTalent() {
  if (!route.query.openTalent) return
  const person = await loadDetail(String(route.query.openTalent))
  if (!person) return
  search.keyword = person.resourceCode || person.fullName
  pagination.page = 1
  await fetchData()
}
watch(()=>route.path,()=>{pagination.page=1;fetchData()});watch(()=>route.query.openTalent,showLinkedTalent);onMounted(async()=>{const results=await Promise.allSettled([getProjectLanguages(),fetchData()]);languages.value=results[0].status==='fulfilled'?results[0].value:[];await showLinkedTalent()});onBeforeUnmount(()=>{clearTimeout(timer);clearTimeout(languageSearchTimer);controller?.abort()})
</script>

<style scoped>
.wechat-account-hint{display:block;color:var(--el-text-color-secondary);line-height:1.6;margin-top:8px}
.talent-name-cell{display:inline-flex;align-items:center;gap:6px;max-width:100%}
.talent-name-cell .talent-name-link{min-width:0;white-space:normal;overflow-wrap:anywhere}
.talent-name-cell .el-tag{flex-shrink:0}
.card-header,.header-actions,.advanced-actions,.tag-list,.action-buttons,.status-option-row{display:flex;align-items:center}.status-option-row{gap:8px;width:100%}.status-switch-tag.el-tag{display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;max-width:100%;cursor:pointer;user-select:none;vertical-align:middle;transition:opacity .15s ease}.status-switch-tag :deep(.el-tag__content){display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap;white-space:nowrap;line-height:1}.status-switch-text{line-height:1}.status-switch-caret{width:10px;height:10px;flex-shrink:0;margin:0;font-size:10px}.status-switch-tag:hover{opacity:.85}.status-switch-tag.is-updating{pointer-events:none;opacity:.55}.status-current-icon{color:var(--el-color-primary)}.action-buttons{justify-content:center;flex-wrap:nowrap;white-space:nowrap}.card-header,.advanced-actions{justify-content:space-between}.header-actions,.tag-list{gap:8px}.page-title{font-size:18px;font-weight:600}.page-subtitle{margin-left:12px;color:var(--el-text-color-secondary);font-size:13px}.search-form{margin-bottom:4px}.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-title{margin-bottom:14px;font-weight:600}.performance-sort-controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--el-border-color-lighter)}.performance-sort-controls label{display:grid;gap:3px;color:var(--el-text-color-secondary);font-size:12px}.pagination{justify-content:flex-end;margin-top:16px}.detail-content{max-height:560px;overflow-y:auto}.detail-content h4{margin:14px 0 8px}.detail-content h4:first-child{margin-top:0}.pre-wrap{white-space:pre-wrap;word-break:break-word}
.talent-editor-body{padding:16px 20px 20px;background:var(--el-fill-color-lighter)}
.talent-editor-form{width:100%}
.talent-editor-form :deep(.el-form-item){margin-bottom:18px}
.talent-editor-form :deep(.el-form-item__label){height:auto;padding:0 0 7px;color:var(--el-text-color-regular);font-size:14px;font-weight:500;line-height:1.4}
.talent-editor-form :deep(.el-form-item__content){min-width:0;line-height:normal}
.talent-editor-form :deep(.el-input__inner),.talent-editor-form :deep(.el-textarea__inner),.talent-editor-form :deep(.el-select__selected-item){font-size:14px}
.form-section{margin-bottom:16px;padding:18px 18px 2px;border:1px solid var(--el-border-color-lighter);border-radius:10px;background:var(--el-bg-color);box-shadow:0 2px 8px rgb(15 23 42 / 4%)}
.form-section:last-child{margin-bottom:0}
.form-section h3{display:flex;align-items:center;gap:8px;margin:0 0 18px;color:var(--el-text-color-primary);font-size:16px;font-weight:600;line-height:1.4}
.form-section h3::before{width:3px;height:17px;flex:0 0 3px;border-radius:2px;background:var(--el-color-primary);content:""}
.form-section-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px}
.form-section-header h3{margin-bottom:4px}
.section-hint{color:var(--el-text-color-secondary);font-size:13px;line-height:1.5}
.required-mark{color:var(--el-color-danger)}
.name-collapsed-summary{margin-bottom:18px;padding:11px 13px;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-fill-color-light);color:var(--el-text-color-regular);font-size:14px;line-height:1.5}
.sub-record{margin:12px 0;padding:14px 14px 0;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-extra-light)}
.performance-domain{margin-top:18px;padding-top:16px;border-top:1px solid var(--el-border-color-lighter)}
.performance-domain>h4{margin:0 0 14px;font-size:16px}
.performance-rating-hint{display:block;margin-top:8px;line-height:1.5;color:var(--el-text-color-secondary)}
.performance-form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:14px}
.performance-form-item{min-width:0;padding:16px 16px 2px;border:1px solid var(--el-border-color-lighter);border-radius:8px;background:var(--el-fill-color-extra-light)}
.performance-form-item--overall{background:var(--el-color-primary-light-9);border-color:var(--el-color-primary-light-7)}
.performance-form-item h4,.performance-form-item h5{margin:0 0 14px;padding-bottom:10px;border-bottom:1px solid var(--el-border-color-lighter);color:var(--el-text-color-primary);font-size:15px;font-weight:600;line-height:1.4}
.performance-form-item :deep(.el-input-number){width:100%}
.performance-form-item :deep(.el-input-number .el-input__inner){padding-right:54px;text-align:left}
.performance-summary-cell{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.attachment-list{display:flex;gap:8px;flex-wrap:wrap}
.talent-editor-footer{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:10px}
.talent-batch-options{display:flex;flex-direction:column;align-items:flex-start;margin-right:auto;text-align:left}
.talent-editor-actions{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px}
.talent-editor-actions .el-button+.el-button{margin-left:0}
.talent-editor-footer .el-button{min-width:88px}
@media(max-width:768px){.card-header{align-items:flex-start;gap:12px;flex-direction:column}.page-subtitle{display:block;margin:4px 0 0}.search-form .el-form-item{width:100%;margin-right:0}.search-form .el-input,.search-form .el-select{width:100%!important}.performance-sort-controls,.performance-form-grid{grid-template-columns:1fr}.talent-editor-body{padding:12px}.form-section{padding:16px 14px 2px}.form-section-header{align-items:stretch;flex-direction:column}.form-section-header .el-button{align-self:flex-end}}
</style>

<style>
.talent-advanced-popper,.talent-detail-popper{max-width:calc(100vw - 32px)!important}.talent-detail-popper .detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.talent-editor-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.talent-editor-dialog .el-dialog__header,.talent-editor-dialog .el-dialog__footer{flex:0 0 auto}.talent-editor-dialog .el-dialog__body{flex:1;min-height:0;padding:0;overflow-y:auto}.talent-editor-dialog .el-dialog__footer{padding:14px 20px;border-top:1px solid var(--el-border-color-lighter);background:var(--el-bg-color);box-shadow:0 -3px 10px rgb(15 23 42 / 5%)}
</style>

<style scoped>
.talent-editor-form :deep(.form-section>h3),.talent-editor-form :deep(.form-section-header h3),.talent-editor-form :deep(.performance-domain>h4){display:none}
</style>

<style>
.talent-detail-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.talent-detail-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.talent-detail-dialog .el-dialog__header,.talent-detail-dialog .el-dialog__footer{flex:0 0 auto}.talent-detail-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter)}.talent-detail-title{user-select:text;cursor:text}
</style>
