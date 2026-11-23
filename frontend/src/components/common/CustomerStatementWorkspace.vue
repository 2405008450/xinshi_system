<template>
  <section ref="workspaceElement" class="statement-workspace" v-loading="loading||saving">
    <el-config-provider size="small">
    <SubClientFinancePreferences v-if="subClientId && settlementScope!=='special'" :sub-client-id="subClientId" :can-write="canWrite" hide-tax />
    <details v-if="$slots['customer-projects']" :open="settlementScope==='special'" class="customer-projects-panel">
      <summary>{{subClientId?'子客户项目':'客户项目'}}<span class="customer-projects-toggle">展开 / 收起</span></summary>
      <div class="workspace-toolbar"><span>项目月份（可合并查看）</span><el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" :disabled="lockMonth" aria-label="客户项目合并月份" placeholder="选择一个或多个月份" style="width:320px;max-width:100%" /></div>
      <div class="customer-projects-scroll" tabindex="0" aria-label="客户项目滚动区域"><slot name="customer-projects" :months="filters.months" :period-number="effectivePeriodNumber" :mode="mode" :reload="load" :selection-changed="queueGenerationStatus" /></div>
    </details>
    <slot name="client-actions" :reload="load" />
    <StatementGenerationProgressDialog v-if="progressPromptMonths.length && settlementScope!=='special' && state?.client_id"
      :client-id="String(state.client_id)" :months="progressPromptMonths" :manager-query="managerQuery"
      @close="closeGenerationProgress" />
    <AppForm data-auto-draft="off" class="workspace-generation" :model="filters" :disabled="deleteMode||focusMissing" inline @submit.prevent="importMonths">
      <el-form-item v-if="!lockMonth" label="账单月份"><el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" placeholder="选择一个或多个月份" style="width:210px;max-width:100%" /></el-form-item>
      <el-form-item v-if="settlementScope!=='special'" label="选择账期"><StatementPeriodSelect v-if="!periodNumber" v-model="selectedPeriodNumber" :months="filters.months||[]" :client-id="state?.client_id||clientId" :settlement-scope="settlementScope" /><span v-else>第 {{periodNumber}} 期</span></el-form-item>
      <el-form-item v-if="!clientId" label="生成范围"><el-radio-group v-model="filters.scope"><el-radio value="project">当前项目</el-radio><el-radio value="customer">该客户全部项目</el-radio></el-radio-group></el-form-item>
      <el-form-item v-if="!projectSelection"><el-checkbox v-model="filters.requiredOnly">仅导入需对账单项目</el-checkbox></el-form-item>
      <el-form-item>
        <el-button type="primary" :disabled="!canWrite||loading||saving||!filters.months?.length" @click="importMonths">{{generationLabel}}</el-button>
        <el-button v-if="state?.client_id" @click="generationVersionsVisible=true">查看历史版本</el-button>
      </el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-if="visiblePendingTasks.length||coverage.items.length||coverage.pending.length||coverageLoading||coverageError" class="statement-project-queues">
    <section class="statement-missing-projects" v-loading="coverageLoading">
      <h4>本月尚未体现的项目（{{coverage.items.length}} 个）</h4>
      <p v-if="coverage.pending.length">另有 {{coverage.pending.length}} 个项目已设为待入账，请在右上方待入账项目中按目标月份 / 账期查看。</p>
      <el-alert v-if="coverageError" :title="coverageError" type="warning" :closable="false"><el-button link @click="coverageRefresh++">重试</el-button></el-alert>
      <el-table :data="coverage.items" border max-height="240" empty-text="所选月份没有其他遗漏项目"><el-table-column label="拖入" width="55"><template #default="{row}"><button type="button" class="statement-queue-handle" :disabled="!canWrite||saving" :aria-label="`拖入未体现项目 ${row.order_no}`" @pointerdown.prevent.stop="startTaskPointer($event,[row.id],'project')">⠿</button></template></el-table-column><el-table-column prop="order_no" label="订单号" min-width="150" /><el-table-column prop="project_name" label="项目名称" min-width="170" show-overflow-tooltip /><el-table-column prop="month" label="账单月份" width="100" /></el-table>
    </section>
    <section v-if="visiblePendingTasks.length" class="statement-pending">
      <h4>待入账项目（{{visiblePendingTasks.length}} 个）</h4>
      <p>可按住 ⠿ 拖入下方对应月份 / 账期的对账单，也可在生成目标月份时自动纳入。</p>
      <el-table :data="visiblePendingTasks" border max-height="240" row-key="id"><el-table-column label="拖入" width="55"><template #default="{row}"><button type="button" class="statement-queue-handle" :disabled="!canWrite||saving" :aria-label="`拖入待入账项目 ${row.order_no}`" @pointerdown.prevent.stop="startTaskPointer($event,[row.id],'pending')">⠿</button></template></el-table-column><el-table-column prop="order_no" label="订单号" min-width="160" /><el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip /><el-table-column prop="month" label="目标月份" width="100" /><el-table-column label="目标账期" width="100"><template #default="{row}">{{row.period_number?`第 ${row.period_number} 期`:'未分账期'}}</template></el-table-column><el-table-column label="操作" width="160" fixed="right"><template #default="{row}"><el-button link :disabled="!canWrite||saving" @click="openSchedule([row.id])">调整月份</el-button><el-button link :disabled="!canWrite||saving" @click="cancelPending(row)">撤销</el-button></template></el-table-column></el-table>
    </section>
    </div>
    <div v-if="state" class="workspace-toolbar">
      <BatchDeleteToolbar v-if="canWrite&&(documents.length||deleteMode)" :active="deleteMode" :selected-count="selectedBoardIds.length" :loading="saving" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="deleteBoards" />
      <template v-if="!deleteMode">
      <el-select v-model="mode" aria-label="对账单订单显示方式" style="width:210px" @change="load"><el-option v-for="option in statementOrderDisplayOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select>
      <el-button v-if="!settlementScope" :disabled="!state.revision" @click="openHistory">记录 / 恢复</el-button>
      <el-dropdown v-if="!projectSelection" trigger="click" @command="reloadProjects"><el-button>更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :disabled="loading||saving" command="reload">重新加载</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
      <el-select v-model="scale" aria-label="对账单画布缩放" style="width:85px"><el-option v-for="value in [0.4,0.5,0.75,1]" :key="value" :value="value" :label="`${value*100}%`" /></el-select>
      <el-dropdown :disabled="downloading||!exportableBoardIds.length" trigger="click" @command="command=>exportStatements(command,exportableBoardIds)">
        <el-button :loading="downloading" :disabled="downloading||!exportableBoardIds.length">导出 / 打印 ▾</el-button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item command="excel">全部下载 Excel</el-dropdown-item><el-dropdown-item command="pdf">全部下载 PDF</el-dropdown-item><el-dropdown-item command="print" divided>全部打印</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
      </template>
    </div>
    <p v-if="!enforceStatementRequirement" class="statement-help workspace-hint">未勾选时使用全部筛选项目；修改仅影响对账单。</p>
    <div v-if="!deleteMode&&selected.length" class="selection-toolbar">
      <span>已选 {{selected.length}} 项项目</span><el-button @click="selected=[]">清空选择</el-button><el-button :disabled="!canWrite" @click="splitSelected">分拆至新对账单</el-button><el-button :disabled="!canWrite" @click="openSchedule(selected)">设为待入账</el-button><el-button :disabled="!canEditContent" @click="restoreTasks">恢复项目原始内容</el-button>
    </div>
    <el-empty v-if="state&&!documents.length" :description="focusBoardId?'该对账单已删除或不存在，可返回对账单管理查看记录':focusMonth?'该客户在此月份尚未生成对账单':'暂无对账单，请筛选或勾选下方项目后点击生成对账单'" />
    <div v-if="documents.length" ref="canvasScroll" class="statement-canvas-scroll">
      <div class="statement-canvas-space" :style="{width:`${canvasWidth*scale}px`,height:`${canvasHeight*scale}px`}">
        <div class="statement-canvas" :style="{width:`${canvasWidth}px`,height:`${canvasHeight}px`,transform:`scale(${scale})`}">
          <section v-for="board in documents" :key="board.id" :data-statement-board="board.id" class="statement-board" :class="{'statement-board--drop':taskDropBoard===board.id}" :style="boardStyle(board)"
            @dragover="overTasks($event,board)" @dragleave="leaveTasks($event)" @drop="dropTasks($event,board)"
            @pointerdown.capture="startBoardDrag($event,board)" @wheel="scrollBoard($event)">
            <div class="statement-board-header">
              <el-checkbox v-if="deleteMode" :model-value="selectedBoardIds.includes(board.id)" :aria-label="`选择对账单：${board.name}`" @update:model-value="value=>selectBoard(board.id,value)">选择</el-checkbox>
              <div class="statement-board-handle">⠿ {{board.name}}</div>
              <el-button v-if="settlementScope!=='special'" link :disabled="!canWrite||saving||loading||deleteMode" @pointerdown.stop @click="changeBoardPeriod(board)">{{board.period_number?`第 ${board.period_number} 期`:'未分账期'}} · 调整账期</el-button>
              <el-select :model-value="board.status||'active'" :aria-label="`对账单状态：${board.name}`" :disabled="!canWrite||saving||loading||deleteMode" style="width:90px;flex-shrink:0" @pointerdown.stop @change="status=>setBoardStatus(board,status)"><el-option value="active" label="有效" /><el-option value="void" label="废除" /></el-select>
              <button v-if="!deleteMode" type="button" class="statement-board-move" data-board-drag-handle
                :aria-label="`拖动整张对账单：${board.name}`" title="按住并拖动，移动整张对账单">⠿ 拖动整张</button>
              <span>项目 {{tasksFor(board.id).length}} 项</span>
              <el-button v-if="!deleteMode" link :aria-label="`最大化查看对账单：${board.name}`" @click="maximizedBoardId=board.id">最大化查看</el-button>
            </div>
            <el-alert v-if="statementBoardMonths(board).length>1" class="statement-merged-months" :title="`合并对账单 · 共 ${statementBoardMonths(board).length} 个月份：${statementBoardMonths(board).join('、')}`" type="info" :closable="false" />
            <details v-if="crossMonthStatementProjects(state.payload.tasks,board.id).length" class="statement-cross-month-projects">
              <summary>非本月项目归入本账单 · {{crossMonthStatementProjects(state.payload.tasks,board.id).length}} 个项目<span v-if="board.period_number"> · 第 {{board.period_number}} 期</span></summary>
              <el-table :data="crossMonthStatementProjects(state.payload.tasks,board.id)" size="small" border max-height="180"><el-table-column prop="orderNo" label="订单号" min-width="150" /><el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip /><el-table-column prop="sourceMonth" label="订单月份" width="100" /><el-table-column prop="billingMonth" label="归属账单月份" width="120" /></el-table>
            </details>
            <div v-if="!deleteMode" class="statement-board-actions">
              <template v-if="!standardStatement">
                <el-button type="primary" plain @click="openInline(board)">{{canEditContent?'放大 / 直接编辑':'放大查看'}}</el-button>
                <el-button :disabled="!canEditContent" @click="editHeader(board)">修改抬头 / 账户 / 印章</el-button>
              </template>
              <el-dropdown v-if="state.private_settings_available" trigger="click" :disabled="!canChangeCompany" @command="subject=>changeCompany(board,subject)">
                <el-button :disabled="!canChangeCompany">对账单主体：{{statementCompanyLabel(board)}} ▾</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="(name,key) in companySubjects" :key="key" :command="key">{{name}}{{key===board.statement.subject_key?'（当前）':''}}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-tooltip v-else content="公司主体与收款账户在正式 OA 中调整">
                <span class="statement-company-label">对账单主体：{{statementCompanyLabel(board)}}</span>
              </el-tooltip>
              <el-button :disabled="!canWrite||saving" @click="createBoard(board)">{{settlementScope==='special'?'新增对账单':'新增下一期对账单'}}</el-button>
              <template v-if="settlementScope==='special'"><el-tooltip content="有勾选添加勾选项目；未勾选添加上方客户项目的全部筛选结果。本单已有项目跳过，不改变财务主表。"><el-button :disabled="!canWrite||saving" @click="addSpecialProjects(board)">添加筛选／勾选项目</el-button></el-tooltip><el-button type="danger" plain :disabled="!canWrite||saving||!selected.some(id=>state.payload.tasks[id]?.board_id===board.id)" @click="removeSpecialProjects(board)">移除所选项目</el-button><el-button :disabled="!board.removed_projects?.length" @click="removedBoardId=board.id;removedVisible=true">已移除项目／恢复（{{board.removed_projects?.length||0}}）</el-button></template>
              <el-dropdown :disabled="downloading||!board.statement.rows.length" trigger="click" @command="command=>exportStatements(command,[board.id])">
                <el-button :disabled="downloading||!board.statement.rows.length">导出 / 打印 ▾</el-button>
                <template #dropdown><el-dropdown-menu>
                  <el-dropdown-item command="excel">下载 Excel</el-dropdown-item>
                  <el-dropdown-item command="pdf">下载 PDF</el-dropdown-item>
                  <el-dropdown-item command="print" divided>打印</el-dropdown-item>
                </el-dropdown-menu></template>
              </el-dropdown>
            </div>
            <div v-if="!deleteMode" class="statement-board-actions"><StatementFileDrag :client-id="state.client_id" :board-id="board.id" :revision="state.revision" :mode="mode" :settlement-scope="settlementScope" :name="`${board.statement.client_name}-${board.name}`" :disabled="saving||!board.statement.rows.length" :print-html="()=>filePrintHtml(board.id)" /></div>
            <p class="statement-system-meta">客户编号：{{board.statement.client_code||'—'}}（仅系统可见）</p>
            <div class="statement-board-content" @click="clickBoard($event,board)"><CustomerStatementPaper :can-open-order="settlementScope!=='special'" :statement="board.statement" :interactive="!deleteMode" :can-write="canWrite&&!saving&&!deleteMode" :can-edit="canEditContent&&!standardStatement" :can-edit-notes="canEditContent&&!saving&&!deleteMode" :selected="selected" @customer-note="(row,value)=>saveCustomerNote(board,row,value)" @task-pointer="startTaskPointer" @task-drag="startNativeTaskDrag" @dragend="stopTaskPointer" @select="selectTasks" @edit="openInline(board)" @open-order="openOrder" /></div>
          </section>
        </div>
      </div>
    </div>
    <div ref="printSource" class="statement-print-source" aria-hidden="true"><div v-for="board in documents" :key="board.id" :data-statement-print="board.id"><CustomerStatementPaper :statement="board.statement" /></div></div>

    <DraggableFormDialog :model-value="!!maximizedBoard" default-maximized class="statement-maximized-view"
      :title="`对账单 · ${maximizedBoard?.name||''}`" append-to-body destroy-on-close
      width="min(1100px, calc(100vw - 32px))" top="5vh" @update:model-value="value=>{if(!value)maximizedBoardId=''}">
      <CustomerStatementPaper :can-open-order="settlementScope!=='special'" v-if="maximizedBoard" :statement="maximizedBoard.statement"
        :interactive="true" :can-write="false" :can-edit="false" :selected="[]"
        @open-order="openOrder" />
      <template #footer><el-button @click="maximizedBoardId=''">返回画布</el-button></template>
    </DraggableFormDialog>
    <TranslationProjectEditor v-if="orderEditor" :key="`${orderEditor.rootId}:${orderEditor.orderNo}`" editor-only embedded :editor-project-id="orderEditor.rootId" :editor-order-no="orderEditor.orderNo" @editor-closed="orderEditor=null" />
    <CustomerStatementInlineEditor v-model="inlineVisible" :board="inlineBoard" :can-write="canEditContent" :saving="saving" :error="error" @save="saveInline" @open-order="openOrder" />
    <CustomerStatementGenerationVersions v-if="state?.client_id" v-model="generationVersionsVisible"
      :client-id="state.client_id" :revision="state.revision" :mode="mode" :can-write="canEditContent" :settlement-scope="settlementScope" @changed="onHistoricalVersionChanged" />
    <DraggableFormDialog v-model="editVisible" class="statement-edit-dialog" data-auto-draft="off" width="min(880px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="closeEdit">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editType==='row'?'修改对账单项目':'修改对账单内容'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editBody"><AppForm ref="editForm" :model="draft" label-position="top" :disabled="saving">
        <el-form-item v-if="editType==='row'" label="订单号"><ReadonlyField :model-value="editingRow?.order_no" source="auto" /></el-form-item>
        <div class="statement-edit-grid"><el-form-item v-for="field in editingFields" :key="field.key" :label="field.label" :prop="field.key" :rules="field.required?[{required:true,message:`请填写${field.label}`,trigger:'change'}]:[]">
          <template v-if="field.key==='stamp_image'"><img :src="draft.stamp_image" class="statement-edit-stamp" alt="印章预览" /><input type="file" accept="image/png,image/jpeg,image/webp" @change="selectStamp" /></template>
          <el-switch v-else-if="field.key==='tax_included'" v-model="draft.tax_included" active-text="含税" inactive-text="不含税" />
          <el-date-picker v-else-if="field.key==='received_date'" v-model="draft[field.key]" type="date" value-format="YYYY-MM-DD" />
          <el-input v-else v-model="draft[field.key]" :type="field.multiline?'textarea':'text'" :rows="field.multiline?3:undefined" :maxlength="5000" />
        </el-form-item></div>
        <p v-if="editType==='row' && !fixedEditingRow" class="statement-help">小计可独立调整。修改数量或单价后，可点击下方按钮按计价数量重新计算。</p>
        <el-button v-if="editType==='row' && !fixedEditingRow" @click="recalculate">按数量 × 单价 ÷ 计价数量重算小计</el-button>
      </AppForm></div>
      <template #footer><el-button :disabled="saving" @click="closeEdit()">取消</el-button><el-button type="primary" :loading="saving" @click="saveEdit">确认修改…</el-button></template>
    </DraggableFormDialog>


    <DraggableFormDialog v-model="scheduleVisible" title="设置待入账月份" class="statement-edit-dialog" data-auto-draft="off" width="min(600px, calc(100vw - 32px))" top="8vh" append-to-body>
      <AppForm ref="scheduleForm" :model="scheduleDraft" label-position="top">
        <el-form-item label="所选项目">{{scheduleIds.length}} 项，包含全部收费明细。目标月份尚未生成对账单也可以设置。</el-form-item>
        <el-form-item label="目前所在账期">
          <div class="statement-schedule-periods" role="status">
            <div v-for="label in scheduleCurrentPeriods" :key="label">{{label}}</div>
            <span v-if="schedulePeriodsLoading">正在读取账期…</span>
          </div>
        </el-form-item>
        <el-form-item label="目标账单月份" prop="month" :rules="[{required:true,message:'请选择目标月份',trigger:'change'}]">
          <el-date-picker v-model="scheduleDraft.month" type="month" value-format="YYYY-MM" />
        </el-form-item>
        <el-form-item label="具体账期" prop="boardId">
          <el-select v-model="scheduleDraft.boardId" aria-label="待入账具体账期" placeholder="自动匹配账期" style="width:100%">
            <el-option value="" label="自动匹配账期" />
            <el-option v-for="board in scheduleBoardOptions" :key="board.id" :value="board.id" :label="`${board.period_number?`第 ${board.period_number} 期`:'未分账期'} · ${board.name}`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="scheduleDraft.month" label="目标账期">
          <div class="statement-schedule-periods" role="status">
            <div v-for="label in scheduleTargetPeriods" :key="label">{{label}}</div>
            <span v-if="schedulePeriodsLoading">正在读取账期…</span>
          </div>
        </el-form-item>
        <el-alert v-if="schedulePeriodsError" :title="schedulePeriodsError" type="warning" :closable="false">
          <el-button link type="primary" @click="schedulePeriodsRefresh++">重新读取账期</el-button>
        </el-alert>
      </AppForm>
      <template #footer><el-button @click="scheduleVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveSchedule">确认并记录</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="removedVisible" title="已移除项目／恢复" class="statement-edit-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body>
      <el-alert title="恢复仅将所选项目及其原有内容放回本单，保留此后其他修改；财务主表不变。本单已重新添加的项目不能重复恢复。" type="info" :closable="false" />
      <el-table :data="removedProjects" row-key="id" border max-height="460"><el-table-column label="订单号" min-width="150"><template #default="{row}">{{row.task.rows[0].order_no}}</template></el-table-column><el-table-column label="项目名称" min-width="200"><template #default="{row}">{{row.task.rows[0].project_name}}</template></el-table-column><el-table-column prop="actor_name" label="移除人" width="110" /><el-table-column label="移除时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.removed_at)}}</template></el-table-column><el-table-column label="操作" fixed="right" width="90"><template #default="{row}"><el-button link type="primary" :disabled="!canWrite||saving" @click="restoreRemovedProject(row)">恢复项目</el-button></template></el-table-column></el-table>
      <template #footer><el-button @click="removedVisible=false">关闭</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="auditVisible" title="对账单调整前后" class="statement-edit-dialog" data-auto-draft="off" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body>
      <div v-loading="auditLoading"><el-alert v-if="auditError" :title="auditError" type="error" :closable="false" /><template v-if="auditEntry"><p>{{auditEntry.action}} · 调整人：{{auditEntry.actor_name}} · {{formatBusinessDateTime(auditEntry.created_at)}}</p><StatementAuditChanges :before="auditEntry.before" :after="auditEntry.after" :labels="historyLabels" /></template></div>
      <template #footer><el-button @click="auditVisible=false">关闭</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="historyVisible" title="对账单修改记录" class="statement-edit-dialog" data-auto-draft="off" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body>
      <el-alert title="恢复到某次修改前，会撤销该次及其之后的编排与内容修改，并新增一条恢复记录。" type="info" :closable="false" />
      <el-table v-loading="historyLoading" :data="history.items" row-key="id"><el-table-column prop="revision" label="版本" width="70" /><el-table-column prop="actor_name" label="操作人" width="100" /><el-table-column label="时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column><el-table-column prop="action" label="操作" width="170" /><el-table-column label="变更内容" min-width="300"><template #default="{row}"><StatementAuditChanges :changes="row.changes" :labels="historyLabels" :boards="state?.payload?.boards" :tasks="state?.payload?.tasks" /></template></el-table-column><el-table-column label="调整前后" width="120"><template #default="{row}"><el-button link @click="viewAudit(row)">查看前后</el-button></template></el-table-column><el-table-column label="恢复" width="170" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="!canWrite||!row.restorable||saving" @click="restoreHistory(row)">恢复到本次修改前</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="historyPage" :page-size="20" :total="history.total" layout="total, prev, pager, next" @current-change="loadHistory" />
      <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
    </el-config-provider>
  </section>
