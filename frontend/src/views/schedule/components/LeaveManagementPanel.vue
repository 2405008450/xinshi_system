<template>
  <div class="leave-management">
    <div class="toolbar">
      <el-input
        v-model="filters.keyword"
        clearable
        placeholder="员工姓名或用户名"
        style="width: 210px"
        @input="onKeywordInput"
        @clear="runQuery"
        @keyup.enter="runQuery"
      />
      <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 140px" @change="runQuery">
        <el-option label="请假中" value="active" />
        <el-option label="即将请假" value="upcoming" />
        <el-option label="已结束" value="past" />
      </el-select>
      <el-date-picker
        v-model="filters.range"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        value-format="YYYY-MM-DDTHH:mm:ss"
        style="width: 340px"
        @change="runQuery"
        format="YYYY-MM-DD HH:mm"
        time-format="HH:mm"
        :show-now="true"
        :show-confirm="true"
        :show-footer="true"
      />
      <el-button type="primary" @click="runQuery">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <el-button v-if="canEdit" type="primary" class="add-button" @click="openCreate">新增请假</el-button>
    </div>

    <el-table :data="records" border size="small" v-loading="loading">
      <el-table-column prop="employee_name" label="员工" width="120" fixed="left" />
      <el-table-column prop="department" label="部门" width="120">
        <template #default="{ row }">{{ row.department || '未分部门' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="开始时间" width="170"><template #default="{ row }">{{ formatDateTime(row.start_date) }}</template></el-table-column>
      <el-table-column label="结束时间" width="170"><template #default="{ row }">{{ formatDateTime(row.end_date) }}</template></el-table-column>
      <el-table-column prop="leave_type" label="类型" width="100" />
      <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="canEdit" label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确定删除该条请假记录？" @confirm="removeRecord(row.id)">
            <template #reference><el-button type="danger" link size="small">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑请假记录' : '新增请假记录'" width="min(560px, calc(100vw - 32px))" top="5vh" class="leave-form-dialog" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="员工" prop="employee_id">
          <el-select v-model="form.employee_id" filterable placeholder="请选择员工" style="width: 100%">
            <el-option v-for="user in staff" :key="user.id" :label="`${user.name}${user.dept ? `（${user.dept}）` : ''}`" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="start_date"><el-date-picker v-model="form.start_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item>
        <el-form-item label="结束时间" prop="end_date"><el-date-picker v-model="form.end_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="form.leave_type" style="width: 100%"><el-option v-for="type in leaveTypes" :key="type" :label="type" :value="type" /></el-select></el-form-item>
        <el-form-item label="原因"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createLeave, deleteLeave, getLeaveRecords, updateLeave } from '@/api/leave'
import { getStaffList } from '@/api/schedule'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

defineProps({ canEdit: { type: Boolean, default: false } })
const leaveTypes = ['请假', '调休', '事假', '病假', '年假']
const loading = ref(false)
const saving = ref(false)
const records = ref([])
const staff = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const filters = reactive({ keyword: '', status: '', range: [] })
const form = reactive({ employee_id: '', start_date: '', end_date: '', leave_type: '请假', reason: '' })
const rules = {
  employee_id: [{ required: true, message: '请选择员工', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}
let debounceTimer = null
let requestController = null
let requestSequence = 0

function statusLabel(value) { return ({ active: '请假中', upcoming: '即将请假', past: '已结束' })[value] || value }
function statusType(value) { return value === 'active' ? 'danger' : value === 'upcoming' ? 'warning' : 'info' }

async function loadRecords() {
  requestController?.abort()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const params = {
      employee_keyword: filters.keyword.trim() || undefined,
      status_filter: filters.status || undefined,
      start_date: filters.range?.[0] || undefined,
      end_date: filters.range?.[1] || undefined
    }
    const result = await getLeaveRecords(params, requestController.signal)
    if (sequence === requestSequence) records.value = Array.isArray(result) ? result : []
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED' && sequence === requestSequence) ElMessage.error(error.detail || '读取请假记录失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
function runQuery() { clearTimeout(debounceTimer); loadRecords() }
function onKeywordInput(value) { clearTimeout(debounceTimer); if (!value) runQuery(); else debounceTimer = setTimeout(loadRecords, 400) }
function resetFilters() { Object.assign(filters, { keyword: '', status: '', range: [] }); runQuery() }
function resetForm() { editingId.value = null; Object.assign(form, { employee_id: '', start_date: '', end_date: '', leave_type: '请假', reason: '' }); formRef.value?.clearValidate() }
function openCreate() { resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { employee_id: row.employee_id, start_date: row.start_date, end_date: row.end_date, leave_type: row.leave_type || '请假', reason: row.reason || '' }); dialogVisible.value = true }

async function submit() {
  try { await formRef.value?.validate() } catch { return }
  if (form.end_date <= form.start_date) return ElMessage.warning('结束时间必须晚于开始时间')
  saving.value = true
  try {
    if (editingId.value) await updateLeave(editingId.value, form)
    else await createLeave(form)
    ElMessage.success('请假记录已保存')
    dialogVisible.value = false
    await loadRecords()
  } catch (error) { ElMessage.error(error.detail || '保存请假记录失败') }
  finally { saving.value = false }
}
async function removeRecord(id) {
  try { await deleteLeave(id); ElMessage.success('请假记录已删除'); await loadRecords() }
  catch (error) { ElMessage.error(error.detail || '删除请假记录失败') }
}

onMounted(async () => {
  const [staffResult] = await Promise.allSettled([getStaffList(), loadRecords()])
  staff.value = staffResult.status === 'fulfilled' ? staffResult.value : []
})
onBeforeUnmount(() => { clearTimeout(debounceTimer); requestController?.abort() })
</script>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
.add-button { margin-left: auto; }
:global(.leave-form-dialog) { max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
:global(.leave-form-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.leave-form-dialog .el-dialog__footer) { flex: none; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-extra-light); }
@media (max-width: 720px) { .toolbar > * { width: 100% !important; } .add-button { margin-left: 0; } }
</style>
