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
          <el-button type="primary" @click="handleAddTask">新增任务</el-button>
        </div>
      </div>
    </template>

    <!-- 顶层分类 Tabs -->
    <el-tabs v-model="activeTab" type="border-card">

      <!-- ====== Tab: 我的任务 ====== -->
      <el-tab-pane label="我的任务" name="my_tasks">
        <div class="section-block">
          <p v-if="currentUserName" class="section-desc">当前用户：<strong>{{ currentUserName }}</strong></p>
          <el-table :data="myTasksList" border size="small" class="data-table">
            <el-table-column type="index" label="序号" width="60" />
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
          </el-table>
          <div v-if="currentUserName && !myTasksList.length" class="info-block">
            <p>暂无您的任务，或安排表中的姓名与登录账号不一致。如有疑问请联系项目经理。</p>
          </div>
          <el-empty v-else-if="!currentUserName" description="请先登录，登录账号将用于匹配「我的任务」" />
        </div>
      </el-tab-pane>

      <!-- ====== Tab: 总览 ====== -->
      <el-tab-pane label="总览" name="overview">
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
          <h3 class="section-title">今日班次</h3>
          <el-table :data="shiftTableData" border size="small" class="data-table">
            <el-table-column prop="shift" label="班次" width="140" />
            <el-table-column prop="layoutIt" label="排版/IT部" min-width="160" show-overflow-tooltip />
            <el-table-column prop="client" label="客户部" min-width="200" show-overflow-tooltip />
            <el-table-column prop="hr" label="HR部" min-width="140" show-overflow-tooltip />
            <el-table-column prop="translationProject" label="翻译部+项目部" min-width="160" show-overflow-tooltip />
          </el-table>
          <div class="info-block">
            <h4>请假/调休</h4>
            <ul>
              <li v-for="(note, i) in leaveNotes" :key="i">{{ note }}</li>
            </ul>
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

      <!-- ====== Tab: 急稿安排 ====== -->
      <el-tab-pane label="急稿安排" name="urgent">
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
            <p class="hint">除要求特别高的找Tom看，其他可自行指定翻译基本检查或直接给客户专员。</p>

            <h5>(1) 中英</h5>
            <el-table :data="urgentTableZhEn" border size="small" class="data-table">
              <el-table-column prop="order" label="优先次序" width="110" />
              <el-table-column prop="name" label="姓名" width="90" />
              <el-table-column prop="type" label="类型" width="80" />
              <el-table-column prop="quality" label="质量" width="60" />
              <el-table-column prop="cloudRev" label="云端/修订" width="100" />
              <el-table-column prop="dailyRate" label="日均接/速度/字数" width="140" />
              <el-table-column prop="remarks" label="备注" min-width="200" show-overflow-tooltip />
            </el-table>

            <h5>(2) 英中</h5>
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
                  <el-table :data="person.tasks" border size="small">
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
                    <el-table-column label="操作" width="100" fixed="right">
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
          <el-table-column label="操作" width="120" fixed="right">
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
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ==================== 常量 ====================
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const DEPARTMENTS = [
  { key: '项目经理', label: '项目经理' },
  { key: '翻译部', label: '翻译部' },
  { key: '项目部', label: '项目部' },
  { key: '客户部', label: '客户部' },
  { key: 'HR部', label: 'HR部' },
  { key: '排版/IT部', label: '排版/IT部' },
  { key: '招聘项目', label: '招聘项目' },
  { key: '销售', label: '销售' }
]

// ==================== 状态 ====================
const scheduleDate = ref('')
const activeTab = ref('my_tasks')
const activeDept = ref('项目经理')
const openPersons = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增任务')
const taskFormRef = ref(null)

const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return WEEKDAYS[new Date(scheduleDate.value).getDay()]
})

/** 当前登录用户名（用于「我的任务」匹配安排表中的人员姓名） */
const currentUserName = ref('')
function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

