<template>
  <el-card class="compact-list-card">
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
          <el-button v-if="canEdit && ['departments', 'not_scheduled'].includes(activeTab)" type="primary" @click="handleAddTask">新增任务</el-button>
          <el-button v-if="canEdit && ['departments', 'not_scheduled'].includes(activeTab)" @click="copyFromYesterday">复制昨日工作安排</el-button>
        </div>
      </div>
    </template>

    <!-- 顶层分类 Tabs（管理页：不含「我的任务」，普通用户请使用「我的工作台」/workbench） -->
    <el-tabs v-model="activeTab" type="border-card">

      <el-tab-pane label="内部排班" name="employee_shifts">
        <EmployeeShiftPanel v-model:selected-date="scheduleDate" :can-edit="canEdit" />
      </el-tab-pane>

      <el-tab-pane label="请假管理" name="leave" lazy>
        <LeaveManagementPanel :can-edit="canEdit" />
      </el-tab-pane>

      <!-- ====== Tab: 总览 ====== -->
      <el-tab-pane label="总览" name="overview" lazy>
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
      <el-tab-pane label="译员安排" name="translator" lazy>
        <TranslatorSchedulePanel :selected-date="scheduleDate" :can-edit="canEdit" />
      </el-tab-pane>

      <!-- ====== Tab: 各部门工作安排 ====== -->
      <el-tab-pane label="各部门安排" name="departments" lazy>
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
                    <el-table-column prop="deadline" label="交稿时间" width="140" show-overflow-tooltip>
                      <template #default="{ row }">{{ formatDateTimeMinute(row.deadline) }}</template>
                    </el-table-column>
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
      <el-tab-pane label="暂不安排" name="not_scheduled" lazy>
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
      
    </el-tabs>

    <!-- 新增/编辑任务弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" @close="resetTaskForm">
      <AppForm ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="100px">
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
      </AppForm>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">确定</el-button>
      </template>
    </el-dialog>

  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { canEditSchedule } from '@/utils/permission'
import { formatDateTimeMinute } from '@/utils/dateTime'
import { getSchedule, saveSchedule, copySchedule, getStaffList } from '@/api/schedule'
import { DEPARTMENT_NAMES, normalizeDepartment } from '@/constants/departments'
import EmployeeShiftPanel from './components/EmployeeShiftPanel.vue'
import TranslatorSchedulePanel from './components/TranslatorSchedulePanel.vue'
import LeaveManagementPanel from './components/LeaveManagementPanel.vue'

// ==================== 常量 ====================
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const DEPARTMENTS = DEPARTMENT_NAMES.map((name) => ({ key: name, label: name }))

// ==================== 状态 ====================
const currentDate = new Date()
const scheduleDate = ref([
  currentDate.getFullYear(),
  String(currentDate.getMonth() + 1).padStart(2, '0'),
  String(currentDate.getDate()).padStart(2, '0')
].join('-'))
const activeTab = ref('employee_shifts')
const activeDept = ref('项目经理')
const openPersons = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增任务')
const taskFormRef = ref(null)


const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  return WEEKDAYS[new Date(scheduleDate.value).getDay()]
})

/** 当前用户是否有编辑排班的权限（项目经理、超管） */
const canEdit = computed(() => canEditSchedule())

const pmRotationOrder = ref('伟琪 / 李娴 / 孟花')

const loadedScheduleDate = ref('')
// ==================== 各部门人员任务数据 ====================
const deptPersonData = ref([])

function normalizeTaskForUi(task) {
  const source = task || {}
  return {
    category: source.category || '其他',
    content: source.content ?? source.projectName ?? source.project_name ?? '',
    projectNo: source.projectNo ?? source.orderNo ?? source.order_no ?? '',
    deadline: source.deadline ?? source.customerDeadlineTime ?? source.customer_deadline_time ?? '',
    projectStatus: source.projectStatus ?? source.project_status ?? ''
  }
}

function normalizeDeptPersonDataForUi(data) {
  if (!Array.isArray(data)) return []
  return data.map((person) => ({
    name: person?.name || '',
    dept: normalizeDepartment(person?.dept),
    status: person?.status || 'scheduled',
    tasks: Array.isArray(person?.tasks) ? person.tasks.map(normalizeTaskForUi) : [],
    fixedTasks: Array.isArray(person?.fixedTasks)
      ? person.fixedTasks
      : (Array.isArray(person?.fixed_tasks) ? person.fixed_tasks : [])
  }))
}