</template>
<script setup>
import StatementFileDrag from './StatementFileDrag.vue'
import StatementAuditChanges from './StatementAuditChanges.vue'
import {computed,defineAsyncComponent,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import BatchDeleteToolbar from './BatchDeleteToolbar.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import ReadonlyField from './ReadonlyField.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import CustomerStatementInlineEditor from './CustomerStatementInlineEditor.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getStatementWorkspace,getClientStatementWorkspace,importStatementMonths,changeStatementWorkspace,getPendingStatementPeriods,getStatementWorkspaceHistory,getStatementWorkspaceHistoryEntry,exportStatementWorkspace,exportStatementWorkspacePdf,getStatementGenerationStatus} from '@/api/customerStatements'
import {getStatementProjectCoverage} from '@/api/customerStatements'
import CustomerStatementGenerationVersions from './CustomerStatementGenerationVersions.vue'
import SubClientFinancePreferences from './SubClientFinancePreferences.vue'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {statementOrderDisplayOptions} from '@/utils/statementOrderDisplay'
import {statementBoardMonths,statementBoardMatchesMonths,pendingStatementTasksInScope} from '@/utils/statementBoardMonths'
import {crossMonthStatementProjects} from '@/utils/statementCrossMonthProjects'
import StatementPeriodSelect from './StatementPeriodSelect.vue'
import {statementFileName,isFixedStatementRow} from '@/utils/statementFormatting'
import {statementPrintStyles} from '@/utils/customerStatementPrint'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
const TranslationProjectEditor=defineAsyncComponent(()=>import('@/views/project/translation/ProjectDetails.vue'))
const orderEditor=ref(null)
function openOrder(row){if(!row.root_id)return ElMessage.warning('该订单缺少项目关联，无法打开');orderEditor.value={rootId:row.root_id,orderNo:row.order_no}}
import {connectInvoiceParties,notifyInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import StatementGenerationProgressDialog from './StatementGenerationProgressDialog.vue'
const emit=defineEmits(['loaded','show-boards'])
const props=defineProps({periodNumber:Number,settlementScope:String,subClientId:String,lockMonth:Boolean,enforceStatementRequirement:Boolean,projectSelection:Function,projectReload:Function,managerQuery:{type:Object,default:()=>({})},visibleBoardIds:{type:Array,default:()=>[]},focusMonth:{type:String,default:''},focusBoardId:{type:String,default:''},projectId:{type:[String,Number],default:''},clientId:{type:[String,Number],default:''},billingMonth:String})
const canWrite=hasPermission('projects:write')
const progressPromptMonths=ref([])
function closeGenerationProgress(){
  progressPromptMonths.value=[]
  window.dispatchEvent(new CustomEvent('translation-statements-changed',{detail:{clientId:state.value?.client_id}}))
}

const standardStatement=computed(()=>props.settlementScope==='standard')
function scrollBoard(event){
  if(event.ctrlKey||event.shiftKey||Math.abs(event.deltaX)>Math.abs(event.deltaY))return
  const target=event.currentTarget.querySelector('.statement-board-content')
  if(!target)return
  // 单据上方的工具栏也归本单滚动，滚到底后不把滚轮传给外层页面。
  const nested=event.target.closest('textarea,.el-select-dropdown__wrap,.el-table__body-wrapper .el-scrollbar__wrap')
  if(nested&&nested.scrollHeight>nested.clientHeight)return
  event.preventDefault();event.stopPropagation()
  const unit=event.deltaMode===1?16:event.deltaMode===2?target.clientHeight:1
  target.scrollTop+=event.deltaY*unit/(scale.value||1)
}
const companySubjects={guangzhou:'广州总公司',shenzhen:'深圳分公司',shanghai:'上海分公司'}
const statementCompanyLabel=board=>companySubjects[board.statement.subject_key]||board.statement.company||'待设置'
const canEditContent=computed(()=>canWrite&&state.value?.capabilities?.edit_content===true)
const canChangeCompany=computed(()=>canEditContent.value&&state.value?.private_settings_available&&!saving.value)
const filters=reactive({months:[props.billingMonth||businessDateTimeInputValue().slice(0,7)],scope:'customer',requiredOnly:true})
const selectedPeriodNumber=ref()
const effectivePeriodNumber=computed(()=>props.settlementScope==='special'?undefined:props.periodNumber||selectedPeriodNumber.value)
watch(()=>JSON.stringify(filters.months),()=>{selectedPeriodNumber.value=undefined})
const modeStorageKey=`customer-statement-order-display:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const savedMode=localStorage.getItem(modeStorageKey)
const state=ref(null),loading=ref(false),saving=ref(false),error=ref(''),mode=ref(statementOrderDisplayOptions.some(option=>option.value===savedMode)?savedMode:'children'),scale=ref(.75),selected=ref([]),positions=reactive({})
watch(mode,value=>localStorage.setItem(modeStorageKey,value))
const deleteMode=ref(false),selectedBoardIds=ref([])
function enterDeleteMode(){selected.value=[];selectedBoardIds.value=[];deleteMode.value=true}
function exitDeleteMode(){deleteMode.value=false;selectedBoardIds.value=[]}
function selectBoard(id,checked){selectedBoardIds.value=checked?[...new Set([...selectedBoardIds.value,id])]:selectedBoardIds.value.filter(value=>value!==id)}
const visiblePendingTasks=computed(()=>pendingStatementTasksInScope(state.value?.pending_tasks,{
  months:props.lockMonth&&props.billingMonth?[props.billingMonth]:props.focusMonth?[props.focusMonth]:filters.months,
  periodNumber:effectivePeriodNumber.value,subClientId:props.subClientId,settlementScope:props.settlementScope,
}))
const documents=computed(()=>{const all=(state.value?.documents||[]).filter(board=>board.status!=='void'&&(!props.subClientId||props.settlementScope==='special'||board.sub_client_id===props.subClientId||board.id===props.focusBoardId) && (!props.visibleBoardIds.length||props.visibleBoardIds.includes(board.id)) && (!effectivePeriodNumber.value||board.period_number===effectivePeriodNumber.value&&(!props.periodNumber||board.period_month===props.billingMonth)));if(props.focusBoardId)return all.filter(board=>board.id===props.focusBoardId);const months=props.lockMonth&&props.billingMonth?[props.billingMonth]:props.focusMonth?[props.focusMonth]:filters.months;return all.filter(board=>statementBoardMatchesMonths(board,months))})
const coverage=reactive({items:[],pending:[]}),coverageLoading=ref(false),coverageError=ref(''),coverageRefresh=ref(0)
watch(()=>[state.value?.client_id,state.value?.revision,JSON.stringify(filters.months),effectivePeriodNumber.value,props.subClientId,props.settlementScope,JSON.stringify(props.managerQuery),coverageRefresh.value],async(_,__,onCleanup)=>{
  const request=new AbortController();let timer
  onCleanup(()=>{request.abort();clearTimeout(timer)})
  coverage.items=[];coverage.pending=[];coverageError.value='';coverageLoading.value=false
  if(!state.value?.client_id||!filters.months?.length||!documents.value.length)return
  coverageLoading.value=true
  timer=setTimeout(async()=>{try{const query=props.managerQuery||{};const data=await getStatementProjectCoverage(state.value.client_id,{months:[...filters.months],period_number:effectivePeriodNumber.value,sub_client_id:props.subClientId,manager_ids:query.manager_ids||[],only_mine:!!query.only_mine,client_manager:query.client_manager},props.settlementScope,request.signal);if(!request.signal.aborted)Object.assign(coverage,data)}catch(e){if(!request.signal.aborted)coverageError.value=getLocalizedErrorMessage(e,'未体现项目检查失败')}finally{if(!request.signal.aborted)coverageLoading.value=false}},400)
},{immediate:true})
watch(()=>documents.value.length,count=>{scale.value=count>=3?.4:count===2?.5:.75})
const focusMissing=computed(()=>!!(props.focusBoardId||props.focusMonth)&&!!state.value&&!documents.value.length)
watch(()=>[props.billingMonth,props.periodNumber],([month])=>{if(month)filters.months=[month]})
const position=board=>{if(positions[board.id])return positions[board.id];if(documents.value.length!==(state.value?.documents||[]).length){const index=documents.value.findIndex(item=>item.id===board.id);return {x:(index%3)*980,y:Math.floor(index/3)*900}}return {x:board.x||0,y:board.y||0}}
const canvasWidth=computed(()=>Math.max(980,...documents.value.map(board=>position(board).x+980)))
const canvasHeight=computed(()=>Math.max(740,...documents.value.map(board=>position(board).y+740)))
const activeBoardId=ref('')
const boardStyle=board=>({left:`${position(board).x}px`,top:`${position(board).y}px`,zIndex:activeBoardId.value===board.id?1:0})
const tasksFor=boardId=>Object.values(state.value?.payload.tasks||{}).filter(task=>task.board_id===boardId)
const canvasScroll=ref()
const maximizedBoardId=ref('')
const maximizedBoard=computed(()=>documents.value.find(board=>board.id===maximizedBoardId.value))
let sequence=0,controller,disposed=false,drag=null,suppressBoardClickUntil=0
const frames=new Set()
const printSource=ref(),downloading=ref(false)
function apply(data){emit('loaded',data);exitDeleteMode();state.value=data;selected.value=[];for(const key of Object.keys(positions))delete positions[key]}
function onHistoricalVersionChanged(data){apply(data);window.dispatchEvent(new CustomEvent('translation-statements-changed'))}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await (props.clientId?getClientStatementWorkspace(props.clientId,mode.value,{signal:controller.signal,params:{settlement_scope:props.settlementScope}}):getStatementWorkspace(props.projectId,mode.value,{signal:controller.signal}));if(seq===sequence)apply(data)}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'对账单加载失败')}finally{if(seq===sequence)loading.value=false}}
async function reloadProjects(){if(props.projectReload&&await props.projectReload()===false)return;await load()}
async function confirm(text,title='确认对账单修改'){try{await ElMessageBox.confirm(text,title,{type:'warning',confirmButtonText:'确认并记录',cancelButtonText:'取消'});return true}catch{return false}}
async function mutate(action,data,text,confirmAction=()=>confirm(text)){if(saving.value||loading.value||!state.value)return false;const revision=state.value.revision;if(!await confirmAction()||disposed)return false;saving.value=true;error.value='';try{const result=await changeStatementWorkspace(state.value.client_id,{revision,action,data,confirmed:true},mode.value,props.settlementScope);if(!disposed){apply(result);window.dispatchEvent(new CustomEvent('translation-statements-changed'))}ElMessage.success('已保存并记录修改历史');return true}catch(e){if(e.code==='ERR_CANCELED'){if(action==='edit_customer_note'&&!disposed)await load();return false}error.value=getLocalizedErrorMessage(e,'对账单修改失败');return false}finally{saving.value=false}}
async function deleteBoards(){
  const ids=[...selectedBoardIds.value];if(!ids.length||!canWrite)return
  const names=documents.value.filter(board=>ids.includes(board.id)).map(board=>board.name).join('、')
  const text=`删除 ${ids.length} 份对账单：${names}？所含项目从当前对账单中移除，可按月份重新生成。删除前的完整内容、操作人和时间会保留，可从修改记录恢复。`
  const confirmBatch=ids.length>1?async()=>{try{await ElMessageBox.prompt(text+'请输入“删除”确认。','批量删除对账单',{type:'warning',confirmButtonText:'确认删除并记录',cancelButtonText:'取消',inputValidator:value=>value==='删除'||'请输入“删除”确认'});return true}catch{return false}}:undefined
  await mutate('delete_boards',{board_ids:ids,...(ids.length>1?{confirmation:'删除'}:{})},text,confirmBatch)
}
const generationExists=ref(false),generationVersionsVisible=ref(false)
const generationLabel=computed(()=>`${generationExists.value?'再次生成':'生成'}对账单`)
let generationTimer,generationRequest
function generationPayload(orderIds){
  return {
    ...(props.clientId?{client_id:props.clientId}:{project_id:props.projectId}),
    months:[...filters.months],period_number:effectivePeriodNumber.value,settlement_scope:props.settlementScope,sub_client_id:props.subClientId,
    order_ids:orderIds,required_only:props.enforceStatementRequirement||(orderIds===undefined&&filters.requiredOnly),
    scope:props.clientId?'customer':filters.scope,revision:state.value.revision,
    board_id:specialTarget.value||props.focusBoardId||(props.focusMonth?documents.value[0]?.id:null)||null,
  }
}
function queueGenerationStatus(){
  clearTimeout(generationTimer)
  generationRequest?.abort()
  generationExists.value=false
  if(!state.value?.client_id||!filters.months?.length)return
  generationTimer=setTimeout(async()=>{
    const request=generationRequest=new AbortController()
    try{
      const orderIds=await props.projectSelection?.({flush:false,signal:request.signal})
      if(request.signal.aborted||props.projectSelection&&!orderIds)return
      const result=await getStatementGenerationStatus(state.value.client_id,generationPayload(orderIds),{signal:request.signal})
      if(!request.signal.aborted)generationExists.value=result.exists
    }catch{if(!request.signal.aborted)generationExists.value=false}
  },400)
}
watch(()=>[state.value?.revision,filters.months,filters.scope,filters.requiredOnly,effectivePeriodNumber.value,props.settlementScope],
  queueGenerationStatus,{deep:true,flush:'post'})
async function importMonths(){
  if(!canWrite||saving.value||!filters.months?.length||!state.value)return
  if(effectivePeriodNumber.value&&filters.months.length!==1){ElMessage.warning('生成指定账期时请选择一个账单月份；合并多月份查看可选择全部期次');return}
  let orderIds
  try{
    orderIds=await props.projectSelection?.()
    if(props.projectSelection&&!orderIds)throw new Error('项目表尚未加载完成')
  }catch(e){error.value=getLocalizedErrorMessage(e,'读取项目范围失败');return}
  const payload=generationPayload(orderIds)
  const selection=orderIds?`所选或筛选出的 ${orderIds.length} 个订单`:'范围内的项目'
  if(!await confirm(`按 ${payload.months.join('、')} 的${selection}生成一个版本，并纳入对应的待入账项目。`,generationLabel.value))return
  saving.value=true
  try{
    const data=await importStatementMonths({...payload,confirmed:true},mode.value)
    if(!disposed){
      apply(data)
      // 普通项目可能因自动标记为“需对账单”移到另一栏，先保留进度提示，关闭后再刷新客户分组。
      if(props.settlementScope==='special')window.dispatchEvent(new CustomEvent('translation-statements-changed'))
    }
    ElMessage.success(data.generation_saved?`已保存第 ${data.revision} 版，可在「生成版本」查看`:`新增 ${data.imported} 项，已有 ${data.existing} 项`)
    if(!disposed && props.settlementScope!=='special')progressPromptMonths.value=[...payload.months]

  }catch(e){error.value=getLocalizedErrorMessage(e,'生成对账单失败')}
  finally{saving.value=false}
}
async function splitSelected(){let name;try{name=(await ElMessageBox.prompt('填写分拆后的对账单名称；保留项目内容与月份。','分拆对账单',{inputValidator:value=>!!value?.trim()||'请填写名称'})).value}catch{return}const before=new Set(state.value.documents.map(board=>board.id));const shown=documents.value.map(board=>board.id);if(await mutate('split_board',{task_ids:[...selected.value],name},`将所选 ${selected.value.length} 项项目分拆为“${name}”，保留原内容并记录前后归属？`)){const added=state.value.documents.filter(board=>!before.has(board.id)).map(board=>board.id);emit('show-boards',[...shown,...added])}}

const specialTarget=ref('')
const removedVisible=ref(false),removedBoardId=ref('')
const removedProjects=computed(()=>state.value?.payload.boards.find(board=>board.id===removedBoardId.value)?.removed_projects||[])
async function restoreRemovedProject(row){await mutate('restore_special_projects',{board_id:removedBoardId.value,removed_project_ids:[row.id]},`将 ${row.task.rows[0].order_no} 恢复到本特殊结算对账单，保留之后其他修改？`)}
async function addSpecialProjects(board){specialTarget.value=board.id;try{await importMonths()}finally{specialTarget.value=''}}
async function removeSpecialProjects(board){const ids=selected.value.filter(id=>state.value.payload.tasks[id]?.board_id===board.id);await mutate('remove_special_projects',{board_id:board.id,task_ids:ids},`仅从本特殊结算单移除 ${ids.length} 个项目，可在本单「已移除项目／恢复」逐项恢复，保留修改记录，财务主表不变。`)}
async function createBoard(board){
  if(props.settlementScope==='special'){await mutate('create_board',{name:`特殊结算对账单 ${documents.value.length+1}`,board_id:board.id},'新增一份独立特殊结算对账单，同月可有多份有效单，可重复纳入同一项目。');return}
  const months=new Set(statementBoardMonths(board))
  const peers=(state.value.documents||[]).filter(item=>item.status!=='void'&&(item.sub_client_id||null)===(board.sub_client_id||null)&&(item.settlement_scope||'standard')===(board.settlement_scope||'standard')&&statementBoardMonths(item).some(month=>months.has(month)))
  const next=Math.max(1,...peers.map(item=>item.period_number||0))+1
  await mutate('create_board',{name:`${[...months].join('、')} · 第 ${next} 期对账单`,board_id:board.id},`新增第 ${next} 期对账单；原单未分账期时标为第一期。可将项目移动到新账期，保留修改记录。`)
}
async function changeBoardPeriod(board){
  let value
  try{value=(await ElMessageBox.prompt('填写账期序号。同月份的有效对账单不能使用相同账期。','调整对账单账期',{inputValue:String(board.period_number||1),inputValidator:text=>/^[1-9]\d*$/.test(text||'')&&Number.isSafeInteger(Number(text))||'请输入大于零的整数'})).value}catch{return}
  await mutate('set_board_period',{board_id:board.id,period_number:Number(value)},`将本对账单调整为第 ${value} 期？项目保留在本单，调整前后均保留记录。`)
}
function selectTasks(ids,checked){selected.value=checked?[...new Set([...selected.value,...ids])]:selected.value.filter(id=>!ids.includes(id))}
const auditVisible=ref(false),auditLoading=ref(false),auditError=ref(''),auditEntry=ref(null)
async function viewAudit(row){auditVisible.value=true;auditLoading.value=true;auditEntry.value=null;auditError.value='';try{auditEntry.value=await getStatementWorkspaceHistoryEntry(state.value.client_id,row.id)}catch(e){auditError.value=getLocalizedErrorMessage(e,'记录加载失败')}finally{auditLoading.value=false}}
const scheduleVisible=ref(false),scheduleForm=ref(),scheduleIds=ref([]),scheduleDraft=reactive({month:'',boardId:''})
const scheduleBoardOptions=computed(()=>(state.value?.documents||[]).filter(board=>
  board.status!=='void'&&(board.period_month?board.period_month===scheduleDraft.month:(board.statement.months||[]).includes(scheduleDraft.month))&&
  scheduleIds.value.every(id=>(state.value.payload.tasks[id]?.rows[0]?.sub_client_id||null)===(board.sub_client_id||null))))
watch(()=>scheduleDraft.month,()=>{if(!scheduleBoardOptions.value.some(board=>board.id===scheduleDraft.boardId))scheduleDraft.boardId=''})
const schedulePeriods=ref([]),schedulePeriodsLoading=ref(false),schedulePeriodsError=ref(''),schedulePeriodsRefresh=ref(0)
function schedulePeriodLabels(labels){
  const counts=new Map()
  for(const label of labels)counts.set(label,(counts.get(label)||0)+1)
  return [...counts].map(([label,count])=>counts.size>1?`${label}（${count} 项）`:label)
}
function periodLabel(month,number,needsPeriod){
  return `${month} · ${number?`第 ${number} 期`:needsPeriod?'待指定账期':'未分账期'}`
}
const scheduleCurrentPeriods=computed(()=>schedulePeriodLabels(schedulePeriods.value.map(row=>{
  const label=periodLabel(row.current_month,row.current_period,row.current_needs_period)
  return row.current_pending?`${label}（待入账）`:label
})))
const scheduleTargetPeriods=computed(()=>{const board=scheduleBoardOptions.value.find(board=>board.id===scheduleDraft.boardId);return board?[`${periodLabel(scheduleDraft.month,board.period_number,false)} · ${board.name}`]:schedulePeriodLabels(schedulePeriods.value.map(row=>
  periodLabel(scheduleDraft.month,row.target_period,row.target_needs_period)))})
watch(()=>[scheduleVisible.value,scheduleDraft.month,scheduleIds.value,state.value?.client_id,props.settlementScope,schedulePeriodsRefresh.value],
  async ([visible,month,ids,clientId,scope],_,onCleanup)=>{
    schedulePeriods.value=[]
    schedulePeriodsError.value=''
    schedulePeriodsLoading.value=false
    if(!visible||!clientId||!ids.length)return
    const previewMonth=month||state.value.payload.tasks[ids[0]]?.month
    if(!previewMonth)return
    const request=new AbortController()
    onCleanup(()=>request.abort())
    schedulePeriodsLoading.value=true
    try{
      const result=await getPendingStatementPeriods(clientId,{month:previewMonth,task_ids:ids},scope,request.signal)
      if(!request.signal.aborted)schedulePeriods.value=result
    }catch(error){
      if(!request.signal.aborted)schedulePeriodsError.value=getLocalizedErrorMessage(error,'账期读取失败')
    }finally{
      if(!request.signal.aborted)schedulePeriodsLoading.value=false
    }
  })
function openSchedule(ids){scheduleIds.value=[...new Set(ids)];scheduleDraft.month=state.value.payload.tasks[ids[0]]?.month||filters.months[0];scheduleDraft.boardId=state.value.payload.tasks[ids[0]]?.pending_target_board_id||'';scheduleVisible.value=true}
async function saveSchedule(){if(!await scheduleForm.value?.validate().catch(()=>false))return;const target=scheduleBoardOptions.value.find(board=>board.id===scheduleDraft.boardId);if(await mutate('schedule_tasks',{task_ids:scheduleIds.value,month:scheduleDraft.month,board_id:target?.id||null},`将 ${scheduleIds.value.length} 项项目设为 ${scheduleDraft.month}${target?` · ${target.period_number?`第 ${target.period_number} 期`:'未分账期'}（${target.name}）`:''} 待入账，从原对账单移出；生成目标月份时自动纳入，并保留调整记录。`))scheduleVisible.value=false}
async function cancelPending(row){await mutate('cancel_pending',{task_ids:[row.id]},`撤销 ${row.order_no} 的待入账调整，恢复至调整前的对账单和月份？`)}
async function restoreTasks(){await mutate('restore_task',{task_ids:[...selected.value]},`恢复所选 ${selected.value.length} 项项目首次导入时的内容、月份及对账单归属。`)}
async function setBoardStatus(board,status){if(!canWrite)return;await mutate('set_board_status',{board_id:board.id,status},status==='void'?`废除“${board.name}”并移入历史版本？保留完整内容和调整记录。`:`将“${board.name}”设为有效？同月份、同账期的其他有效对账单会自动废除并移入历史版本。`)}
const workspaceElement=ref(),taskDropBoard=ref('')
let taskPointer=null,nativeTaskIds=[]
function validTaskIds(ids,kind='task'){return Array.isArray(ids)&&ids.length&&ids.every(id=>kind==='project'?coverage.items.some(row=>row.id===id):state.value?.payload.tasks[id]&&(kind==='pending'?state.value.payload.tasks[id].pending:!state.value.payload.tasks[id].pending))}
function taskTarget(event){const element=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-statement-board]');return element&&workspaceElement.value?.contains(element)?documents.value.find(board=>board.id===element.dataset.statementBoard):null}
function stopTaskPointer(){window.removeEventListener('pointermove',moveTaskPointer);window.removeEventListener('pointerup',endTaskPointer);window.removeEventListener('pointercancel',stopTaskPointer);taskPointer=null;nativeTaskIds=[];taskDropBoard.value=''}
function startTaskPointer(event,ids,kind='task'){
  if(!canWrite||saving.value||loading.value||deleteMode.value||event.button!==0||!validTaskIds(ids,kind))return
  stopTaskPointer();taskPointer={ids:[...ids],kind,x:event.clientX,y:event.clientY,pointerId:event.pointerId,moved:false}
  window.addEventListener('pointermove',moveTaskPointer);window.addEventListener('pointerup',endTaskPointer);window.addEventListener('pointercancel',stopTaskPointer,{once:true})
}
function moveTaskPointer(event){
  if(!taskPointer||event.pointerId!==taskPointer.pointerId)return
  if(Math.hypot(event.clientX-taskPointer.x,event.clientY-taskPointer.y)<5&&!taskPointer.moved)return
  taskPointer.moved=true;event.preventDefault();suppressBoardClickUntil=Date.now()+500
  const board=taskTarget(event)
  taskDropBoard.value=board&&(taskPointer.kind==='project'||taskPointer.ids.some(id=>state.value.payload.tasks[id].board_id!==board.id))?board.id:''
  const scroll=canvasScroll.value,bounds=scroll?.getBoundingClientRect()
  if(bounds)scroll.scrollBy(event.clientX>bounds.right-30?20:event.clientX<bounds.left+30?-20:0,event.clientY>bounds.bottom-30?20:event.clientY<bounds.top+30?-20:0)
}
function endTaskPointer(event){if(!taskPointer||event.pointerId!==taskPointer.pointerId)return;const pointer=taskPointer,board=taskTarget(event);stopTaskPointer();if(pointer.moved&&board){suppressBoardClickUntil=Date.now()+500;void dropQueueItems(pointer.ids,board,pointer.kind)}}
async function dropQueueItems(ids,board,kind){
  if(!validTaskIds(ids,kind)||!canWrite||saving.value||loading.value||deleteMode.value)return
  if(kind==='task')return moveTasksToBoard(ids,board)
  if(kind==='pending')return mutate('accept_pending',{task_ids:ids,board_id:board.id},`将 ${ids.length} 个待入账项目纳入“${board.name}”？保留原内容，并记录归属。`)
  const row=coverage.items.find(item=>item.id===ids[0]);if(!row||!statementBoardMonths(board).includes(row.month)){ElMessage.warning('项目与目标对账单月份不匹配');return}
  const revision=state.value.revision
  if(!await confirm(`将 ${ids.length} 个尚未体现的项目纳入“${board.name}”？`))return
  saving.value=true
  try{const data=await importStatementMonths({client_id:state.value.client_id,scope:'customer',months:[row.month],board_id:board.id,order_ids:ids,revision,confirmed:true,required_only:false,settlement_scope:props.settlementScope,sub_client_id:props.subClientId,period_number:board.period_number||undefined},mode.value);if(!disposed)apply(data);ElMessage.success('项目已纳入对账单');window.dispatchEvent(new CustomEvent('translation-statements-changed'))}catch(e){error.value=getLocalizedErrorMessage(e,'项目纳入失败')}finally{saving.value=false}
}
function startNativeTaskDrag(ids){stopTaskPointer();if(validTaskIds(ids))nativeTaskIds=[...ids]}
function overTasks(event,board){if(!canWrite||saving.value||loading.value||deleteMode.value||!nativeTaskIds.length)return;event.preventDefault();event.stopPropagation();event.dataTransfer.dropEffect='move';taskDropBoard.value=nativeTaskIds.some(id=>state.value.payload.tasks[id].board_id!==board.id)?board.id:''}
function leaveTasks(event){if(!event.currentTarget.contains(event.relatedTarget))taskDropBoard.value=''}
function dropTasks(event,board){if(!nativeTaskIds.length)return;event.preventDefault();event.stopPropagation();let ids;try{ids=JSON.parse(event.dataTransfer.getData('application/x-statement-tasks'))}catch{stopTaskPointer();return}const own=Array.isArray(ids)&&ids.length===nativeTaskIds.length&&ids.every(id=>nativeTaskIds.includes(id));stopTaskPointer();if(own)void moveTasksToBoard(ids,board)}
async function moveTasksToBoard(ids,board){
  if(!canWrite||saving.value||loading.value||deleteMode.value||!validTaskIds(ids))return
  ids=ids.filter(id=>state.value.payload.tasks[id].board_id!==board.id);if(!ids.length)return
  const months=[...new Set(board.period_month?[board.period_month]:board.statement.months||[])]
  let month=months[0]
  if(months.length!==1){try{month=(await ElMessageBox.prompt('目标对账单含多个月份，请填写项目的目标账单月份（YYYY-MM）。','选择目标账单月份',{inputValue:state.value.payload.tasks[ids[0]].month,inputValidator:value=>/^\d{4}-(0[1-9]|1[0-2])$/.test(value)||'请输入 YYYY-MM 格式的月份'})).value}catch{return}}
  await mutate('move_tasks',{task_ids:ids,board_id:board.id,month},`将 ${ids.length} 项项目移至“${board.name}”（${periodLabel(month,board.period_number,false)}）？保留项目内容并记录调整前后的归属。`)
}
function startBoardDrag(event,board) {
  const explicitHandle=event.target.closest('[data-board-drag-handle]')
  if(saving.value||loading.value||deleteMode.value||event.button!==0||
    (!explicitHandle&&event.target.closest('button,input,label,a,select,textarea,[contenteditable],.statement-table-wrap,.statement-board-actions,.statement-ui')))return
  if(drag)return
  event.preventDefault()
  event.stopPropagation()
  activeBoardId.value=board.id
  const scroll=canvasScroll.value
  drag={id:board.id,startX:event.clientX,startY:event.clientY,original:{...position(board)},
    scrollLeft:scroll?.scrollLeft||0,scrollTop:scroll?.scrollTop||0}
  window.addEventListener('pointermove',moveBoard)
  window.addEventListener('pointerup',endBoard,{once:true})
  window.addEventListener('pointercancel',cancelBoardDrag,{once:true})
}
function moveBoard(event) {
  if(!drag)return
  const scroll=canvasScroll.value
  if(scroll) {
    const bounds=scroll.getBoundingClientRect()
    const dx=event.clientX>bounds.right-36?24:event.clientX<bounds.left+36?-24:0
    const dy=event.clientY>bounds.bottom-36?24:event.clientY<bounds.top+36?-24:0
    scroll.scrollBy(dx,dy)
  }
  positions[drag.id]={
    x:Math.max(0,Math.min(20000,drag.original.x+(event.clientX-drag.startX+(scroll?.scrollLeft||0)-drag.scrollLeft)/scale.value)),
    y:Math.max(0,Math.min(20000,drag.original.y+(event.clientY-drag.startY+(scroll?.scrollTop||0)-drag.scrollTop)/scale.value)),
  }
  suppressBoardClickUntil=Date.now()+500
}
function cancelBoardDrag() {
  window.removeEventListener('pointermove',moveBoard)
  window.removeEventListener('pointerup',endBoard)
  window.removeEventListener('pointercancel',cancelBoardDrag)
  if(drag)positions[drag.id]={...drag.original}
  drag=null
}
function endBoard() {
  window.removeEventListener('pointermove',moveBoard)
  window.removeEventListener('pointercancel',cancelBoardDrag)
  const moved=drag
  drag=null
  if(!moved)return
  const next=positions[moved.id]
  if(!next||Math.abs(next.x-moved.original.x)+Math.abs(next.y-moved.original.y)<4) {
    if(next)positions[moved.id]={...moved.original}
    return
  }
}

const inlineVisible=ref(false),inlineBoard=ref(null)
let inlineRevision=0
function openInline(board){if(standardStatement.value||deleteMode.value||saving.value||inlineVisible.value)return;inlineBoard.value=board;inlineRevision=state.value.revision;error.value='';inlineVisible.value=true}
async function changeCompany(board,subject){
  if(!canChangeCompany.value)return
  const changed=await mutate('change_company_subject',{board_id:board.id,subject_key:subject},`将对应客户或子客户的对账单主体同步为${companySubjects[subject]}，同时更新其对账单的公司名称、收款账户和印章？`)
  if(changed)notifyInvoiceParties({kind:'statement-subject',clientId:String(state.value.client_id),subClientId:board.sub_client_id})
}
function clickBoard(event,board){if(Date.now()<suppressBoardClickUntil||event.target.closest('button,input,textarea,label,.statement-ui'))return;openInline(board)}
async function saveInline(data){
  if(state.value.revision!==inlineRevision){error.value='对账单已变化，请关闭窗口重新打开后编辑';return}
  if(await mutate('edit_document',data,'确认保存这份对账单的全部修改？仅修改对账单，每个字段的修改前后内容、操作人与时间都会记录。'))inlineVisible.value=false
}
const editVisible=ref(false),editType=ref('row'),editingBoard=ref(),editingRow=ref(),draft=reactive({}),editForm=ref(),editBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editBody)
const rowFields=[{key:'received_date',label:'来稿日期'},{key:'project_name',label:'项目名称'},{key:'language_pair',label:'翻译方向'},{key:'quantity',label:'工作量'},{key:'basis',label:'计价方式'},{key:'unit_price',label:'单价'},{key:'unit_size',label:'单价对应数量（每多少单位）'},{key:'unit_label',label:'单价口径文案'},{key:'currency',label:'货币',required:true},{key:'subtotal',label:'小计'},{key:'remarks',label:'备注',multiline:true}]
const headerFields=[{key:'name',label:'对账单名称',required:true},{key:'company',label:'公司抬头'},{key:'title',label:'对账单标题'},{key:'client_name',label:'客户名称'},{key:'client_code',label:'客户编号'},{key:'billing_label',label:'账单月份显示（留空按项目月份）'},{key:'issue_date',label:'账单日期'},{key:'tax_included',label:'金额口径标签（金额不自动换算）'},{key:'bank_name',label:'开户行'},{key:'account_name',label:'账户名'},{key:'account_number',label:'账号'},{key:'stamp_image',label:'印章图片'}]
const fixedEditingRow=computed(()=>isFixedStatementRow(editingRow.value))
const editingFields=computed(()=>{
  if(editType.value!=='row')return state.value?.private_settings_available?headerFields:headerFields.filter(field=>!['bank_name','account_name','account_number','stamp_image'].includes(field.key))
  if(!fixedEditingRow.value)return rowFields
  return rowFields.filter(field=>!['quantity','unit_price','unit_size'].includes(field.key)).map(field=>{
    if(field.key==='basis')return {...field,label:'工作量及计价方式',multiline:true}
    if(field.key==='subtotal')return {...field,label:'固定价格'}
    if(field.key==='unit_label')return {...field,label:'金额口径'}
    return field
  })
})
let originalDraft=''
function openEdit(type,board,row){editType.value=type;editingBoard.value=board;editingRow.value=row;for(const key of Object.keys(draft))delete draft[key];const values=type==='row'?row:{...board.fields,name:board.name,tax_included:board.tax_included};for(const field of editingFields.value)draft[field.key]=values[field.key]??'';originalDraft=JSON.stringify(draft);clearFieldSearch();editVisible.value=true}
const editHeader=board=>openEdit('header',board)
const editRow=(board,row)=>openEdit('row',board,row)
async function closeEdit(done){if(saving.value)return;if(JSON.stringify(draft)!==originalDraft&&!await confirm('放弃尚未确认保存的修改？','关闭编辑'))return;if(typeof done==='function')done();else editVisible.value=false}
async function saveEdit(){if(!await editForm.value?.validate().catch(()=>false))return;const old=JSON.parse(originalDraft);const fields=Object.fromEntries(Object.entries(draft).filter(([key,value])=>value!==old[key]));if(!Object.keys(fields).length){editVisible.value=false;return}const names=editingFields.value.filter(field=>Object.hasOwn(fields,field.key)).map(field=>field.label).join('、');const action=editType.value==='row'?'edit_row':'edit_board';const data={board_id:editingBoard.value.id,fields,...(editType.value==='row'?{row_id:editingRow.value._row_id}:{})};if(await mutate(action,data,`确认修改 ${names}？只修改本份对账单，订单号保持不变；修改前内容会保留在记录中。`)){originalDraft=JSON.stringify(draft);editVisible.value=false}}
function recalculate(){const total=calculateCustomerPrice(draft.unit_price,draft.quantity,draft.unit_size);if(total==null)return ElMessage.warning('请填写有效的单价、工作量和大于零的计价数量');draft.subtotal=total}
async function selectStamp(event){const file=event.target.files?.[0];if(!file)return;if(file.size>2000000||!['image/png','image/jpeg','image/webp'].includes(file.type))return ElMessage.warning('请选择2MB以内的PNG、JPG或WebP');draft.stamp_image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)})}

const historyVisible=ref(false),historyLoading=ref(false),historyPage=ref(1),history=reactive({items:[],total:0})
let historySequence=0
async function loadHistory(){const seq=++historySequence;historyLoading.value=true;try{const data=await getStatementWorkspaceHistory(state.value.client_id,{skip:(historyPage.value-1)*20,limit:20});if(seq===historySequence&&!disposed)Object.assign(history,data)}catch(e){error.value=getLocalizedErrorMessage(e,'修改记录加载失败')}finally{if(seq===historySequence)historyLoading.value=false}}
function refreshSubject(event){if(['customer-statement-settings','sub-client-finance','statement-subject'].includes(event.detail?.kind)&&String(event.detail.clientId)===String(state.value?.client_id)&&!saving.value)void load()}
connectInvoiceParties()
window.addEventListener(invoicePartiesEvent,refreshSubject)
onBeforeUnmount(()=>window.removeEventListener(invoicePartiesEvent,refreshSubject))
window.addEventListener('customer-statement-history-refresh',load)
window.addEventListener('customer-statement-workspace-reload',reloadProjects)
onBeforeUnmount(()=>{window.removeEventListener('customer-statement-history-refresh',load);window.removeEventListener('customer-statement-workspace-reload',reloadProjects)})
function openHistory(){historyPage.value=1;historyVisible.value=true;void loadHistory()}
const historyLabels=Object.fromEntries([...rowFields,...headerFields].map(field=>[field.key,field.label]))
async function restoreHistory(row){if(await mutate('restore_history',{history_id:row.id},`恢复至版本 ${row.revision} 修改前？此后所有编排和内容修改将撤销，现状仍会保留在新的恢复记录中。`))void loadHistory()}
async function saveCustomerNote(board,row,value){if(!canEditContent)return;const saved=await mutate('edit_customer_note',{board_id:board.id,row_id:row._row_id,customer_note:value},'',async()=>true);if(saved&&props.settlementScope!=='special')window.dispatchEvent(new CustomEvent('translation-finance-changed',{detail:{clientId:state.value.client_id,projectId:row.root_id}}))}
const exportableBoardIds=computed(()=>documents.value.filter(board=>board.statement.rows.length).map(board=>board.id))
function exportStatements(command,ids){if(command==='print')printBoards(ids);else void download(ids,command)}
async function download(ids,format='excel'){
  if(!ids.length||downloading.value||!state.value)return
  const boards=documents.value.filter(board=>ids.includes(board.id)),revision=state.value.revision,clientId=state.value.client_id,displayMode=mode.value
  if(!boards.length)return
  downloading.value=true;error.value=''
  try{
    const files=[]
    for(const board of boards){const fetch=format==='pdf'?exportStatementWorkspacePdf:exportStatementWorkspace;const blob=await fetch(clientId,{board_ids:[board.id],revision,mode:displayMode,settlement_scope:props.settlementScope});files.push({blob,name:statementFileName(`${board.statement.client_name}-${board.name}`,format)})}
    for(const file of files){const url=URL.createObjectURL(file.blob),link=document.createElement('a');link.href=url;link.download=file.name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),300000)}
  }catch(e){error.value=getLocalizedErrorMessage(e,format==='pdf'?'对账单PDF下载失败':'对账单Excel下载失败')}
  finally{downloading.value=false}
}
function filePrintHtml(id){const element=printSource.value?.querySelector(`[data-statement-print="${CSS.escape(id)}"]`);return `<style>${statementPrintStyles}.statement-ui{display:none}</style>${element?.innerHTML||''}`}
async function printBoards(ids) {
  if(!ids.length||!state.value||downloading.value)return
  downloading.value=true
  try {
    const blob=await exportStatementWorkspacePdf(state.value.client_id,{
      board_ids:ids,revision:state.value.revision,mode:mode.value,settlement_scope:props.settlementScope,
    })
    if(disposed)return
    const url=URL.createObjectURL(blob)
    const frame=document.createElement('iframe')
    frame.style.cssText='position:fixed;width:1px;height:1px;border:0;right:0;bottom:0'
    frame.title='对账单打印'
    const cleanup=()=>{
      frames.delete(cleanup)
      frame.remove()
      URL.revokeObjectURL(url)
    }
    frames.add(cleanup)
    frame.onload=()=>{
      try {
        frame.contentWindow.addEventListener('afterprint',cleanup,{once:true})
        frame.contentWindow.focus()
        frame.contentWindow.print()
      } catch {
        cleanup()
        ElMessage.error('打印窗口打开失败')
      }
    }
    frame.onerror=()=>{cleanup();ElMessage.error('打印文件加载失败')}
    frame.src=url
    document.body.appendChild(frame)
  } catch(error) {
    ElMessage.error(getLocalizedErrorMessage(error,'打印文件生成失败'))
  } finally {
    downloading.value=false
  }
}
watch(()=>[props.clientId,props.projectId,props.focusBoardId,props.focusMonth,props.periodNumber],()=>{exitDeleteMode();inlineVisible.value=false;selected.value=[];editVisible.value=false;historyVisible.value=false;void load()},{immediate:true})
onBeforeUnmount(()=>{disposed=true;sequence++;historySequence++;controller?.abort();clearTimeout(generationTimer);generationRequest?.abort();cancelBoardDrag();stopTaskPointer();for(const cleanup of frames)cleanup()})
</script>
<style scoped>
.statement-project-queues{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;margin:10px 0}.statement-missing-projects,.statement-pending{min-width:0;border:1px solid var(--el-border-color);border-radius:6px;padding:10px;background:#fff}.statement-missing-projects h4,.statement-pending h4{margin:0 0 8px}.statement-project-queues p{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}.statement-pending{grid-column:2}.statement-queue-handle{border:0;background:transparent;cursor:grab;touch-action:none;font-size:20px}.statement-queue-handle:active{cursor:grabbing}@media(max-width:850px){.statement-project-queues{grid-template-columns:minmax(0,1fr)}.statement-pending{grid-column:1;grid-row:1}}
.statement-cross-month-projects{flex:none;margin:4px 10px;border:1px solid var(--el-border-color);border-radius:4px;background:var(--el-color-warning-light-9);max-height:220px;overflow:auto}.statement-cross-month-projects>summary{cursor:pointer;padding:8px;font-size:12px;font-weight:600;user-select:none}
.statement-board-header{cursor:grab;touch-action:none}
.statement-board-header:active{cursor:grabbing}
.statement-board-move{display:inline-flex;align-items:center;min-height:38px;padding:6px 14px;border:1px solid var(--el-border-color);border-radius:6px;background:#fff;color:var(--el-text-color-primary);font:inherit;font-weight:600;cursor:grab;touch-action:none;user-select:none}
.statement-board-move:active{cursor:grabbing;background:var(--el-fill-color-light)}
.statement-board-content :deep(.statement-paper>h2),.statement-board-content :deep(.statement-paper>h3){cursor:grab;touch-action:none}
:global(.statement-maximized-view){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
:global(.statement-maximized-view>.el-dialog__body){flex:1;min-height:0;overflow:auto}
:global(.statement-maximized-view>.el-dialog__header),:global(.statement-maximized-view>.el-dialog__footer){flex:none}
.statement-canvas-space{overflow:clip}
.workspace-generation{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 0 2px}.workspace-generation :deep(.el-form-item){margin:0 0 8px}.workspace-toolbar :deep(.el-button + .el-button){margin-left:0}.workspace-toolbar{padding-top:10px;border-top:1px solid var(--el-border-color-lighter)}.workspace-hint{margin:6px 0 12px}.workspace-toolbar :deep(.el-select){flex-shrink:0}

.customer-projects-scroll{max-height:min(560px,60vh);overflow-y:auto;overflow-x:hidden;scrollbar-gutter:stable;overscroll-behavior:contain}.customer-projects-panel{margin-bottom:12px;border:1px solid var(--el-border-color);border-radius:6px;background:#fff;min-width:0}.customer-projects-panel>summary{cursor:pointer;padding:12px 16px;font-weight:600;user-select:none}.customer-projects-toggle{float:right;font-size:12px;font-weight:400;color:var(--el-text-color-secondary)}.customer-projects-panel :deep(.statement-client-finance > .el-card__header){display:none}.customer-projects-panel :deep(.statement-client-finance){border:0}

.statement-workspace{min-width:0}.statement-help{font-size:12px;line-height:1.7;color:var(--el-text-color-secondary)}.workspace-toolbar,.selection-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}.statement-canvas-scroll{overflow:auto;max-height:72vh;border:1px solid var(--el-border-color);background:#eef2f6}.statement-canvas-space{position:relative;min-width:100%}.statement-canvas{position:relative;transform-origin:top left}.statement-board{position:absolute;width:960px;height:720px;background:white;border:1px solid #ccd3de;border-radius:8px;display:flex;flex-direction:column;box-shadow:0 2px 10px #0001}.statement-board--drop{outline:3px solid var(--el-color-primary)}.statement-board-header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px;border-bottom:1px solid #ddd;flex:none}.statement-board-handle{flex:1;cursor:grab;touch-action:none;user-select:none;font-weight:600}.statement-board-handle:active{cursor:grabbing}.statement-board-actions{padding:10px;display:flex;gap:8px;flex-wrap:wrap;flex:none}.statement-system-meta{margin:8px 16px;color:var(--el-text-color-secondary);font-size:12px}.statement-board-content{flex:1;min-height:0;overflow-x:auto;overflow-y:scroll;scrollbar-gutter:stable;overscroll-behavior-y:contain;scrollbar-width:auto}.statement-edit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.statement-edit-stamp{display:block;width:130px;height:130px;object-fit:contain}.statement-history-changes{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto}.statement-print-source{position:fixed;left:-20000px;top:0;width:1050px;pointer-events:none}.statement-workspace .el-pagination{margin-top:12px}.statement-edit-grid .el-date-editor{max-width:100%;width:100%}
:global(.statement-edit-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.statement-edit-dialog .el-dialog__header),:global(.statement-edit-dialog .el-dialog__footer){flex:none}:global(.statement-edit-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.statement-edit-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}@media(max-width:680px){.statement-edit-grid{grid-template-columns:minmax(0,1fr)}}

.workspace-generation{padding:2px 0;gap:6px}.workspace-generation :deep(.el-form-item){margin:0 0 4px}.workspace-toolbar{margin:4px 0;padding-top:5px;gap:6px}.workspace-hint{font-size:11px;margin:3px 0 6px}.customer-projects-panel{margin-bottom:6px}.customer-projects-panel>summary{padding:8px 12px}.statement-board-header{padding:6px 10px}.statement-board-actions{padding:5px 8px;gap:6px}.statement-board-actions :deep(.el-button + .el-button){margin-left:0}.statement-system-meta{margin:4px 12px}
</style>

<style scoped>
.statement-maximized-view :deep(.el-dialog__body){overflow-y:scroll;scrollbar-gutter:stable;overscroll-behavior:contain}
</style>