/** 我的任务：根据当前用户名从部门人员数据中筛出该人员的任务列表 */
const myTasksList = computed(() => {
  const name = currentUserName.value
  if (!name) return []
  const person = deptPersonData.value.find((p) => p.name === name || p.name.includes(name) || name.includes(p.name))
  if (!person || !person.tasks) return []
  return person.tasks.map((t) => ({
    category: t.category,
    content: t.content,
    projectNo: t.projectNo || '',
    deadline: t.deadline || ''
  }))
})

const pmRotationOrder = ref('伟琪 / 李娴 / 孟花')

// ==================== 急稿表 ====================
const urgentTableZhEn = ref([
  { order: '2 中午12点后', name: '王婷', type: '全部', quality: '73', cloudRev: '-', dailyRate: '5/1000/8000', remarks: '法律类需审改，其他中英要求不是很高的可基本检查' },
  { order: '3 傍晚5点后', name: '王邃玲', type: '全部', quality: '80', cloudRev: '可/可', dailyRate: '5/1000/6000', remarks: '法律类需安排审改' },
  { order: '1', name: '高超', type: '全部', quality: '73', cloudRev: '可/可', dailyRate: '5/1000/8000', remarks: '大概仅适合银行，法律类需审改' },
  { order: 'N/A', name: '曹柳云', type: '全部', quality: '73', cloudRev: '可/可', dailyRate: '-', remarks: '非合同法律类需审改' },
  { order: '0', name: '孙红艳', type: '全部', quality: '74', cloudRev: '可/可', dailyRate: '2/500/2000', remarks: '中英要求不高的均可基本检查' },
  { order: '1', name: '商莹', type: '全部', quality: '74', cloudRev: '可/可', dailyRate: '3/500/3000', remarks: '不接法律和医学' },
  { order: 'N/A', name: '陈风', type: '全部', quality: '73', cloudRev: '-', dailyRate: '?/?/7000', remarks: '需审改' },
  { order: '2 中午12点后', name: '雷智', type: '全部', quality: '74', cloudRev: '-', dailyRate: '?/?/4000', remarks: '需审改' },
  { order: 'N/A', name: '何长青', type: '全部', quality: '74', cloudRev: '-', dailyRate: '?/?/4000', remarks: '需审改' },
  { order: '1', name: '李鲁莎', type: '全部', quality: '73', cloudRev: '-', dailyRate: '?/?/6000', remarks: '需审改' }
])

const urgentTableEnZh = ref([
  { order: '2（白天不做稿）', name: '史明月', type: '全部（不适合对中文要求高的）', quality: '74', cloudRev: '可/未知', dailyRate: '1/500/4000', remarks: '工作日中午和下午不能做稿，一般需审改' },
  { order: '1', name: '杨雪', type: '全部（法律类优先）', quality: '75', cloudRev: '可/未知', dailyRate: '5/350/3000', remarks: '律师，一般需审改' },
  { order: 'N/A', name: '王邃玲', type: '全部（中文较好）', quality: '78', cloudRev: '可/可', dailyRate: '5/500/4000', remarks: '注意优先安排中英项目' },
  { order: 'N/A', name: '曹柳云', type: '全部', quality: '75', cloudRev: '可/可', dailyRate: '5/500/4000', remarks: '一般需审改' },
  { order: '1', name: '梁昌金', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '5/500/4000', remarks: '一般需审改' },
  { order: '1', name: '熊建磊', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '-', remarks: '一般要审改' },
  { order: '1', name: '张留寰', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '-', remarks: '一般要审改' },
  { order: '1', name: '乔艳红', type: '全部', quality: '75', cloudRev: '可/可', dailyRate: '?/?/7000', remarks: '急稿可不改' }
])

