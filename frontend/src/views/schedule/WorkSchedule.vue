<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">工作安排</span>
        <div class="header-actions">
          <el-date-picker
            v-model="scheduleDate"
            type="date"
            placeholder="选择安排日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 170px"
            @change="onDateChange"
          />
          <el-tag type="info" effect="plain">{{ weekdayLabel }}</el-tag>
          <el-button v-if="canEdit" type="primary" @click="handleAddTask">新增任务</el-button>
          <el-button v-if="canEdit" @click="copyFromYesterday">从昨日复制</el-button>
        </div>
      </div>
    </template>

    <!-- 顶层分类 Tabs（管理页：不含「我的任务」，普通用户请使用「我的工作台」/workbench） -->
    <el-tabs v-model="activeTab" type="border-card">

      <!-- ====== Tab: 总览 ====== -->
      <el-tab-pane label="总览" name="overview">
        <!-- 急稿相关说明（原急稿安排内容） -->
        <div class="section-block">
          <div class="sub-section">
            <h4>1. 证件类今日优先次序</h4>
            <p>各位翻译（李娴）轮流安排</p>
          </div>
          <div class="sub-section">
            <h4>2. 急稿译审安排</h4>
            <p>需审改的找<strong>陈佳</strong></p>
          </div>
          <div class="sub-section">
            <h4>3. 文字类今天优先次序</h4>
            <p class="hint">除要求特别高的找Tom看，其他可自行指定翻译基本检查或直接给客户专员。中英/英中译员优先次序见「译员安排」。</p>
          </div>
        </div>

        <!-- Part 0 项目经理安排 -->
        <div class="section-block">
          <h3 class="section-title">项目经理安排</h3>
          <p class="section-desc">
            今天需分析来稿的安排顺序（客户专员直接给翻译/项目专员轮流分析，注意协调——一般不连续给两位分析。如有明显问题请少妃协调）：
          </p>
          <p class="pm-order"><strong>今日分析顺序：</strong>{{ pmRotationOrder }}</p>
          <ul class="rule-list">
            <li>项目较急的、比较大/复杂的，则<strong>优先</strong>，且一个较大项目视为两个项目</li>
            <li>姓名加（2）的同事先轮流两次，然后再全体轮流一次</li>
          </ul>
        </div>

        <!-- Part II 班次 -->
        <div class="section-block">
          <div class="section-title-row">
            <h3 class="section-title">今日班次</h3>
            <el-button v-if="canEdit" type="primary" size="small" @click="openShiftFullEdit">编辑班次</el-button>
          </div>
          <p class="section-desc hint">常规：早早班 8:30-18:00、早班 9:00-18:30、晚班 10:30-20:00、晚晚班 13:30-21:30；另有特殊班次。一周排班一次，临时变动可用「临时调整」。</p>
          <el-table :data="shiftTableData" border size="small" class="data-table">
            <el-table-column prop="shift" label="班次" width="160" show-overflow-tooltip />
            <el-table-column prop="layoutIt" label="排版" min-width="140" show-overflow-tooltip />
            <el-table-column prop="client" label="客户部" min-width="180" show-overflow-tooltip />
            <el-table-column prop="hr" label="（项目助理）HR部" min-width="120" show-overflow-tooltip />
            <el-table-column prop="translationProject" label="翻译部+项目部" min-width="140" show-overflow-tooltip />
            <el-table-column v-if="canEdit" label="操作" width="100" fixed="right">
              <template #default="{ row, $index }">
                <el-button type="primary" link size="small" @click="openShiftRowEdit($index)">临时调整</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="info-block">
            <div class="info-block-title-row">
              <h4>请假/调休</h4>
              <el-button v-if="canEdit" type="primary" link size="small" @click="openLeaveNotesEdit">编辑</el-button>
            </div>
            <ul>
              <li v-for="(note, i) in leaveNotes" :key="i">{{ note }}</li>
            </ul>
            <el-empty v-if="!leaveNotes.length" description="暂无请假/调休公告" :image-size="48" />
          </div>

          <!-- 结构化请假管理 -->
          <div class="info-block" style="margin-top: 16px">
            <div class="info-block-title-row">
              <h4>请假管理（结构化）</h4>
              <el-button v-if="canEdit" type="primary" link size="small" @click="leaveFormVisible = true">新增请假</el-button>
            </div>
            <el-table v-if="leaveRecords.length" :data="leaveRecords" border size="small" class="data-table" style="margin-top: 8px">
              <el-table-column prop="employee_name" label="员工" width="100" />
              <el-table-column prop="start_date" label="开始日期" width="120" />
              <el-table-column prop="end_date" label="结束日期" width="120" />
              <el-table-column prop="leave_type" label="类型" width="100" />
              <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
              <el-table-column v-if="canEdit" label="操作" width="80" fixed="right">
                <template #default="{ row }">
                  <el-popconfirm title="确定删除该条请假记录？" @confirm="handleDeleteLeave(row.id)">
                    <template #reference>
                      <el-button type="danger" link size="small">删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无结构化请假记录" :image-size="48" />
          </div>
        </div>

        <!-- 统计卡片 -->
        <div class="section-block">
          <h3 class="section-title">今日概况</h3>
          <div class="stat-cards">
            <div class="stat-card" v-for="dept in deptStats" :key="dept.name">
              <div class="stat-number">{{ dept.count }}</div>
              <div class="stat-label">{{ dept.name }}</div>
            </div>
            <div class="stat-card stat-card--warn">
              <div class="stat-number">{{ notScheduledCount }}</div>
              <div class="stat-label">暂不安排</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ====== Tab: 译员安排（中英/英中） ====== -->
      <el-tab-pane label="译员安排" name="translator">
        <div class="section-block">
          <div class="sub-section">
            <div class="section-title-row">
              <h4>中英 今日优先次序</h4>
              <el-button v-if="canEdit" type="primary" size="small" @click="openTranslatorTableEdit('zhEn')">编辑中英</el-button>
            </div>
            <p class="hint">除要求特别高的找Tom看，其他可自行指定翻译基本检查或直接给客户专员。</p>
            <el-table :data="urgentTableZhEn" border size="small" class="data-table">
              <el-table-column prop="order" label="优先次序" width="110" />
              <el-table-column prop="name" label="姓名" width="90" />
              <el-table-column prop="type" label="类型" width="80" />
              <el-table-column prop="quality" label="质量" width="60" />
              <el-table-column prop="cloudRev" label="云端/修订" width="100" />
              <el-table-column prop="dailyRate" label="日均接/速度/字数" width="140" />
              <el-table-column prop="remarks" label="备注" min-width="200" show-overflow-tooltip />
            </el-table>
          </div>
          <div class="sub-section">
            <div class="section-title-row">
              <h4>英中 今日优先次序</h4>
              <el-button v-if="canEdit" type="primary" size="small" @click="openTranslatorTableEdit('enZh')">编辑英中</el-button>
            </div>
            <p class="hint">字数多、修订多、参考多等复杂情况需基本检查；要求很高的需找Tom。其他直接给客户专员。</p>
            <el-table :data="urgentTableEnZh" border size="small" class="data-table">
              <el-table-column prop="order" label="优先次序" width="120" />
              <el-table-column prop="name" label="姓名" width="90" />
              <el-table-column prop="type" label="类型" width="140" />
              <el-table-column prop="quality" label="质量" width="60" />
              <el-table-column prop="cloudRev" label="云端/修订" width="100" />
              <el-table-column prop="dailyRate" label="日均接/速度/字数" width="140" />
              <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- ====== Tab: 各部门工作安排 ====== -->
      <el-tab-pane label="各部门安排" name="departments">
        <!-- 部门内部 Tabs -->
        <el-tabs v-model="activeDept" type="card">
          <el-tab-pane
            v-for="dept in DEPARTMENTS"
            :key="dept.key"
            :label="`${dept.label}（${getDeptTaskCount(dept.key)}）`"
            :name="dept.key"
          >
            <!-- 部门内人员列表，每人一个折叠面板 -->
            <el-collapse v-model="openPersons" class="person-collapse">
              <el-collapse-item
                v-for="person in getPersonsByDept(dept.key)"
                :key="person.name"
                :name="person.name"
              >
                <template #title>
                  <div class="person-title">
                    <span class="person-name">{{ person.name }}</span>
                    <el-tag
                      :type="person.status === 'scheduled' ? 'success' : 'info'"
                      size="small"
                      class="person-status"
                    >
                      {{ person.status === 'scheduled' ? '已安排' : '暂不安排' }}
                    </el-tag>
                    <span class="person-task-count">{{ person.tasks.length }} 项任务</span>
                  </div>
                </template>
                <div class="person-tasks">
                  <el-table :data="getDeptTasksSorted(person)" border size="small">
                    <el-table-column type="index" label="#" width="50" />
                    <el-table-column prop="category" label="任务类型" width="140">
                      <template #default="{ row }">
                        <el-tag :type="getTaskCategoryType(row.category)" size="small" effect="plain">
                          {{ row.category }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="content" label="任务内容" min-width="300" show-overflow-tooltip />
                    <el-table-column prop="projectNo" label="项目编号" width="140" show-overflow-tooltip />
                    <el-table-column prop="deadline" label="交稿时间" width="140" show-overflow-tooltip />
                    <el-table-column v-if="canEdit" label="操作" width="100" fixed="right">
                      <template #default="{ row }">
                        <el-button type="primary" link size="small" @click="handleEditDeptTask(person, row)">编辑</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-if="person.fixedTasks && person.fixedTasks.length" class="fixed-tasks">
                    <h5>固定任务</h5>
                    <ul>
                      <li v-for="(ft, fi) in person.fixedTasks" :key="fi">{{ ft }}</li>
                    </ul>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>



      <!-- ====== Tab: 暂不安排 ====== -->
      <el-tab-pane label="暂不安排" name="not_scheduled">
        <div class="section-block">
          <el-table :data="notScheduledTasks" border size="small" class="data-table">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="personName" label="人员" width="100" />
            <el-table-column prop="department" label="部门" width="110" />
            <el-table-column prop="projectOrTask" label="项目/任务" min-width="280" show-overflow-tooltip />
            <el-table-column prop="projectNo" label="项目编号" width="140" show-overflow-tooltip />
            <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
          </el-table>
          <el-empty v-if="!notScheduledTasks.length" description="今日无暂不安排项" />
        </div>
      </el-tab-pane>
      
      <!-- ====== Tab: 当天来稿 ====== -->
      <el-tab-pane label="当天来稿" name="today_incoming">
        <div class="section-block">
          <div class="section-title-row" style="margin-bottom: 12px;">
            <span class="section-desc">当日来稿项目，按回客户时间倒序排列（交稿截止时间越晚的越靠前）。</span>
            <el-button type="primary" size="small" :loading="todayIncomingLoading" @click="fetchTodayIncoming">刷新</el-button>
          </div>
          <el-table :data="todayIncomingList" border size="small" class="data-table" v-loading="todayIncomingLoading">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="project_no" label="项目编号" width="140" show-overflow-tooltip />
            <el-table-column prop="client_name" label="客户/项目" min-width="160" show-overflow-tooltip />
            <el-table-column prop="status" label="项目状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getProjectStatusType(row.status)" size="small" effect="plain">
                  {{ getProjectStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="deadline" label="回客户时间" width="160" sortable show-overflow-tooltip />
            <el-table-column prop="word_count" label="字数" width="100" show-overflow-tooltip />
            <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
          </el-table>
          <el-empty v-if="!todayIncomingLoading && !todayIncomingList.length" description="今日暂无来稿" />
        </div>
      </el-tab-pane>

      <!-- ====== Tab: 全部项目 ====== -->
      <el-tab-pane label="全部项目" name="all_tasks">
        <div class="filter-bar">
          <el-select v-model="taskFilter.dept" placeholder="按部门筛选" clearable style="width: 140px" @change="fetchTasks">
            <el-option v-for="d in DEPARTMENTS" :key="d.key" :label="d.label" :value="d.key" />
          </el-select>
          <el-input v-model="taskFilter.person" placeholder="按人员搜索" clearable style="width: 140px" @keyup.enter="fetchTasks" />
          <el-select v-model="taskFilter.status" placeholder="状态" clearable style="width: 120px" @change="fetchTasks">
            <el-option label="已安排" value="scheduled" />
            <el-option label="暂不安排" value="not_scheduled" />
          </el-select>
          <el-button type="primary" @click="fetchTasks">查询</el-button>
          <el-button @click="resetTaskFilter">重置</el-button>
        </div>
        <el-table :data="filteredTaskList" border size="small" v-loading="loading" class="data-table">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="personName" label="人员" width="100" />
          <el-table-column prop="department" label="部门" width="110" />
          <el-table-column prop="projectOrTask" label="项目/任务" min-width="220" show-overflow-tooltip />
          <el-table-column prop="timeSlot" label="时间段" width="100" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'scheduled' ? 'success' : 'info'" size="small">
                {{ row.status === 'scheduled' ? '已安排' : '暂不安排' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remarks" label="备注" min-width="140" show-overflow-tooltip />
          <el-table-column v-if="canEdit" label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="handleEditTask(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click="handleDeleteTask(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          small
          class="pagination"
          @current-change="fetchTasks"
          @size-change="fetchTasks"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑任务弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" @close="resetTaskForm">
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="100px">
        <el-form-item label="人员" prop="personName">
          <el-input v-model="taskForm.personName" placeholder="请输入人员姓名" />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-select v-model="taskForm.department" placeholder="请选择" clearable style="width: 100%">
            <el-option v-for="d in DEPARTMENTS" :key="d.key" :label="d.label" :value="d.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务类型" prop="taskCategory">
          <el-select v-model="taskForm.taskCategory" placeholder="请选择" clearable style="width: 100%">
            <el-option label="直接项目任务（优先）" value="直接项目任务" />
            <el-option label="非直接项目任务" value="非直接项目任务" />
            <el-option label="固定任务" value="固定任务" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目/任务" prop="projectOrTask">
          <el-input v-model="taskForm.projectOrTask" type="textarea" :rows="3" placeholder="项目或任务描述" />
        </el-form-item>
        <el-form-item label="项目编号" prop="projectNo">
          <el-input v-model="taskForm.projectNo" placeholder="如 TP260205004" />
        </el-form-item>
        <el-form-item label="交稿时间" prop="deadline">
          <el-input v-model="taskForm.deadline" placeholder="如 2月6日15点" />
        </el-form-item>
        <el-form-item label="时间段" prop="timeSlot">
          <el-input v-model="taskForm.timeSlot" placeholder="如：全天、上午、9:00-12:00" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="taskForm.status">
            <el-radio value="scheduled">已安排</el-radio>
            <el-radio value="not_scheduled">暂不安排</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="taskForm.remarks" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">确定</el-button>
      </template>
    </el-dialog>

    <!-- 班次整表编辑弹窗（一周排班） -->
    <el-dialog v-model="shiftFullEditVisible" title="编辑班次表" width="900px" @close="closeShiftFullEdit">
      <p class="section-desc hint">可增删行、修改每格人员；班次时间可选预设或自定义（如 8:45~9:30）。</p>
      <el-table :data="shiftFullEditData" border size="small" class="data-table">
        <el-table-column label="班次" width="180">
          <template #default="{ row }">
            <el-select v-model="row.shift" filterable allow-create default-first-option placeholder="选预设或输入" style="width: 100%">
              <el-option v-for="opt in SHIFT_PRESET_OPTIONS" :key="opt" :label="opt" :value="opt" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="排版" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.layoutIt" placeholder="人员，多人用顿号" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="客户部" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.client" placeholder="人员" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="HR部" min-width="100">
          <template #default="{ row }">
            <el-input v-model="row.hr" placeholder="人员" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="翻译部+项目部" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.translationProject" placeholder="人员" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="removeShiftRow($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="shift-edit-actions">
        <el-button type="primary" plain @click="addShiftRow">新增一行（特殊班次）</el-button>
      </div>
      <template #footer>
        <el-button @click="shiftFullEditVisible = false">取消</el-button>
        <el-button type="primary" @click="submitShiftFullEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 班次单行临时调整弹窗 -->
    <el-dialog v-model="shiftRowEditVisible" title="临时调整该班次" width="520px" @close="closeShiftRowEdit">
      <el-form label-width="120px" size="small">
        <el-form-item label="班次时间">
          <el-select v-model="shiftRowForm.shift" filterable allow-create default-first-option placeholder="选预设或输入" style="width: 100%">
            <el-option v-for="opt in SHIFT_PRESET_OPTIONS" :key="opt" :label="opt" :value="opt" />
          </el-select>
        </el-form-item>
        <el-form-item label="排版">
          <el-input v-model="shiftRowForm.layoutIt" placeholder="多人用顿号分隔" />
        </el-form-item>
        <el-form-item label="客户部">
          <el-input v-model="shiftRowForm.client" />
        </el-form-item>
        <el-form-item label="HR部">
          <el-input v-model="shiftRowForm.hr" />
        </el-form-item>
        <el-form-item label="翻译部+项目部">
          <el-input v-model="shiftRowForm.translationProject" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shiftRowEditVisible = false">取消</el-button>
        <el-button type="primary" @click="submitShiftRowEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 结构化请假新增弹窗 -->
    <el-dialog v-model="leaveFormVisible" title="新增请假记录" width="480px">
      <el-form :model="leaveForm" label-width="80px">
        <el-form-item label="员工">
          <el-select v-model="leaveForm.employee_id" filterable placeholder="请选择员工" style="width: 100%" @change="onLeaveEmployeeChange">
            <el-option v-for="u in allStaffList" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="leaveForm.start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="leaveForm.end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择结束日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="leaveForm.leave_type" placeholder="请选择" style="width: 100%">
            <el-option label="请假" value="请假" />
            <el-option label="调休" value="调休" />
            <el-option label="事假" value="事假" />
            <el-option label="病假" value="病假" />
            <el-option label="年假" value="年假" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="leaveForm.reason" type="textarea" :rows="2" placeholder="可选填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leaveFormVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLeaveForm">提交</el-button>
      </template>
    </el-dialog>

    <!-- 请假/调休公告编辑弹窗 -->
    <el-dialog v-model="leaveNotesEditVisible" title="编辑请假/调休公告" width="560px" @close="closeLeaveNotesEdit">
      <p class="section-desc hint">已提前申请的请假、调休等，可增删改。保存后仅影响当日安排数据。</p>
      <div class="leave-notes-edit-list">
        <div v-for="(item, i) in leaveNotesEditList" :key="i" class="leave-notes-edit-item">
          <el-input v-model="leaveNotesEditList[i]" type="textarea" :rows="2" placeholder="如：张三 2月10日-12日请假" />
          <el-button type="danger" link size="small" class="leave-notes-del-btn" @click="removeLeaveNote(i)">删除</el-button>
        </div>
      </div>
      <el-button type="primary" plain size="small" @click="addLeaveNote">新增一条</el-button>
      <template #footer>
        <el-button @click="leaveNotesEditVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLeaveNotesEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 译员安排表编辑（中英/英中） -->
    <el-dialog v-model="translatorEditVisible" :title="translatorEditTitle" width="920px" @close="closeTranslatorTableEdit">
      <p class="section-desc hint">可增删行、修改各列。保存后仅影响当日安排数据。</p>
      <el-table :data="translatorEditData" border size="small" class="data-table">
        <el-table-column label="优先次序" width="120">
          <template #default="{ row }">
            <el-input v-model="row.order" placeholder="如 1、2、N/A" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="姓名" width="100">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-input v-model="row.type" placeholder="如 全部" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="质量" width="70">
          <template #default="{ row }">
            <el-input v-model="row.quality" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="云端/修订" width="100">
          <template #default="{ row }">
            <el-input v-model="row.cloudRev" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="日均接/速度/字数" width="150">
          <template #default="{ row }">
            <el-input v-model="row.dailyRate" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.remarks" type="textarea" :rows="1" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" @click="removeTranslatorRow($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="shift-edit-actions">
        <el-button type="primary" plain @click="addTranslatorRow">新增一行</el-button>
      </div>
      <template #footer>
        <el-button @click="translatorEditVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTranslatorTableEdit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjects } from '@/api/projects'
import { canEditSchedule } from '@/utils/permission'
import { getSchedule, saveSchedule, copySchedule, getStaffList, getTranslatorList } from '@/api/schedule'
import { getLeaveRecords, createLeave, deleteLeave } from '@/api/leave'

// ==================== 常量 ====================
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
/** 班次预设：早早班、早班、晚班、晚晚班 + 常见特殊班次 */
const SHIFT_PRESET_OPTIONS = [
  '早早班 8:30-18:00',
  '早班 9:00-18:30',
  '晚班 10:30-20:00',
  '晚晚班 13:30-21:30',
  '9:30-18:30',
  '8:45~9:30'
]
const DEPARTMENTS = [
  { key: '项目经理', label: '项目经理' },
  { key: '翻译部', label: '翻译部' },
  { key: '项目部', label: '项目部' },
  { key: '客户部', label: '客户部' },
  { key: 'HR部', label: 'HR部' },
  { key: '排版', label: '排版' },
  { key: '招聘项目', label: '招聘项目' },
  { key: '销售', label: '销售' }
]

// ==================== 状态 ====================
const scheduleDate = ref('')
const activeTab = ref('overview')
const activeDept = ref('项目经理')
const openPersons = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增任务')
const taskFormRef = ref(null)

// 班次编辑：整表 / 单行
const shiftFullEditVisible = ref(false)
const shiftFullEditData = ref([])
const shiftRowEditVisible = ref(false)
const editingShiftRowIndex = ref(-1)
const shiftRowForm = reactive({ shift: '', layoutIt: '', client: '', hr: '', translationProject: '' })

// 请假/调休公告编辑
const leaveNotesEditVisible = ref(false)
const leaveNotesEditList = ref([])

// 译员安排表编辑（中英 / 英中）
const translatorEditVisible = ref(false)
const translatorEditType = ref('zhEn') // 'zhEn' | 'enZh'
const translatorEditData = ref([])
const translatorEditTitle = computed(() =>
  translatorEditType.value === 'zhEn' ? '编辑中英 今日优先次序' : '编辑英中 今日优先次序'
)

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return WEEKDAYS[new Date(scheduleDate.value).getDay()]
})

/** 当前用户是否有编辑排班的权限（项目经理、超管） */
const canEdit = computed(() => canEditSchedule())

const pmRotationOrder = ref('伟琪 / 李娴 / 孟花')

// ==================== 急稿表（从 translator 表动态拉取） ====================
const urgentTableZhEn = ref([])
const urgentTableEnZh = ref([])

// ==================== 班次表 ====================
const shiftTableData = ref([])
const leaveNotes = ref([])

// ==================== 结构化请假管理 ====================
const leaveRecords = ref([])
const leaveFormVisible = ref(false)
const leaveForm = reactive({
  employee_id: '',
  employee_name: '',
  start_date: '',
  end_date: '',
  leave_type: '请假',
  reason: ''
})
const allStaffList = ref([])

async function loadLeaveRecords() {
  try {
    const res = await getLeaveRecords()
    leaveRecords.value = Array.isArray(res) ? res : []
  } catch {
    leaveRecords.value = []
  }
}

function onLeaveEmployeeChange(empId) {
  const u = allStaffList.value.find((s) => s.id === empId)
  leaveForm.employee_name = u ? u.name : ''
}

async function submitLeaveForm() {
  if (!leaveForm.employee_id || !leaveForm.start_date || !leaveForm.end_date) {
    ElMessage.warning('请填写员工、开始日期、结束日期')
    return
  }
  try {
    await createLeave({
      employee_id: leaveForm.employee_id,
      employee_name: leaveForm.employee_name,
      start_date: leaveForm.start_date,
      end_date: leaveForm.end_date,
      leave_type: leaveForm.leave_type,
      reason: leaveForm.reason
    })
    ElMessage.success('请假记录已添加')
    leaveFormVisible.value = false
    leaveForm.employee_id = ''
    leaveForm.employee_name = ''
    leaveForm.start_date = ''
    leaveForm.end_date = ''
    leaveForm.leave_type = '请假'
    leaveForm.reason = ''
    loadLeaveRecords()
  } catch (e) {
    ElMessage.error('添加失败：' + (e.response?.data?.detail || e.message))
  }
}

async function handleDeleteLeave(leaveId) {
  try {
    await deleteLeave(leaveId)
    ElMessage.success('已删除')
    loadLeaveRecords()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

// ==================== 各部门人员任务数据 ====================
const deptPersonData = ref([])

/**
 * 从后端 API 动态拉取员工列表，生成排班初始模板
 */
async function fetchDefaultDeptPersonData() {
  try {
    const staffList = await getStaffList()
    if (Array.isArray(staffList) && staffList.length > 0) {
      return staffList.map((s) => ({
        name: s.name,
        dept: s.dept || '',
        status: 'scheduled',
        tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }],
        fixedTasks: Array.isArray(s.fixedTasks) ? s.fixedTasks : []
      }))
    }
  } catch (e) {
    console.warn('拉取员工列表失败，使用空模板', e)
  }
  return []
}

/**
 * 从后端 API 动态拉取译员列表
 */
async function fetchDefaultTranslatorData(direction) {
  try {
    const list = await getTranslatorList(direction)
    if (Array.isArray(list)) return list
  } catch (e) {
    console.warn('拉取译员列表失败', e)
  }
  return []
}

async function initDeptPersonData() {
  deptPersonData.value = await fetchDefaultDeptPersonData()
}

/** 获取某日工作安排的默认数据（用于无存储时的初始模板，从数据库动态生成） */
async function getDefaultScheduleData() {
  const [defaultStaff, defaultZhEn, defaultEnZh] = await Promise.all([
    fetchDefaultDeptPersonData(),
    fetchDefaultTranslatorData('zh_en'),
    fetchDefaultTranslatorData('en_zh')
  ])
  return {
    deptPersonData: defaultStaff,
    notScheduledTasks: [],
    pmRotationOrder: '',
    shiftTableData: [],
    leaveNotes: [],
    urgentTableZhEn: defaultZhEn,
    urgentTableEnZh: defaultEnZh
  }
}

async function saveScheduleForDate() {
  const date = scheduleDate.value
  if (!date) return
  try {
    const data = {
      shift_table: shiftTableData.value,
      leave_notes: leaveNotes.value,
      urgent_table_zh_en: urgentTableZhEn.value,
      urgent_table_en_zh: urgentTableEnZh.value,
      dept_person_data: deptPersonData.value,
      not_scheduled_tasks: notScheduledTasks.value,
      pm_rotation_order: pmRotationOrder.value
    }
    await saveSchedule(date, data)
  } catch (e) {
    console.error('保存工作安排失败', e)
  }
}

/** 加载某日安排到页面：从后端拉取，无则用默认数据 */
async function loadScheduleForDate(date) {
  // 并行发起默认数据和当日排班数据，不再串行等待
  const [defaultResult, storedResult] = await Promise.allSettled([
    getDefaultScheduleData(),
    getSchedule(date)
  ])
  const defaultData = defaultResult.status === 'fulfilled' ? defaultResult.value : {
    deptPersonData: [], notScheduledTasks: [], pmRotationOrder: '',
    shiftTableData: [], leaveNotes: [], urgentTableZhEn: [], urgentTableEnZh: []
  }
  const stored = storedResult.status === 'fulfilled' ? storedResult.value : null

  if (stored) {
    deptPersonData.value = stored.dept_person_data ?? defaultData.deptPersonData
    notScheduledTasks.value = stored.not_scheduled_tasks ?? defaultData.notScheduledTasks
    pmRotationOrder.value = stored.pm_rotation_order ?? defaultData.pmRotationOrder
    shiftTableData.value = stored.shift_table ?? defaultData.shiftTableData
    leaveNotes.value = stored.leave_notes ?? defaultData.leaveNotes
    urgentTableZhEn.value = stored.urgent_table_zh_en ?? defaultData.urgentTableZhEn
    urgentTableEnZh.value = stored.urgent_table_en_zh ?? defaultData.urgentTableEnZh
  } else {
    // 404 或网络错误，用默认数据
    deptPersonData.value = defaultData.deptPersonData
    notScheduledTasks.value = defaultData.notScheduledTasks
    pmRotationOrder.value = defaultData.pmRotationOrder
    shiftTableData.value = defaultData.shiftTableData
    leaveNotes.value = defaultData.leaveNotes
    urgentTableZhEn.value = defaultData.urgentTableZhEn
    urgentTableEnZh.value = defaultData.urgentTableEnZh
  }
  fetchTasks()
}

// ==================== 班次编辑（整表 / 单行临时调整） ====================
function openShiftFullEdit() {
  shiftFullEditData.value = JSON.parse(JSON.stringify(shiftTableData.value))
  shiftFullEditVisible.value = true
}

function closeShiftFullEdit() {
  shiftFullEditData.value = []
}

function addShiftRow() {
  shiftFullEditData.value.push({ shift: '', layoutIt: '', client: '', hr: '', translationProject: '' })
}

function removeShiftRow(index) {
  shiftFullEditData.value.splice(index, 1)
}

function submitShiftFullEdit() {
  shiftTableData.value = JSON.parse(JSON.stringify(shiftFullEditData.value))
  saveScheduleForDate()
  shiftFullEditVisible.value = false
  ElMessage.success('班次表已保存')
}

function openShiftRowEdit(index) {
  const row = shiftTableData.value[index]
  if (!row) return
  editingShiftRowIndex.value = index
  shiftRowForm.shift = row.shift || ''
  shiftRowForm.layoutIt = row.layoutIt || ''
  shiftRowForm.client = row.client || ''
  shiftRowForm.hr = row.hr || ''
  shiftRowForm.translationProject = row.translationProject || ''
  shiftRowEditVisible.value = true
}

function closeShiftRowEdit() {
  editingShiftRowIndex.value = -1
  shiftRowForm.shift = ''
  shiftRowForm.layoutIt = ''
  shiftRowForm.client = ''
  shiftRowForm.hr = ''
  shiftRowForm.translationProject = ''
}

function submitShiftRowEdit() {
  const idx = editingShiftRowIndex.value
  if (idx < 0 || !shiftTableData.value[idx]) return
  shiftTableData.value[idx] = {
    shift: shiftRowForm.shift,
    layoutIt: shiftRowForm.layoutIt,
    client: shiftRowForm.client,
    hr: shiftRowForm.hr,
    translationProject: shiftRowForm.translationProject
  }
  saveScheduleForDate()
  shiftRowEditVisible.value = false
  ElMessage.success('该班次已临时调整并保存')
}

// ==================== 请假/调休公告编辑 ====================
function openLeaveNotesEdit() {
  leaveNotesEditList.value = [...leaveNotes.value]
  leaveNotesEditVisible.value = true
}

function closeLeaveNotesEdit() {
  leaveNotesEditList.value = []
}

function addLeaveNote() {
  leaveNotesEditList.value.push('')
}

function removeLeaveNote(index) {
  leaveNotesEditList.value.splice(index, 1)
}

function submitLeaveNotesEdit() {
  leaveNotes.value = leaveNotesEditList.value.filter((s) => String(s).trim() !== '')
  saveScheduleForDate()
  leaveNotesEditVisible.value = false
  ElMessage.success('请假/调休公告已保存')
}

// ==================== 译员安排表编辑（中英/英中） ====================
const TRANSLATOR_ROW_TEMPLATE = () => ({
  order: '',
  name: '',
  type: '',
  quality: '',
  cloudRev: '',
  dailyRate: '',
  remarks: ''
})

function openTranslatorTableEdit(type) {
  translatorEditType.value = type
  const source = type === 'zhEn' ? urgentTableZhEn.value : urgentTableEnZh.value
  translatorEditData.value = JSON.parse(JSON.stringify(source.length ? source : [TRANSLATOR_ROW_TEMPLATE()]))
  translatorEditVisible.value = true
}

function closeTranslatorTableEdit() {
  translatorEditData.value = []
}

function addTranslatorRow() {
  translatorEditData.value.push(TRANSLATOR_ROW_TEMPLATE())
}

function removeTranslatorRow(index) {
  translatorEditData.value.splice(index, 1)
}

function submitTranslatorTableEdit() {
  const data = translatorEditData.value.map((r) => ({
    order: r.order || '',
    name: r.name || '',
    type: r.type || '',
    quality: r.quality || '',
    cloudRev: r.cloudRev || '',
    dailyRate: r.dailyRate || '',
    remarks: r.remarks || ''
  }))
  if (translatorEditType.value === 'zhEn') {
    urgentTableZhEn.value = data
  } else {
    urgentTableEnZh.value = data
  }
  saveScheduleForDate()
  translatorEditVisible.value = false
  ElMessage.success(translatorEditType.value === 'zhEn' ? '中英译员安排已保存' : '英中译员安排已保存')
}

// ==================== 暂不安排 ====================
const notScheduledTasks = ref([])

// ==================== 当天来稿 ====================
const todayIncomingList = ref([])
const todayIncomingLoading = ref(false)

function getProjectStatusLabel(status) {
  const map = { pending: '待启动', in_progress: '进行中', completed: '已完成', paused: '已暂停' }
  return map[status] || status || '-'
}

function getProjectStatusType(status) {
  const map = { pending: 'info', in_progress: 'warning', completed: 'success', paused: 'danger' }
  return map[status] || 'info'
}

/** 解析日期字符串为可比较值（用于排序），支持 ISO、YYYY-MM-DD、中文简写等 */
function parseDeadlineForSort(deadline) {
  if (!deadline || typeof deadline !== 'string') return 0
  const s = deadline.trim()
  const iso = /^\d{4}-\d{2}-\d{2}/.exec(s)
  if (iso) return new Date(iso[0]).getTime()
  const cn = /(\d{1,2})月(\d{1,2})日/.exec(s)
  if (cn) {
    const y = new Date().getFullYear()
    const m = parseInt(cn[1], 10) - 1
    const d = parseInt(cn[2], 10)
    return new Date(y, m, d).getTime()
  }
  return 0
}

async function fetchTodayIncoming() {
  todayIncomingLoading.value = true
  try {
    const dateToUse = scheduleDate.value || new Date().toISOString().slice(0, 10)
    const todayStr = dateToUse.slice(0, 10)
    const res = await getProjects({ limit: 500 })
    const list = Array.isArray(res) ? res : []
    const todayItems = list.filter((p) => {
      const createdAt = p.created_at
      if (!createdAt) return false
      const createdStr = typeof createdAt === 'string' ? createdAt.slice(0, 10) : ''
      return createdStr === todayStr
    })
    todayItems.sort((a, b) => {
      const ta = parseDeadlineForSort(a.deadline)
      const tb = parseDeadlineForSort(b.deadline)
      return tb - ta
    })
    todayIncomingList.value = todayItems
  } catch (e) {
    ElMessage.error('获取当天来稿失败：' + (e.message || '网络错误'))
    todayIncomingList.value = []
  } finally {
    todayIncomingLoading.value = false
  }
}

watch(activeTab, (name) => {
  if (name === 'today_incoming') fetchTodayIncoming()
})

// ==================== 部门统计 ====================
const deptStats = computed(() => {
  return DEPARTMENTS.map((d) => ({
    name: d.label,
    count: deptPersonData.value.filter((p) => p.dept === d.key && p.status === 'scheduled').length
  }))
})
const notScheduledCount = computed(() => notScheduledTasks.value.length)

function getDeptTaskCount(deptKey) {
  return deptPersonData.value.filter((p) => p.dept === deptKey).length
}

function getPersonsByDept(deptKey) {
  return deptPersonData.value.filter((p) => p.dept === deptKey)
}

function getTaskCategoryType(cat) {
  const map = { '直接项目任务': 'danger', '非直接项目任务': 'warning', '固定任务': 'info', '其他': '' }
  return map[cat] || ''
}

/** 任务类型显示顺序：直接项目任务 > 非直接项目任务 > 固定任务 > 其他 */
const TASK_CATEGORY_ORDER = { '直接项目任务': 0, '非直接项目任务': 1, '固定任务': 2, '其他': 3 }
function getDeptTasksSorted(person) {
  if (!person?.tasks?.length) return []
  return [...person.tasks].sort((a, b) => {
    const orderA = TASK_CATEGORY_ORDER[a.category] ?? 4
    const orderB = TASK_CATEGORY_ORDER[b.category] ?? 4
    return orderA - orderB
  })
}

// ==================== 全部项目列表 ====================
const taskFilter = reactive({ dept: '', person: '', status: '' })
const filteredTaskList = ref([])
const pagination = reactive({ page: 1, limit: 20, total: 0 })

function buildFlatTasks() {
  const arr = []
  deptPersonData.value.forEach((p) => {
    p.tasks.forEach((t) => {
      arr.push({
        id: `${p.name}-${t.content}`.slice(0, 30) + '-' + Math.random().toString(36).slice(2, 6),
        personName: p.name,
        department: p.dept,
        projectOrTask: t.content,
        projectNo: t.projectNo || '',
        timeSlot: '',
        status: p.status,
        remarks: t.deadline ? `交稿: ${t.deadline}` : ''
      })
    })
  })
  return arr
}

function fetchTasks() {
  loading.value = true
  let list = buildFlatTasks()
  if (taskFilter.dept) list = list.filter((t) => t.department === taskFilter.dept)
  if (taskFilter.person) {
    const kw = taskFilter.person.trim().toLowerCase()
    list = list.filter((t) => t.personName.toLowerCase().includes(kw))
  }
  if (taskFilter.status) list = list.filter((t) => t.status === taskFilter.status)
  pagination.total = list.length
  const start = (pagination.page - 1) * pagination.limit
  filteredTaskList.value = list.slice(start, start + pagination.limit)
  loading.value = false
}

function resetTaskFilter() {
  taskFilter.dept = ''
  taskFilter.person = ''
  taskFilter.status = ''
  pagination.page = 1
  fetchTasks()
}

// ==================== 新增/编辑弹窗 ====================
const taskForm = reactive({
  id: '', scheduleDate: '', personName: '', department: '', taskCategory: '', projectOrTask: '', projectNo: '', deadline: '', timeSlot: '', status: 'scheduled', remarks: '',
  _editContent: '', _editProjectNo: '' // 编辑时用于定位原任务，提交后替换
})
const taskRules = {
  personName: [{ required: true, message: '请输入人员', trigger: 'blur' }],
  department: [{ required: true, message: '请选择部门', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

function handleAddTask() {
  dialogTitle.value = '新增任务'
  resetTaskForm()
  dialogVisible.value = true
}

function handleEditTask(row) {
  dialogTitle.value = '编辑任务'
  Object.assign(taskForm, { id: row.id, personName: row.personName, department: row.department, projectOrTask: row.projectOrTask, status: row.status, remarks: row.remarks })
  dialogVisible.value = true
}

function handleEditDeptTask(person, task) {
  dialogTitle.value = '编辑任务'
  Object.assign(taskForm, {
    id: `${person.name}-edit`,
    personName: person.name,
    department: person.dept,
    taskCategory: task.category,
    projectOrTask: task.content,
    projectNo: task.projectNo || '',
    deadline: task.deadline || '',
    status: person.status,
    _editContent: task.content,
    _editProjectNo: task.projectNo || ''
  })
  dialogVisible.value = true
}

function handleDeleteTask(row) {
  ElMessageBox.confirm('确定要删除该任务吗？', '提示', { type: 'warning' })
    .then(() => {
      const person = deptPersonData.value.find((p) => p.name === row.personName && p.dept === row.department)
      if (person) {
        person.tasks = person.tasks.filter((t) => t.content !== row.projectOrTask)
      }
      ElMessage.success('已删除')
      saveScheduleForDate()
      fetchTasks()
    })
    .catch(() => {})
}

function submitTask() {
  if (!taskFormRef.value) return
  taskFormRef.value.validate((valid) => {
    if (!valid) return
    const person = deptPersonData.value.find((p) => p.name === taskForm.personName && p.dept === taskForm.department)
    const newTask = {
      category: taskForm.taskCategory || '其他',
      content: taskForm.projectOrTask || '',
      projectNo: taskForm.projectNo || '',
      deadline: taskForm.deadline || ''
    }
    if (person) {
      if (taskForm.id && taskForm.id.endsWith('-edit')) {
        const idx = person.tasks.findIndex(
          (t) => t.content === taskForm._editContent && (t.projectNo || '') === (taskForm._editProjectNo || '')
        )
        if (idx !== -1) person.tasks[idx] = newTask
      } else {
        person.tasks.push(newTask)
      }
      person.status = taskForm.status
    } else {
      deptPersonData.value.push({
        name: taskForm.personName,
        dept: taskForm.department,
        status: taskForm.status,
        tasks: [newTask],
        fixedTasks: []
      })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    saveScheduleForDate()
    fetchTasks()
  })
}

function resetTaskForm() {
  Object.keys(taskForm).forEach((k) => {
    if (k.startsWith('_')) return
    taskForm[k] = ''
  })
  taskForm.status = 'scheduled'
  taskForm._editContent = ''
  taskForm._editProjectNo = ''
  taskFormRef.value?.resetFields()
}

function onDateChange() {
  loadScheduleForDate(scheduleDate.value)
}

/** 取昨日日期 YYYY-MM-DD */
function getYesterdayDate(dateStr) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() - 1)
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
}

async function copyFromYesterday() {
  const yesterday = getYesterdayDate(scheduleDate.value)
  try {
    await copySchedule(yesterday, scheduleDate.value)
    await loadScheduleForDate(scheduleDate.value)
    ElMessage.success('已从昨日复制并保存为当日安排')
  } catch (e) {
    ElMessage.warning('昨日无安排数据可复制，请先保存昨日安排或选择其他日期')
  }
}

// ==================== 初始化 ====================
onMounted(async () => {
  const today = new Date()
  scheduleDate.value = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-')
  // 三组请求全部并行，互不等待；getStaffList 与 loadScheduleForDate 内部的 staff/list 合并为一次
  const [, , staffResult] = await Promise.allSettled([
    loadScheduleForDate(scheduleDate.value),
    loadLeaveRecords(),
    getStaffList()
  ])
  allStaffList.value = staffResult.status === 'fulfilled' && Array.isArray(staffResult.value)
    ? staffResult.value
    : []
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

/* 各分区 */
.section-block {
  margin-bottom: 28px;
}
.section-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.section-title-row .section-title {
  margin: 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-color-primary-light-7);
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-color-primary-light-7);
}
.section-desc {
  margin: 0 0 8px 0;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
.pm-order {
  margin: 10px 0;
  font-size: 15px;
}
.rule-list {
  padding-left: 20px;
  margin: 0 0 12px 0;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}
.rule-list li { margin-bottom: 4px; }

/* 数据表格 */
.data-table {
  margin-bottom: 12px;
}

/* 信息块 */
.info-block {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.info-block-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.info-block-title-row h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}
.info-block h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
}
.info-block ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.7;
}

/* 统计卡片 */
.stat-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.stat-card {
  flex: 1;
  min-width: 100px;
  padding: 16px;
  background: var(--el-color-primary-light-9);
  border-radius: 8px;
  text-align: center;
  border: 1px solid var(--el-color-primary-light-7);
}
.stat-card--warn {
  background: var(--el-color-info-light-9);
  border-color: var(--el-color-info-light-7);
}
.stat-number {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.stat-card--warn .stat-number {
  color: var(--el-color-info);
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

/* 急稿子段 */
.sub-section { margin-bottom: 20px; }
.sub-section h4 { margin: 0 0 8px; font-size: 14px; color: var(--el-text-color-primary); }
.sub-section h5 { margin: 14px 0 6px; font-size: 13px; color: var(--el-text-color-regular); }
.hint { color: var(--el-text-color-secondary); font-size: 12px; margin: 4px 0 8px; }
.shift-edit-actions {
  margin-top: 12px;
}
.leave-notes-edit-list {
  margin-bottom: 12px;
  max-height: 320px;
  overflow-y: auto;
}
.leave-notes-edit-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 10px;
}
.leave-notes-edit-item .el-input { flex: 1; }
.leave-notes-del-btn { flex-shrink: 0; margin-top: 4px; }

/* 部门 > 人员折叠面板 */
.person-collapse {
  border: none;
}
.person-title {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.person-name {
  font-weight: 600;
  font-size: 14px;
}
.person-status {
  flex-shrink: 0;
}
.person-task-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
  padding-right: 12px;
}
.person-tasks {
  padding: 4px 0;
}
.fixed-tasks {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
.fixed-tasks h5 {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.fixed-tasks ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* 筛选 */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
