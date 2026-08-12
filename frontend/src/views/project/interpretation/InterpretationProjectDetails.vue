<template>
  <el-card class="interpretation-card">
    <template #header>
      <div class="card-header">
        <span>口译项目详情</span>
        <div class="header-actions">
          <TableColumnSettings
            v-model="visibleColumnKeys"
            :columns="tableColumns"
            :column-count="2"
            @reset="resetColumns"
          />
          <el-button v-if="canWrite" type="primary" @click="handleAdd">新增口译项目</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input
          v-model="searchForm.keyword"
          placeholder="订单号、项目名称、客户名称或客户单号"
          clearable
          style="width: 300px"
          @input="handleTextSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="项目状态">
        <el-select v-model="searchForm.projectStatus" clearable placeholder="全部" style="width: 150px" @change="handleSearch">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-popover
          v-model:visible="advancedVisible"
          trigger="click"
          placement="bottom-end"
          :width="760"
          popper-class="interpretation-advanced-popover"
        >
          <template #reference>
            <el-button>
              高级筛选
              <span v-if="advancedCount" class="filter-count">{{ advancedCount }}</span>
            </el-button>
          </template>
          <div class="advanced-panel">
            <div class="advanced-header">
              <span>高级筛选</span>
              <div>
                <el-button v-if="advancedCount" link type="primary" @click="clearAdvanced">清空高级条件</el-button>
                <el-button link @click="advancedVisible = false">关闭</el-button>
              </div>
            </div>
            <el-form label-position="top">
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="项目类型">
                    <el-select v-model="searchForm.projectType" clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="预定日期">
                    <el-date-picker
                      v-model="searchForm.scheduledDateRange"
                      type="daterange"
                      value-format="YYYY-MM-DD"
                      range-separator="至"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      @change="handleSearch"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :lg="8">
                  <el-form-item label="译员">
                    <el-select v-model="searchForm.translatorId" filterable clearable placeholder="全部" @change="handleSearch">
                      <el-option v-for="item in translators" :key="item.id" :label="translatorOptionLabel(item)" :value="item.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border class="interpretation-table">
      <el-table-column type="index" label="序号" width="64" align="center" fixed="left" />
      <el-table-column label="订单号" width="210" fixed="left">
        <template #default="{ row }">
          <div class="order-cell">
            <el-popover
              trigger="click"
              placement="left"
              :width="760"
              title="口译项目详情"
              popper-class="interpretation-detail-popover"
              @show="loadDetail(row.id)"
            >
              <template #reference>
                <el-button type="primary" link @click.stop>{{ row.orderNo }}</el-button>
              </template>
              <div class="detail-content" v-loading="detailLoadingId === row.id">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(detailRow(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="客户全称">{{ textValue(detailRow(row).clientFullName) }}</el-descriptions-item>
                  <el-descriptions-item label="客户领域">{{ textValue(detailRow(row).clientDomain) }}</el-descriptions-item>
                  <el-descriptions-item label="项目时间" :span="2">{{ timeRangesText(detailRow(row).timeRanges) }}</el-descriptions-item>
                  <el-descriptions-item label="项目地点" :span="2">{{ arrayText(detailRow(row).locations, '、') }}</el-descriptions-item>
                  <el-descriptions-item label="客户咨询时间">{{ formatDateTime(detailRow(row).customerConsultationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="客户确认时间">{{ formatDateTime(detailRow(row).customerConfirmationTime) }}</el-descriptions-item>
                  <el-descriptions-item label="口译领域" :span="2">{{ textValue(detailRow(row).interpretationDomain) }}</el-descriptions-item>
                  <el-descriptions-item label="口译内容" :span="2">{{ textValue(detailRow(row).interpretationContent) }}</el-descriptions-item>
                  <el-descriptions-item label="项目文件路径" :span="2">{{ textValue(detailRow(row).filePath) }}</el-descriptions-item>
                  <el-descriptions-item label="报价单路径" :span="2">{{ textValue(detailRow(row).quotationPath) }}</el-descriptions-item>
                  <el-descriptions-item label="合同路径" :span="2">{{ textValue(detailRow(row).contractPath) }}</el-descriptions-item>
                  <el-descriptions-item label="客户对信实评价" :span="2">
                    {{ ratingText(detailRow(row).clientRating, detailRow(row).clientRatingNote) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="客户对译员评价" :span="2">
                    {{ interpreterRatingsText(detailRow(row).interpreterAssignments) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="发圈请求" :span="2">{{ textValue(detailRow(row).socialPostRequest) }}</el-descriptions-item>
                  <el-descriptions-item label="资源请求" :span="2">{{ textValue(detailRow(row).resourceRequest) }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="2">
                    <div class="remarks-detail">{{ textValue(detailRow(row).remarks) }}</div>
                  </el-descriptions-item>
                  <el-descriptions-item label="邮件主题预览" :span="2">{{ textValue(detailRow(row).emailSubjectPreview) }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </el-popover>
            <div class="path-actions">
              <el-button link type="primary" :icon="FolderOpened" title="打开路径" @click.stop="openProjectPath(row)" />
              <el-button link type="primary" :icon="CopyDocument" title="复制路径" @click.stop="copyProjectPath(row)" />
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        v-for="column in visibleTableColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :min-width="column.minWidth"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <el-tag v-if="column.key === 'projectStatus'" :type="statusType(row.projectStatus)">{{ statusLabel(row.projectStatus) }}</el-tag>
          <el-popover
            v-else-if="column.key === 'clientShortName' && row.clientShortName"
            trigger="click"
            placement="left"
            :width="420"
            title="客户关联信息"
            popper-class="interpretation-client-popover"
          >
            <template #reference>
              <el-button type="primary" link @click.stop>{{ row.clientShortName }}</el-button>
            </template>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="子客户/联系人">{{ textValue(row.subClientContact) }}</el-descriptions-item>
              <el-descriptions-item label="客户单号/项目标识">{{ textValue(row.customerOrderNo) }}</el-descriptions-item>
            </el-descriptions>
          </el-popover>
          <el-popover
            v-else-if="column.key === 'assignedInterpretersDisplay'"
            trigger="click"
            placement="left"
            :width="760"
            title="译员安排详情"
            popper-class="interpretation-interpreter-popover"
            @show="loadDetail(row.id)"
          >
            <template #reference>
              <el-button type="primary" link @click.stop>{{ row.assignedInterpretersDisplay || '查看要求' }}</el-button>
            </template>
            <div class="interpreter-detail-content" v-loading="detailLoadingId === row.id">
              <div class="interpreter-detail-section-title">常用要求</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="译员人数">{{ textValue(detailRow(row).requiredInterpreterCount) }}</el-descriptions-item>
                <el-descriptions-item label="译员性别">{{ textValue(detailRow(row).requiredInterpreterGender) }}</el-descriptions-item>
                <el-descriptions-item label="口译水平">{{ textValue(detailRow(row).requiredInterpretationLevel) }}</el-descriptions-item>
                <el-descriptions-item label="特殊要求">{{ textValue(detailRow(row).interpreterSpecialRequirements) }}</el-descriptions-item>
              </el-descriptions>
              <div class="interpreter-detail-section-title">形象与着装要求</div>
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="译员身高">{{ textValue(detailRow(row).interpreterHeightRequirement) }}</el-descriptions-item>
                <el-descriptions-item label="译员相貌">{{ textValue(detailRow(row).interpreterAppearanceRequirement) }}</el-descriptions-item>
                <el-descriptions-item label="着装要求">{{ textValue(detailRow(row).interpreterDressRequirement) }}</el-descriptions-item>
              </el-descriptions>
              <div class="interpreter-detail-section-title">
                已安排译员（{{ detailRow(row).interpreterAssignments?.length || 0 }} 人）
              </div>
              <template v-if="detailRow(row).interpreterAssignments?.length">
                <el-descriptions
                  v-for="person in detailRow(row).interpreterAssignments"
                  :key="person.id"
                  :title="person.translatorName"
                  :column="2"
                  border
                  size="small"
                  class="translator-profile"
                >
                  <el-descriptions-item label="译员编号">{{ textValue(person.translatorCode) }}</el-descriptions-item>
                  <el-descriptions-item label="口译水平">{{ textValue(person.translatorInterpretationLevel) }}</el-descriptions-item>
                  <el-descriptions-item label="性别">{{ textValue(person.translatorGender) }}</el-descriptions-item>
                  <el-descriptions-item label="身高">{{ textValue(person.translatorHeight) }}</el-descriptions-item>
                  <el-descriptions-item label="相貌">{{ textValue(person.translatorAppearance) }}</el-descriptions-item>
                  <el-descriptions-item label="语种">{{ textValue(person.translatorLanguages) }}</el-descriptions-item>
                  <el-descriptions-item label="翻译类型">{{ textValue(person.translatorTranslationType) }}</el-descriptions-item>
                  <el-descriptions-item label="方向">{{ textValue(person.translatorDirection) }}</el-descriptions-item>
                  <el-descriptions-item label="简历路径" :span="2">{{ textValue(person.translatorResumePath) }}</el-descriptions-item>
                  <el-descriptions-item label="客户评价" :span="2">{{ ratingText(person.customerRating, person.evaluationNote) }}</el-descriptions-item>
                </el-descriptions>
              </template>
              <el-empty v-else description="暂未安排译员" :image-size="64" />
            </div>
          </el-popover>
          <span v-else-if="column.key === 'projectName'">{{ row.projectName || '待完善' }}</span>
          <span v-else>{{ textValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton v-if="canWrite" action="edit" @click="handleEdit(row)" />
          <TableActionButton v-if="canWrite" action="delete" @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @size-change="fetchData"
      @current-change="fetchData"
    />

    <el-dialog
      v-model="dialogVisible"
      class="interpretation-editor-dialog"
      :title="dialogTitle"
      width="min(1080px, calc(100vw - 32px))"
      top="5vh"
      @closed="resetForm"
    >
      <div ref="dialogBodyRef" class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
          <section class="form-section">
            <h3>基础与客户</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12">
                <el-form-item label="项目状态" prop="projectStatus">
                  <el-select v-model="form.projectStatus" style="width: 100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24"><el-form-item label="项目名称"><el-input v-model="form.projectName" placeholder="完善时间、地点、方向和类型后点击生成，也可手工编辑" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="项目类型">
                  <el-select v-model="form.projectTypes" multiple clearable collapse-tags collapse-tags-tooltip style="width: 100%">
                    <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12"><el-form-item label="具体任务"><el-input v-model="form.taskDescription" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12">
                <el-form-item label="关联客户">
                  <el-select v-model="form.clientId" filterable clearable style="width: 100%" placeholder="选择已有客户，或在下方录入新客户" @change="handleClientChange">
                    <el-option v-for="item in clients" :key="item.id" :label="`${item.client_short_name} · ${item.client_name}`" :value="item.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12"><el-form-item label="现客户经理"><el-input v-model="form.currentClientManager" disabled /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="客户简称"><el-input v-model="form.clientShortName" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户全称"><el-input v-model="form.clientFullName" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户编号"><el-input v-model="form.clientCode" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8">
                <el-form-item label="子客户">
                  <el-select v-model="form.subClientId" clearable filterable style="width: 100%">
                    <el-option v-for="item in selectedClientSubClients" :key="item.id" :label="item.client_short_name" :value="item.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8"><el-form-item label="联系人"><el-input v-model="form.contactName" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户单号/标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户预算"><el-input v-model="form.customerBudget" placeholder="可填写金额、计价单位及差旅说明" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户咨询时间"><el-date-picker v-model="form.customerConsultationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户确认时间"><el-date-picker v-model="form.customerConfirmationTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" /></el-form-item></el-col>
            </el-row>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>时间、地点与命名</h3><el-button type="primary" plain @click="addTimeRange">增加时间段</el-button></div>
            <div v-for="(item, index) in form.timeRanges" :key="index" class="repeat-card">
              <div class="repeat-title">时间段 {{ index + 1 }}<el-button v-if="form.timeRanges.length > 1" link type="danger" @click="form.timeRanges.splice(index, 1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="12"><el-form-item label="预定开始"><el-date-picker v-model="item.scheduledStart" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="预定结束"><el-date-picker v-model="item.scheduledEnd" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="实际开始"><el-date-picker v-model="item.actualStart" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" clearable /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="实际结束"><el-date-picker v-model="item.actualEnd" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" clearable /></el-form-item></el-col>
              </el-row>
            </div>
            <el-row :gutter="12">
              <el-col v-for="index in 4" :key="index" :xs="24" :md="12">
                <el-form-item :label="`项目地点${['一', '二', '三', '四'][index - 1]}`"><el-input v-model="form.locations[index - 1]" /></el-form-item>
              </el-col>
            </el-row>
            <div class="section-title-row"><h4>口译方向</h4><div><el-button link type="primary" @click="addLanguage">新增语种</el-button><el-button type="primary" plain @click="addDirection">增加方向</el-button></div></div>
            <div v-for="(item, index) in form.languageDirections" :key="index" class="direction-row">
              <el-select v-model="item.sourceLanguageId" filterable placeholder="语种 A">
                <el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-language-tag">新</el-tag></el-option>
              </el-select>
              <span class="direction-arrow">↔</span>
              <el-select v-model="item.targetLanguageId" filterable placeholder="语种 B">
                <el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-language-tag">新</el-tag></el-option>
              </el-select>
              <el-button link type="danger" @click="form.languageDirections.splice(index, 1)">删除</el-button>
            </div>
            <el-button type="primary" @click="generateProjectName">生成项目名称</el-button>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>译员安排与评价</h3><el-button type="primary" plain @click="addInterpreter">增加译员</el-button></div>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="译员人数"><el-input-number v-model="form.requiredInterpreterCount" :min="0" style="width: 100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="译员性别"><el-select v-model="form.requiredInterpreterGender" clearable placeholder="不限" style="width: 100%"><el-option label="不限" value="不限" /><el-option label="男" value="男" /><el-option label="女" value="女" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="口译水平"><el-select v-model="form.requiredInterpretationLevel" clearable placeholder="请选择" style="width: 100%"><el-option label="初级" value="初级" /><el-option label="中级" value="中级" /><el-option label="高级" value="高级" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="特殊要求"><el-input v-model="form.interpreterSpecialRequirements" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <div class="interpreter-requirement-group">
              <div class="requirement-group-title">形象与着装要求</div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="8"><el-form-item label="译员身高"><el-input v-model="form.interpreterHeightRequirement" /></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="译员相貌"><el-input v-model="form.interpreterAppearanceRequirement" /></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="着装要求"><el-input v-model="form.interpreterDressRequirement" /></el-form-item></el-col>
              </el-row>
            </div>
            <div v-for="(item, index) in form.interpreterAssignments" :key="index" class="repeat-card">
              <div class="repeat-title">译员 {{ index + 1 }}<el-button link type="danger" @click="form.interpreterAssignments.splice(index, 1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="12"><el-form-item label="译员"><el-select v-model="item.translatorId" filterable style="width: 100%"><el-option v-for="person in translators" :key="person.id" :label="translatorOptionLabel(person)" :value="person.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户评价"><el-select v-model="item.customerRating" clearable style="width: 100%"><el-option v-for="rating in ratingOptions" :key="rating.value" :label="rating.label" :value="rating.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24"><el-form-item label="评价备注"><el-input v-model="item.evaluationNote" type="textarea" :rows="2" /></el-form-item></el-col>
              </el-row>
            </div>
          </section>

          <section class="form-section">
            <h3>扩展信息</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="口译领域"><el-input v-model="form.interpretationDomain" type="textarea" :rows="2" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="口译内容"><el-input v-model="form.interpretationContent" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="项目文件路径"><PathInput v-model="form.filePath" @open="openPathValue(form.filePath)" @copy="copyPathValue(form.filePath)" /></el-form-item>
            <el-form-item label="报价单路径"><PathInput v-model="form.quotationPath" @open="openPathValue(form.quotationPath)" @copy="copyPathValue(form.quotationPath)" /></el-form-item>
            <el-form-item label="合同路径"><PathInput v-model="form.contractPath" @open="openPathValue(form.contractPath)" @copy="copyPathValue(form.contractPath)" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="客户对信实评价"><el-select v-model="form.clientRating" clearable style="width: 100%"><el-option v-for="rating in ratingOptions" :key="rating.value" :label="rating.label" :value="rating.value" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="评价备注"><el-input v-model="form.clientRatingNote" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="发圈请求"><el-input v-model="form.socialPostRequest" type="textarea" :rows="2" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="资源请求"><el-input v-model="form.resourceRequest" type="textarea" :rows="2" /></el-form-item></el-col>
            </el-row>
            <el-form-item label="备注" class="remarks-form-item"><el-input v-model="form.remarks" type="textarea" :rows="5" /></el-form-item>
            <el-form-item label="邮件主题预览"><el-input v-model="form.emailSubjectPreview" type="textarea" :rows="3" /></el-form-item>
          </section>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { CopyDocument, FolderOpened } from '@element-plus/icons-vue'
import { ElButton, ElInput, ElMessage, ElMessageBox } from 'element-plus'
import * as projectApi from '@/api/interpretationProjects'
import * as clientApi from '@/api/clients'
import * as translatorApi from '@/api/translators'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'

const PathInput = defineComponent({
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'open', 'copy'],
  setup(props, { emit }) {
    return () => h('div', { class: 'path-input' }, [
      h(ElInput, { modelValue: props.modelValue, 'onUpdate:modelValue': (value) => emit('update:modelValue', value) }),
      h(ElButton, { icon: FolderOpened, onClick: () => emit('open') }),
      h(ElButton, { icon: CopyDocument, onClick: () => emit('copy') }),
    ])
  },
})

const canWrite = hasPermission('projects:write')
const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增口译项目')
const formRef = ref(null)
const dialogBodyRef = ref(null)
const tableData = ref([])
const clients = ref([])
const translators = ref([])
const languages = ref([])
const detailCache = reactive({})
const detailLoadingId = ref(null)
const advancedVisible = ref(false)
let searchTimer = null
let requestController = null
let requestId = 0

const projectTypeOptions = [
  { value: 'onsite', label: '现场口译' },
  { value: 'booth', label: '展会摊位口译' },
  { value: 'exhibition_escort', label: '展会陪同口译' },
  { value: 'escort', label: '陪同口译' },
  { value: 'small_business_meeting', label: '小型商务会议口译' },
  { value: 'consecutive', label: '会议交传口译' },
  { value: 'simultaneous', label: '会议同传口译' },
  { value: 'online_meeting', label: '线上会议口译' },
  { value: 'online_simultaneous', label: '线上同传口译' },
]
const projectTypeMap = Object.fromEntries(projectTypeOptions.map((item) => [item.value, item.label]))
const statusOptions = [
  { value: 'initial_follow_up', label: '初步跟进中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'cancelled', label: '已取消' },
  { value: 'partially_cancelled', label: '已部分取消' },
  { value: 'ended', label: '已结束' },
  { value: 'settled', label: '已结款' },
]
const statusMap = Object.fromEntries(statusOptions.map((item) => [item.value, item.label]))
const ratingOptions = [
  { value: 'very_satisfied', label: '非常满意' },
  { value: 'satisfied', label: '满意' },
  { value: 'basically_satisfied', label: '基本满意' },
  { value: 'dissatisfied', label: '不满意' },
  { value: 'very_dissatisfied', label: '非常不满意' },
]
const ratingMap = Object.fromEntries(ratingOptions.map((item) => [item.value, item.label]))

const tableColumns = [
  { key: 'projectName', label: '项目名称', minWidth: 210 },
  { key: 'taskDescription', label: '具体任务', minWidth: 180 },
  { key: 'currentClientManager', label: '现客户经理', width: 130 },
  { key: 'projectStatus', label: '项目状态', width: 130 },
  { key: 'clientShortName', label: '客户简称', width: 150 },
  { key: 'subClientContact', label: '子客户/联系人', minWidth: 170 },
  { key: 'customerOrderNo', label: '客户单号/项目标识', minWidth: 180 },
  { key: 'languageDirectionsDisplay', label: '口译方向', minWidth: 210 },
  { key: 'customerBudget', label: '客户预算', minWidth: 160 },
  { key: 'assignedInterpretersDisplay', label: '译员安排', minWidth: 180 },
  { key: 'clientCode', label: '客户编号', width: 150 },
  { key: 'translatorCodes', label: '译员编号', minWidth: 160 },
]
const defaultColumns = [
  'projectName', 'taskDescription', 'currentClientManager', 'projectStatus',
  'clientShortName',
  'languageDirectionsDisplay', 'customerBudget', 'assignedInterpretersDisplay',
]
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns(
  'interpretation-details-v2', tableColumns, defaultColumns
)
const visibleTableColumns = computed(() => tableColumns.filter((item) => isVisible(item.key)))

const pagination = reactive({ page: 1, limit: 10, total: 0 })
const searchForm = reactive({
  keyword: '', projectStatus: '', projectType: '', scheduledDateRange: [], translatorId: '',
})
const advancedCount = computed(() => [
  searchForm.projectType,
  searchForm.scheduledDateRange?.length ? 'date' : '',
  searchForm.translatorId,
].filter(Boolean).length)

const emptyTimeRange = () => ({ scheduledStart: '', scheduledEnd: '', actualStart: '', actualEnd: '' })
const defaultForm = () => ({
  id: '', orderNo: '', projectName: '', projectTypes: [], taskDescription: '',
  clientId: '', subClientId: '', clientShortName: '', clientFullName: '', clientCode: '',
  currentClientManager: '', contactName: '', customerOrderNo: '', projectStatus: 'initial_follow_up',
  locations: ['', '', '', ''], customerBudget: '', customerConsultationTime: '', customerConfirmationTime: '',
  requiredInterpreterCount: null, requiredInterpreterGender: '', requiredInterpretationLevel: '',
  interpreterSpecialRequirements: '', interpreterHeightRequirement: '',
  interpreterAppearanceRequirement: '', interpreterDressRequirement: '',
  interpretationDomain: '', interpretationContent: '', filePath: '', quotationPath: '', contractPath: '',
  clientRating: '', clientRatingNote: '', remarks: '', emailSubjectPreview: '', socialPostRequest: '', resourceRequest: '',
  timeRanges: [emptyTimeRange()], languageDirections: [], interpreterAssignments: [],
})
const form = reactive(defaultForm())
const rules = { projectStatus: [{ required: true, message: '请选择项目状态', trigger: 'change' }] }

const selectedClient = computed(() => clients.value.find((item) => item.id === form.clientId))
const selectedClientSubClients = computed(() => selectedClient.value?.sub_clients || [])

const statusLabel = (value) => statusMap[value] || value || '-'
const statusType = (value) => ({ initial_follow_up: 'warning', in_progress: 'primary', cancelled: 'danger', partially_cancelled: 'warning', ended: 'success', settled: 'success' }[value] || 'info')
const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
const arrayText = (value, separator = '；') => Array.isArray(value) && value.length ? value.join(separator) : '-'
const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(String(value).replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}
const formatRange = (item) => {
  const scheduled = `${formatDateTime(item.scheduledStart)} 至 ${formatDateTime(item.scheduledEnd)}`
  const actual = item.actualStart || item.actualEnd ? `；实际 ${formatDateTime(item.actualStart)} 至 ${formatDateTime(item.actualEnd)}` : ''
  return `${scheduled}${actual}`
}
const timeRangesText = (items) => Array.isArray(items) && items.length ? items.map(formatRange).join('；') : '-'
const projectTypesText = (row) => Array.isArray(row.projectTypes) && row.projectTypes.length ? row.projectTypes.map((value) => projectTypeMap[value] || value).join('；') : '-'
const ratingText = (rating, note) => [ratingMap[rating] || rating, note].filter(Boolean).join('：') || '-'
const interpreterRatingsText = (items) => Array.isArray(items) && items.length
  ? items.map((item) => `${item.translatorName}：${ratingText(item.customerRating, item.evaluationNote)}`).join('；')
  : '-'
const translatorOptionLabel = (item) => {
  const name = item.translator_name || item.translatorName
  const code = item.translator_code || item.translatorCode
  const level = item.interpretation_level || item.interpretationLevel
  return `${name}${code ? `（${code}）` : ''}${level ? ` · ${level}` : ''}`
}

const buildFilters = () => {
  const [start, end] = searchForm.scheduledDateRange || []
  return {
    keyword: searchForm.keyword.trim() || undefined,
    project_status: searchForm.projectStatus || undefined,
    project_type: searchForm.projectType || undefined,
    scheduled_date_start: start || undefined,
    scheduled_date_end: end || undefined,
    translator_id: searchForm.translatorId || undefined,
  }
}
const fetchData = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const currentId = ++requestId
  loading.value = true
  const filters = buildFilters()
  try {
    const [rows, count] = await Promise.all([
      projectApi.getInterpretationProjects({ skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit, ...filters }, { signal: requestController.signal }),
      projectApi.getInterpretationProjectCount(filters, { signal: requestController.signal }),
    ])
    if (currentId !== requestId) return
    tableData.value = Array.isArray(rows) ? rows : []
    pagination.total = count?.total || 0
  } catch (error) {
    if (currentId !== requestId || error?.code === 'ERR_CANCELED') return
    tableData.value = []
    pagination.total = 0
    ElMessage.error(error.detail || '加载口译项目失败')
  } finally {
    if (currentId === requestId) loading.value = false
  }
}
const handleSearch = () => { clearTimeout(searchTimer); pagination.page = 1; fetchData() }
const handleTextSearch = (value) => {
  clearTimeout(searchTimer)
  if (!value?.trim()) return handleSearch()
  searchTimer = setTimeout(handleSearch, 400)
}
const resetSearch = () => { Object.assign(searchForm, { keyword: '', projectStatus: '', projectType: '', scheduledDateRange: [], translatorId: '' }); handleSearch() }
const clearAdvanced = () => { Object.assign(searchForm, { projectType: '', scheduledDateRange: [], translatorId: '' }); handleSearch() }

const loadReferenceData = async () => {
  const [clientRows, translatorRows, languageRows] = await Promise.allSettled([
    clientApi.getClients({ skip: 0, limit: 500, frequent_first: true }),
    translatorApi.getTranslators({ skip: 0, limit: 500 }),
    projectApi.getInterpretationLanguages(),
  ])
  clients.value = clientRows.status === 'fulfilled' && Array.isArray(clientRows.value) ? clientRows.value : []
  translators.value = translatorRows.status === 'fulfilled' && Array.isArray(translatorRows.value) ? translatorRows.value : []
  languages.value = languageRows.status === 'fulfilled' && Array.isArray(languageRows.value) ? languageRows.value : []
}
const loadDetail = async (id, force = false) => {
  if (!id) return null
  if (!force && detailCache[id]) return detailCache[id]
  detailLoadingId.value = id
  try {
    const detail = await projectApi.getInterpretationProject(id)
    detailCache[id] = detail
    return detail
  } catch (error) {
    ElMessage.error(error.detail || '加载项目详情失败')
    return null
  } finally {
    detailLoadingId.value = null
  }
}
const detailRow = (row) => detailCache[row.id] || row

const handleClientChange = (id) => {
  const client = clients.value.find((item) => item.id === id)
  form.subClientId = ''
  if (!client) {
    form.currentClientManager = ''
    return
  }
  form.clientShortName = client.client_short_name || ''
  form.clientFullName = client.client_name || ''
  form.clientCode = client.client_code || ''
  form.currentClientManager = client.client_manager || ''
}
const addTimeRange = () => form.timeRanges.push(emptyTimeRange())
const addDirection = () => form.languageDirections.push({ sourceLanguageId: '', targetLanguageId: '' })
const addInterpreter = () => form.interpreterAssignments.push({ translatorId: '', customerRating: '', evaluationNote: '' })
const addLanguage = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要新增的语种或方言名称', '新增口译语种', {
      inputPlaceholder: '例如：粤语', inputValidator: (text) => !!text?.trim() || '语种名称不能为空',
    })
    const created = await projectApi.createInterpretationLanguage(value.trim())
    languages.value.push(created)
    ElMessage.success('语种已新增')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || '新增语种失败')
  }
}

const normalizedNestedPayload = () => ({
  timeRanges: form.timeRanges.filter((item) => item.scheduledStart || item.scheduledEnd).map((item) => ({
    scheduledStart: item.scheduledStart,
    scheduledEnd: item.scheduledEnd,
    actualStart: item.actualStart || null,
    actualEnd: item.actualEnd || null,
  })),
  languageDirections: form.languageDirections.filter((item) => item.sourceLanguageId || item.targetLanguageId).map((item) => ({
    sourceLanguageId: item.sourceLanguageId,
    targetLanguageId: item.targetLanguageId,
  })),
  interpreterAssignments: form.interpreterAssignments.filter((item) => item.translatorId).map((item) => ({
    translatorId: item.translatorId,
    customerRating: item.customerRating || null,
    evaluationNote: item.evaluationNote?.trim() || null,
  })),
})
const validateNested = (nested) => {
  if (form.timeRanges.some((item) => (item.scheduledStart || item.scheduledEnd) && (!item.scheduledStart || !item.scheduledEnd))) throw new Error('每个时间段必须同时填写预定开始和预定结束')
  if (nested.timeRanges.some((item) => new Date(item.scheduledEnd) < new Date(item.scheduledStart))) throw new Error('预定结束时间不能早于预定开始时间')
  if (form.languageDirections.some((item) => (item.sourceLanguageId || item.targetLanguageId) && (!item.sourceLanguageId || !item.targetLanguageId))) throw new Error('每个口译方向必须选择两个语种')
  if (nested.languageDirections.some((item) => item.sourceLanguageId === item.targetLanguageId)) throw new Error('口译方向的两个语种不能相同')
  const directionKeys = nested.languageDirections.map((item) => [item.sourceLanguageId, item.targetLanguageId].sort().join(':'))
  if (new Set(directionKeys).size !== directionKeys.length) throw new Error('同一双向口译方向不能重复')
  const translatorIds = nested.interpreterAssignments.map((item) => item.translatorId)
  if (new Set(translatorIds).size !== translatorIds.length) throw new Error('同一译员不能重复安排')
}
const generateProjectName = async () => {
  try {
    const nested = normalizedNestedPayload()
    validateNested(nested)
    const result = await projectApi.previewInterpretationProjectName({
      projectTypes: form.projectTypes,
      locations: form.locations.filter((item) => item?.trim()).map((item) => item.trim()),
      timeRanges: nested.timeRanges,
      languageDirections: nested.languageDirections,
    })
    form.projectName = result.projectName
    ElMessage.success('项目名称已重新生成，仍可手工修改')
  } catch (error) {
    ElMessage.warning(error.detail || error.message || '无法生成项目名称')
  }
}

const buildPayload = () => {
  const nested = normalizedNestedPayload()
  validateNested(nested)
  return {
    projectName: form.projectName?.trim() || null,
    projectTypes: form.projectTypes,
    taskDescription: form.taskDescription?.trim() || null,
    clientId: form.clientId || null,
    subClientId: form.subClientId || null,
    clientName: form.clientFullName?.trim() || null,
    clientShortName: form.clientShortName?.trim() || null,
    clientCode: form.clientCode?.trim() || null,
    contactName: form.contactName?.trim() || null,
    customerOrderNo: form.customerOrderNo?.trim() || null,
    projectStatus: form.projectStatus,
    locations: form.locations.filter((item) => item?.trim()).map((item) => item.trim()),
    customerBudget: form.customerBudget?.trim() || null,
    requiredInterpreterCount: form.requiredInterpreterCount ?? null,
    requiredInterpreterGender: form.requiredInterpreterGender || null,
    requiredInterpretationLevel: form.requiredInterpretationLevel || null,
    interpreterSpecialRequirements: form.interpreterSpecialRequirements?.trim() || null,
    interpreterHeightRequirement: form.interpreterHeightRequirement?.trim() || null,
    interpreterAppearanceRequirement: form.interpreterAppearanceRequirement?.trim() || null,
    interpreterDressRequirement: form.interpreterDressRequirement?.trim() || null,
    customerConsultationTime: form.customerConsultationTime || null,
    customerConfirmationTime: form.customerConfirmationTime || null,
    interpretationDomain: form.interpretationDomain?.trim() || null,
    interpretationContent: form.interpretationContent?.trim() || null,
    filePath: form.filePath?.trim() || null,
    quotationPath: form.quotationPath?.trim() || null,
    contractPath: form.contractPath?.trim() || null,
    clientRating: form.clientRating || null,
    clientRatingNote: form.clientRatingNote?.trim() || null,
    remarks: form.remarks?.trim() || null,
    emailSubjectPreview: form.emailSubjectPreview?.trim() || null,
    socialPostRequest: form.socialPostRequest?.trim() || null,
    resourceRequest: form.resourceRequest?.trim() || null,
    ...nested,
  }
}
const assignForm = (detail) => {
  Object.assign(form, defaultForm(), {
    ...detail,
    projectName: detail.projectName || '',
    clientId: detail.clientId || '', subClientId: detail.subClientId || '',
    clientShortName: detail.clientShortName || '', clientFullName: detail.clientFullName || '', clientCode: detail.clientCode || '',
    currentClientManager: detail.currentClientManager || '',
    requiredInterpreterCount: detail.requiredInterpreterCount ?? null,
    requiredInterpreterGender: detail.requiredInterpreterGender || '',
    requiredInterpretationLevel: detail.requiredInterpretationLevel || '',
    interpreterSpecialRequirements: detail.interpreterSpecialRequirements || '',
    interpreterHeightRequirement: detail.interpreterHeightRequirement || '',
    interpreterAppearanceRequirement: detail.interpreterAppearanceRequirement || '',
    interpreterDressRequirement: detail.interpreterDressRequirement || '',
    locations: [...(detail.locations || []), '', '', '', ''].slice(0, 4),
    customerConsultationTime: detail.customerConsultationTime || '', customerConfirmationTime: detail.customerConfirmationTime || '',
    timeRanges: detail.timeRanges?.length ? detail.timeRanges.map((item) => ({ scheduledStart: item.scheduledStart, scheduledEnd: item.scheduledEnd, actualStart: item.actualStart || '', actualEnd: item.actualEnd || '' })) : [emptyTimeRange()],
    languageDirections: (detail.languageDirections || []).map((item) => ({ sourceLanguageId: item.sourceLanguageId, targetLanguageId: item.targetLanguageId })),
    interpreterAssignments: (detail.interpreterAssignments || []).map((item) => ({ translatorId: item.translatorId, customerRating: item.customerRating || '', evaluationNote: item.evaluationNote || '' })),
  })
}
const handleAdd = () => { dialogTitle.value = '新增口译项目'; resetForm(); dialogVisible.value = true }
const handleEdit = async (row) => {
  const detail = await loadDetail(row.id, true)
  if (!detail) return
  dialogTitle.value = `编辑口译项目 · ${detail.orderNo}`
  assignForm(detail)
  dialogVisible.value = true
}
const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitLoading.value = true
  try {
    const payload = buildPayload()
    const saved = form.id
      ? await projectApi.updateInterpretationProject(form.id, payload)
      : await projectApi.createInterpretationProject(payload)
    if (form.id) delete detailCache[form.id]
    if (saved?.id) detailCache[saved.id] = saved
    ElMessage.success(form.id ? '口译项目已更新' : '口译项目已创建')
    dialogVisible.value = false
    await fetchData()
  } catch (error) {
    const message = error.detail || error.message || '保存失败'
    ElMessage.error(message)
    if (message.includes('时间')) dialogBodyRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    submitLoading.value = false
  }
}
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除口译项目“${row.orderNo}”吗？`, '删除确认', { type: 'warning' })
    await projectApi.deleteInterpretationProject(row.id)
    delete detailCache[row.id]
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.detail || '删除失败')
  }
}
const resetForm = () => { Object.assign(form, defaultForm()); formRef.value?.clearValidate() }

const toOpenPathHref = (path) => `openpath://${encodeURIComponent(String(path).replace(/^\\\\/, '')).replace(/%5C/gi, '\\').replace(/%2F/gi, '/')}`
const openPathValue = (path) => {
  if (!path?.trim()) return ElMessage.warning('暂无可打开的路径')
  window.location.href = toOpenPathHref(path.trim())
}
const copyPathValue = async (path) => {
  if (!path?.trim()) return ElMessage.warning('暂无可复制的路径')
  try { await navigator.clipboard.writeText(path.trim()); ElMessage.success('路径已复制') } catch { ElMessage.error('复制失败，请手工复制') }
}
const projectPath = async (row) => (await loadDetail(row.id))?.filePath || ''
const openProjectPath = async (row) => openPathValue(await projectPath(row))
const copyProjectPath = async (row) => copyPathValue(await projectPath(row))

onMounted(async () => { await loadReferenceData(); await fetchData() })
onBeforeUnmount(() => { clearTimeout(searchTimer); requestController?.abort() })
</script>

<style scoped>
.card-header, .header-actions, .advanced-header, .section-title-row, .repeat-title, .order-cell, .direction-row { display: flex; align-items: center; }
.card-header, .advanced-header, .section-title-row, .repeat-title { justify-content: space-between; }
.header-actions, .path-actions { display: flex; gap: 8px; }
.search-form { margin-bottom: 4px; }
.filter-count { display: inline-flex; min-width: 18px; height: 18px; margin-left: 5px; padding: 0 5px; align-items: center; justify-content: center; border-radius: 9px; color: #fff; background: var(--el-color-primary); font-size: 11px; }
.advanced-panel { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced-header { margin-bottom: 12px; font-weight: 600; }
.pagination { margin-top: 20px; }
.order-cell { justify-content: space-between; gap: 6px; }
.path-actions { flex-shrink: 0; }
.editor-body { min-height: 0; }
.form-section { margin-bottom: 18px; padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-fill-color-blank); }
.form-section h3 { margin: 0 0 16px; font-size: 16px; }
.form-section h4 { margin: 0; font-size: 15px; }
.section-title-row { margin-bottom: 12px; }
.section-title-row h3 { margin-bottom: 0; }
.repeat-card { margin-bottom: 12px; padding: 12px 12px 0; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-light); }
.interpreter-requirement-group { margin: 4px 0 16px; padding: 14px 14px 0; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-light); }
.requirement-group-title { margin-bottom: 12px; color: var(--el-text-color-regular); font-weight: 600; }
.repeat-title { margin-bottom: 8px; color: var(--el-text-color-regular); font-weight: 600; }
.direction-row { gap: 10px; margin-bottom: 10px; }
.direction-row .el-select { flex: 1; }
.direction-arrow { flex: 0 0 auto; color: var(--el-color-primary); font-size: 20px; font-weight: 700; }
.new-language-tag { float: right; margin-left: 8px; }
.remarks-form-item :deep(textarea) { min-height: 120px; }
:deep(.path-input) { display: flex; width: 100%; gap: 8px; }
:deep(.path-input .el-input) { flex: 1; }
</style>

<style>
.interpretation-advanced-popover, .interpretation-detail-popover, .interpretation-client-popover, .interpretation-interpreter-popover { max-width: calc(100vw - 32px) !important; }
.interpretation-client-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-interpreter-popover .interpreter-detail-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.interpretation-interpreter-popover .interpreter-detail-section-title { margin: 14px 0 8px; color: var(--el-text-color-primary); font-weight: 600; }
.interpretation-interpreter-popover .interpreter-detail-section-title:first-child { margin-top: 0; }
.interpretation-interpreter-popover .translator-profile { margin-bottom: 12px; }
.interpretation-interpreter-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-detail-popover .detail-content { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.interpretation-detail-popover .el-descriptions__content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
.interpretation-detail-popover .remarks-detail { min-height: 88px; white-space: pre-wrap; }
.interpretation-editor-dialog { display: flex; max-height: 90vh; flex-direction: column; overflow: hidden; }
.interpretation-editor-dialog .el-dialog__header,
.interpretation-editor-dialog .el-dialog__footer { flex: 0 0 auto; }
.interpretation-editor-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; padding-top: 12px; }
.interpretation-editor-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -3px 10px rgba(0, 0, 0, 0.04); }
@media (max-width: 768px) {
  .interpretation-card .search-form .el-form-item { display: flex; width: 100%; margin-right: 0; }
  .interpretation-card .search-form .el-input, .interpretation-card .search-form .el-select { width: 100% !important; }
  .direction-row { align-items: stretch; flex-direction: column; }
  .direction-arrow { text-align: center; transform: rotate(90deg); }
}
</style>