// ==================== 班次表 ====================
const shiftTableData = ref([
  { shift: '8:30-18:00', layoutIt: '', client: '靖琳、楚翘', hr: '翠珍', translationProject: '伟琪' },
  { shift: '9:00-18:30', layoutIt: '运坚、胜辉、浚轩、裕林、晨旭', client: '瑞珠', hr: '雅然、辛建、文慧', translationProject: '以龙、志林' },
  { shift: '9:30-18:30', layoutIt: '', client: '家铭（9点半）', hr: '立溶、舒婷、宇琪', translationProject: '旷姣' },
  { shift: '10:30-20:00', layoutIt: '美霞、苗丹、黄萌', client: '舒倩(晚班)', hr: '紫霞', translationProject: '振中、孟花' },
  { shift: '13:30-21:30', layoutIt: '大杰', client: '烨珊', hr: '颖琦、少洁、菀筠', translationProject: '李娴' },
  { shift: '8:45~9:30', layoutIt: '泉哥、武哥（销售）', client: '少妃、陈佳、韵钰', hr: '', translationProject: 'Thomas' }
])

const leaveNotes = ref([
  '武哥周五（2月6日）12:00后请假',
  'Thomas周五（0206）14:00开始请假，7、8点在家办公',
  '陈佳0206上午请假，0206下午、0208-0210、0215在家办公共5天，0211-0214请假4天',
  '瑞珠2月11日-14日（周三至周六）休年假',
  '以龙2月11日-14日请假四天',
  '美霞0213-0214调休两天'
])

// ==================== 各部门人员任务数据 ====================
const deptPersonData = ref([])