function normalizeNotScheduledTasksForUi(data) {
  if (!Array.isArray(data)) return []
  return data.map((item) => ({
    personName: item?.personName ?? item?.person_name ?? '',
    department: normalizeDepartment(item?.department),
    projectOrTask: item?.projectOrTask ?? item?.projectName ?? item?.project_name ?? '',
    projectNo: item?.projectNo ?? item?.orderNo ?? item?.order_no ?? '',
    deadline: item?.deadline ?? item?.customerDeadlineTime ?? item?.customer_deadline_time ?? '',
    remarks: item?.remarks ?? ''
  }))
}

function serializeTaskForApi(task) {
  const source = task || {}
  return {
    category: source.category || '其他',
    project_name: source.content ?? source.projectName ?? source.project_name ?? '',
    order_no: source.projectNo ?? source.orderNo ?? source.order_no ?? '',
    customer_deadline_time: source.deadline ?? source.customerDeadlineTime ?? source.customer_deadline_time ?? '',
    project_status: source.projectStatus ?? source.project_status ?? ''
  }
}

function serializeDeptPersonDataForApi(data) {
  if (!Array.isArray(data)) return []
  return data.map((person) => ({
    name: person?.name || '',
    dept: person?.dept || '',
    status: person?.status || 'scheduled',
    tasks: Array.isArray(person?.tasks) ? person.tasks.map(serializeTaskForApi) : [],
    fixed_tasks: Array.isArray(person?.fixedTasks)
      ? person.fixedTasks
      : (Array.isArray(person?.fixed_tasks) ? person.fixed_tasks : [])
  }))
}

function serializeNotScheduledTasksForApi(data) {
  if (!Array.isArray(data)) return []
  return data.map((item) => ({
    person_name: item?.personName ?? item?.person_name ?? '',
    department: item?.department ?? '',
    project_name: item?.projectOrTask ?? item?.projectName ?? item?.project_name ?? '',
    order_no: item?.projectNo ?? item?.orderNo ?? item?.order_no ?? '',
    customer_deadline_time: item?.deadline ?? item?.customerDeadlineTime ?? item?.customer_deadline_time ?? '',
    remarks: item?.remarks ?? ''
  }))
}

/**
 * 从后端 API 动态拉取员工列表，生成排班初始模板
 */
async function fetchDefaultDeptPersonData() {
  try {
    const staffList = await getStaffList()
    if (Array.isArray(staffList) && staffList.length > 0) {
      return staffList.map((s) => ({
        name: s.name,
        dept: normalizeDepartment(s.dept),
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

async function initDeptPersonData() {
  deptPersonData.value = await fetchDefaultDeptPersonData()
}

/** 获取某日工作安排的默认数据（用于无存储时的初始模板，从数据库动态生成） */
async function getDefaultScheduleData() {
  const defaultStaff = await fetchDefaultDeptPersonData()
  return {
    deptPersonData: defaultStaff,
    notScheduledTasks: [],
    pmRotationOrder: ''
  }
}

async function saveScheduleForDate() {
  const date = scheduleDate.value
  if (!date) return
  try {
    const data = {
      dept_person_data: serializeDeptPersonDataForApi(deptPersonData.value),
      not_scheduled_tasks: serializeNotScheduledTasksForApi(notScheduledTasks.value),
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
    deptPersonData: [], notScheduledTasks: [], pmRotationOrder: ''
  }
  const stored = storedResult.status === 'fulfilled' ? storedResult.value : null

  if (stored) {
    deptPersonData.value = normalizeDeptPersonDataForUi(stored.dept_person_data ?? defaultData.deptPersonData)
    notScheduledTasks.value = normalizeNotScheduledTasksForUi(stored.not_scheduled_tasks ?? defaultData.notScheduledTasks)
    pmRotationOrder.value = stored.pm_rotation_order ?? defaultData.pmRotationOrder
  } else {
    // 404 或网络错误，用默认数据
    deptPersonData.value = defaultData.deptPersonData
    deptPersonData.value = normalizeDeptPersonDataForUi(deptPersonData.value)
    notScheduledTasks.value = normalizeNotScheduledTasksForUi(defaultData.notScheduledTasks)
    pmRotationOrder.value = defaultData.pmRotationOrder
  }
}

// ==================== 暂不安排 ====================
const notScheduledTasks = ref([])

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

async function ensureActiveTabData() {
  const tasks = []
  if (['overview', 'departments', 'not_scheduled'].includes(activeTab.value)) {
    if (loadedScheduleDate.value !== scheduleDate.value) {
      tasks.push(loadScheduleForDate(scheduleDate.value).then(() => { loadedScheduleDate.value = scheduleDate.value }))
    }
  }
  await Promise.allSettled(tasks)
}

function onDateChange() {
  loadedScheduleDate.value = ''
  ensureActiveTabData()
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
watch(activeTab, ensureActiveTabData)
onMounted(ensureActiveTabData)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.leave-filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
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