function initDeptPersonData() {
  deptPersonData.value = [
    // 项目经理
    { name: '伟琪', dept: '项目经理', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '整理词汇并上传术语库（完成项目任务后再做）', projectNo: '爱彼', deadline: '' },
      { category: '直接项目任务', content: '1.2w跟进：舒婷派王珊娜，导出完整版译文、给颖琦派专检排版', projectNo: 'TP260205004', deadline: '2月9日9:30' },
      { category: '直接项目任务', content: '剩06：60w+，李鲁莎已回，已发惠喜专检+排版，周日下午6点回', projectNo: 'TP260115013', deadline: '周日下午6点' }
    ], fixedTasks: ['登记文件属性', '每月专检稽查（崔盼盼、水雅丽）'] },
    { name: '李娴', dept: '项目经理', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '待安排的分析、继续已安排的分析、跟进自己的项目', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '461份（961页）分析及跟进：英文转录已完成，其他语种继续转录', projectNo: 'TP251224018', deadline: '2026年3月22日17点' },
      { category: '直接项目任务', content: '2.5k，翠珍派沙柏霖，HR收稿时确认词汇及QA', projectNo: 'TP260205025', deadline: '2月9日10点' },
      { category: '直接项目任务', content: '2.8k跟进：11语种，各译员回稿后专检排版、验收', projectNo: 'TP260205016', deadline: '2月10日下午17点' }
    ], fixedTasks: ['每月专检稽查（戴欣然、刘惠喜）'] },
    { name: '孟花', dept: '项目经理', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '跟进：英语已派孙红艳检查反馈，繁体已派贺媛处理更新', projectNo: 'TP251224029', deadline: '尽快回' },
      { category: '直接项目任务', content: '大概15万中朝，MT后抽查、HR派数检、运坚还原、前中后抽查', projectNo: 'TP260202012', deadline: '2月8日晚18点' }
    ], fixedTasks: ['每月专检稽查（王雨菡、陈慧楠）', '整理词汇（待定）'] },

    // 翻译部
    { name: '少妃', dept: '翻译部', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '词汇整理+句式跟进等非项目任务、跟进自己的项目', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '译员开拓跟进：哈萨克/乌克兰/格鲁吉亚/阿塞拜疆语', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '项目安排：185份Excel 40w跟进、483页整理跟进、13w分析跟进', projectNo: 'TP260121020 等', deadline: '' }
    ], fixedTasks: [] },
    { name: '陈佳', dept: '翻译部', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '跟进招聘项目、安排邮件', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '10w（37份）跟进：文件15-29已派王婷修订，周六9点回', projectNo: 'TP260119005', deadline: '2月8日9:30/2月25日9:30' },
      { category: '直接项目任务', content: '尼泊尔/英译中 审改', projectNo: 'TP260204018', deadline: '2月6日15点' },
      { category: '直接项目任务', content: '3.6w 排版早上回，专检、基本检查，最后陈佳看看', projectNo: 'TP260202006', deadline: '2月6日17点' },
      { category: '直接项目任务', content: '8k，黎凤周五下午6点回，陈佳看看，颖琦派专检排版', projectNo: 'TP260205006', deadline: '2月8日12点' },
      { category: '直接项目任务', content: '19份，葡译中/德译中 审改', projectNo: 'TP260204020', deadline: '2月9日17点' }
    ], fixedTasks: ['银行词汇', '信实翻译 中译小语种 机翻引擎测试'] },
    { name: 'Thomas', dept: '翻译部', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '银行词汇', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '2.6k，彭霓周五早九点回，Thomas看看，瑞珠专检排版', projectNo: 'TP260204013', deadline: '2月6日中午12点' },
      { category: '直接项目任务', content: '4.6w（8k+1.2w+2.6w）跟进审改', projectNo: 'TP260203010', deadline: '2月6日12点/16:30' },
      { category: '直接项目任务', content: '4.5k 已审改，已一检，瑞珠二检及排版，最后Thomas验收', projectNo: 'TP260130008', deadline: '2月13日17点' },
      { category: '直接项目任务', content: '广州年鉴 中译英（母语）整体流程跟进', projectNo: 'TP260202007', deadline: '2月13日17点' }
    ], fixedTasks: [] },

    // 项目部
    { name: '旷姣', dept: '项目部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },

    // 客户部
    { name: '楚翘', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '6k排版已回，陈慧楠专检早八点半回，验收发客户', projectNo: 'TP260204003', deadline: '2月6日9点' },
      { category: '直接项目任务', content: '1.4k修订，黎凤早8:30回，检查修订及专检', projectNo: 'TP260205003', deadline: '2月6日9:30' },
      { category: '直接项目任务', content: '900修订，曹柳云早八点半回，检查修订及专检', projectNo: 'TP260205026', deadline: '2月6日11点' },
      { category: '直接项目任务', content: '王纵横 中译英（NAATI翻译）', projectNo: 'TP260130023', deadline: '2月6日中午12点' },
      { category: '直接项目任务', content: '吴先生 中译英（MTPE）', projectNo: 'TP260203015', deadline: '2月6日下午18点' },
      { category: '直接项目任务', content: '费雪尔 英译中（对照回稿）', projectNo: 'TP260204002', deadline: '2月6日下午18点' },
      { category: '直接项目任务', content: '胜美达 日译中', projectNo: 'TP260204019', deadline: '2月6日下午17点' },
      { category: '直接项目任务', content: '马小姐 英译中（代办澳洲海牙认证）', projectNo: 'TP260123012', deadline: '2月10日下午18点' }
    ], fixedTasks: [] },
    { name: '雅然', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '验收发客户', projectNo: 'TP260203005', deadline: '2月6日9:30' },
      { category: '直接项目任务', content: '验收发客户', projectNo: 'TP260205019', deadline: '2月6日9:30' },
      { category: '直接项目任务', content: '验收发客户', projectNo: 'TP260205028', deadline: '2月6日9:30' },
      { category: '直接项目任务', content: '专检排版', projectNo: 'TP260205027', deadline: '2月6日9:30' },
      { category: '直接项目任务', content: '王雨菡检查修订+专检，早九点回，看是否需调整排版', projectNo: 'TP260204015', deadline: '2月6日11点' }
    ], fixedTasks: [] },
    { name: '苗丹', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '杨雪周四晚十一点回，苗丹后续', projectNo: 'TP260205029', deadline: '2月6日11点' }
    ], fixedTasks: [] },
    { name: '家铭', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '已派曹柳云，早八点半回，专检排版', projectNo: 'TP251226015', deadline: '' },
      { category: '直接项目任务', content: '杨雪周四晚回，专检排版', projectNo: 'TP260205030', deadline: '2月6日中午12点' }
    ], fixedTasks: [] },
    { name: '黄萌', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '专检排版', projectNo: 'TP260204027', deadline: '2月6日11点' }
    ], fixedTasks: [] },
    { name: '武哥', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },
    { name: '靖琳', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },
    { name: '辛建', dept: '客户部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },

    // HR部
    { name: '韵钰', dept: 'HR部', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '词汇整理+句式跟进等非项目任务', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '合肥思达智数信息科技，评测项目，多语种翻译质检', projectNo: 'TP260202003', deadline: '2月28日23点' }
    ], fixedTasks: ['（暂停）项目专员培训资料调整', '（暂停）项目经理培训资料梳理、编写'] },
    { name: '立溶', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '舒婷', dept: 'HR部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '其他', content: '百度地图上架', projectNo: '', deadline: '' }
    ], fixedTasks: [] },
    { name: '宇琪', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '翠珍', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '紫霞', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '菀筠', dept: 'HR部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '其他', content: '爱企查上架', projectNo: '', deadline: '' }
    ], fixedTasks: [] },
    { name: '颖琦', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '少洁', dept: 'HR部', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },

    // 排版/IT部
    { name: '运坚', dept: '排版/IT部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },
    { name: '瑞珠', dept: '排版/IT部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '4k，已派王珊娜，早八点半回稿，专检排版', projectNo: 'TP260205022', deadline: '2月6日10点' },
      { category: '直接项目任务', content: '3.5k，已派廖伟燕修订，早九点回，检查修订及专检', projectNo: 'TP260205020', deadline: '2月6日11:30' },
      { category: '直接项目任务', content: '7k，柬译中（MTPE），专检排版', projectNo: 'TP260202014', deadline: '2月6日15点' },
      { category: '直接项目任务', content: '7k，已派陆素明，周五晚十点回，专检排版', projectNo: 'TP260205023', deadline: '2月9日9:30' }
    ], fixedTasks: ['每月专检稽查（梁承敏、沈佳佳）'] },
    { name: '大杰', dept: '排版/IT部', status: 'scheduled', tasks: [
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '大杰调整排版，运坚转HTML（吉利汽车客户反馈）', projectNo: '', deadline: '' }
    ], fixedTasks: ['每月专检稽查（贺媛、孙晓燕）'] },

    // 招聘项目
    { name: '振中', dept: '招聘项目', status: 'scheduled', tasks: [
      { category: '非直接项目任务', content: '非直接项目任务、固定项目任务', projectNo: '', deadline: '' },
      { category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }
    ], fixedTasks: [] },

    // 销售
    { name: '以龙', dept: '销售', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
    { name: '志林', dept: '销售', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] }
  ]
}

// ==================== 暂不安排 ====================
const notScheduledTasks = ref([
  {
    personName: '-',
    department: '翻译部',
    projectOrTask: '3w，李娴跟进：已派曹柳云9号早八点半回，Thomas审改，李娴导出完整版、给翠珍派一检二检，瑞珠排版，待安排内部细节检查',
    projectNo: 'TP260202016',
    remarks: '广州年鉴，中译英（母语），2月28日交'
  }
])

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
  id: '', scheduleDate: '', personName: '', department: '', taskCategory: '', projectOrTask: '', projectNo: '', deadline: '', timeSlot: '', status: 'scheduled', remarks: ''
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
    status: person.status
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
        // 编辑模式
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
    fetchTasks()
  })
}

function resetTaskForm() {
  Object.keys(taskForm).forEach((k) => { taskForm[k] = '' })
  taskForm.status = 'scheduled'
  taskFormRef.value?.resetFields()
}

function onDateChange() {
  fetchTasks()
}

// ==================== 初始化 ====================
onMounted(() => {
  initCurrentUserName()
  const today = new Date()
  scheduleDate.value = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-')
  initDeptPersonData()
  fetchTasks()
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
