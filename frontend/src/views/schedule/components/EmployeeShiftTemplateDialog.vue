<template>
  <el-dialog
    v-model="dialogVisible"
    :title="`${employee?.name || employee?.full_name || employee?.username || '员工'} · 常规排班`"
    width="min(820px, calc(100vw - 32px))"
    top="5vh"
    class="shift-template-dialog"
    @open="loadTemplate"
  >
    <AppForm label-width="96px">
      <el-form-item label="生效周">
        <el-date-picker
          v-model="effectiveFrom"
          type="date"
          value-format="YYYY-MM-DD"
          format="YYYY-MM-DD"
          placeholder="请选择周一"
        />
        <span class="form-hint">必须选择周一；新版本不会改变此前历史排班。</span>
      </el-form-item>
      <el-form-item label="固定班次">
        <el-switch v-model="lockEnabled" active-text="已锁定" inactive-text="未锁定" />
        <span class="form-hint">锁定后，单日临时调整必须填写原因。</span>
      </el-form-item>
      <el-form-item v-if="lockEnabled !== initialLocked || lockEnabled" label="锁定说明">
        <el-input v-model="lockReason" maxlength="500" show-word-limit placeholder="请填写锁定或解锁原因" />
      </el-form-item>
    </AppForm>

    <section class="workday-quick-set">
      <div class="workday-quick-set__header">
        <div>
          <strong>周一至周五统一设置</strong>
          <p>一次应用到五个工作日，应用后仍可在下方逐日微调。</p>
        </div>
        <el-tag v-if="workdayUniform" type="success" effect="plain">当前工作日一致</el-tag>
        <el-tag v-else type="info" effect="plain">当前工作日不一致</el-tag>
      </div>
      <div class="workday-quick-set__controls">
        <el-select
          v-model="workdayDraft.shift_code"
          :disabled="initialLocked && lockEnabled"
          placeholder="选择工作日统一班次"
          @change="applyPreset(workdayDraft)"
        >
          <el-option
            v-for="option in workdayPresets"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <template v-if="workdayDraft.shift_code === 'custom'">
          <el-time-select v-model="workdayDraft.start_time" start="06:00" step="00:15" end="23:45" placeholder="开始" :disabled="initialLocked && lockEnabled" />
          <el-time-select v-model="workdayDraft.end_time" start="06:00" step="00:15" end="23:45" placeholder="结束" :disabled="initialLocked && lockEnabled" />
        </template>
        <el-button
          type="primary"
          :disabled="!workdayDraft.shift_code || (initialLocked && lockEnabled)"
          @click="applyWorkdaySchedule"
        >应用到周一至周五</el-button>
        <el-button :disabled="initialLocked && lockEnabled" @click="copyMondayToWorkdays">复制周一班次</el-button>
      </div>
    </section>

    <el-table :data="days" border size="small" v-loading="loading">
      <el-table-column label="星期" width="90">
        <template #default="{ row }">{{ weekdayLabels[row.weekday - 1] }}</template>
      </el-table-column>
      <el-table-column label="常规班次" min-width="230">
        <template #default="{ row }">
          <el-select v-model="row.shift_code" :disabled="initialLocked && lockEnabled" style="width: 100%" @change="applyPreset(row)">
            <el-option
              v-for="option in optionsForDay(row.weekday)"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="自定义开始" width="150">
        <template #default="{ row }">
          <el-time-select
            v-model="row.start_time"
            start="06:00"
            step="00:15"
            end="23:45"
            :disabled="row.shift_code !== 'custom' || (initialLocked && lockEnabled)"
            style="width: 100%"
          />
        </template>
      </el-table-column>
      <el-table-column label="自定义结束" width="150">
        <template #default="{ row }">
          <el-time-select
            v-model="row.end_time"
            start="06:00"
            step="00:15"
            end="23:45"
            :disabled="row.shift_code !== 'custom' || (initialLocked && lockEnabled)"
            style="width: 100%"
          />
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveTemplate">保存模板</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getEmployeeShiftTemplate, saveEmployeeShiftLock, saveEmployeeShiftTemplate } from '@/api/schedule'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  employee: { type: Object, default: null },
  referenceDate: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const presets = [
  { value: 'early_early', label: '早早班 08:30–18:00', start: '08:30', end: '18:00' },
  { value: 'early', label: '早班 09:00–18:30', start: '09:00', end: '18:30' },
  { value: 'late', label: '晚班 10:30–20:00', start: '10:30', end: '20:00' },
  { value: 'late_late', label: '晚晚班 13:30–21:30', start: '13:30', end: '21:30' },
  { value: 'weekend_duty', label: '周末值班 09:30–18:00', start: '09:30', end: '18:00' },
  { value: 'custom', label: '自定义时间' },
  { value: 'off', label: '休息' },
  { value: 'unassigned', label: '未安排' }
]
const workdayPresets = presets.filter(option => option.value !== 'weekend_duty')

const loading = ref(false)
const saving = ref(false)
const effectiveFrom = ref('')
const days = ref([])
const lockEnabled = ref(false)
const initialLocked = ref(false)
const lockReason = ref('')
const workdayDraft = reactive({ shift_code: '', start_time: null, end_time: null })
const workdayUniform = computed(() => {
  const workdays = days.value.filter(day => day.weekday <= 5)
  if (workdays.length !== 5) return false
  const first = workdays[0]
  return workdays.every(day => (
    day.shift_code === first.shift_code
    && day.start_time === first.start_time
    && day.end_time === first.end_time
  ))
})

function getMonday(value) {
  const base = value ? new Date(`${value}T00:00:00`) : new Date()
  const day = base.getDay() || 7
  base.setDate(base.getDate() - day + 1)
  return `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, '0')}-${String(base.getDate()).padStart(2, '0')}`
}

function defaultDays() {
  return Array.from({ length: 7 }, (_, index) => ({
    weekday: index + 1,
    shift_code: index >= 5 ? 'off' : 'unassigned',
    start_time: null,
    end_time: null
  }))
}

function optionsForDay(weekday) {
  return presets.filter(option => option.value !== 'weekend_duty' || weekday >= 6)
}

function applyPreset(row) {
  const preset = presets.find(item => item.value === row.shift_code)
  row.start_time = preset?.start || null
  row.end_time = preset?.end || null
}

function syncWorkdayDraft() {
  const workdays = days.value.filter(day => day.weekday <= 5)
  if (workdays.length !== 5 || !workdayUniform.value) {
    Object.assign(workdayDraft, { shift_code: '', start_time: null, end_time: null })
    return
  }
  const first = workdays[0]
  Object.assign(workdayDraft, {
    shift_code: first.shift_code,
    start_time: first.start_time,
    end_time: first.end_time
  })
}

function applyWorkdaySchedule() {
  if (workdayDraft.shift_code === 'custom' && (
    !workdayDraft.start_time
    || !workdayDraft.end_time
    || workdayDraft.end_time <= workdayDraft.start_time
  )) {
    ElMessage.warning('请完整填写工作日自定义时间，且结束时间必须晚于开始时间')
    return
  }
  days.value.forEach(day => {
    if (day.weekday <= 5) {
      Object.assign(day, {
        shift_code: workdayDraft.shift_code,
        start_time: workdayDraft.start_time,
        end_time: workdayDraft.end_time
      })
    }
  })
  ElMessage.success('已应用到周一至周五，可继续逐日微调')
}

function copyMondayToWorkdays() {
  const monday = days.value.find(day => day.weekday === 1)
  if (!monday) return
  Object.assign(workdayDraft, {
    shift_code: monday.shift_code,
    start_time: monday.start_time,
    end_time: monday.end_time
  })
  applyWorkdaySchedule()
}

async function loadTemplate() {
  if (!props.employee?.id && !props.employee?.user_id) return
  loading.value = true
  try {
    const data = await getEmployeeShiftTemplate(props.employee.id || props.employee.user_id, props.referenceDate)
    effectiveFrom.value = data.effective_from || getMonday(props.referenceDate)
    days.value = (data.days || defaultDays()).map(day => ({ ...day }))
    syncWorkdayDraft()
    lockEnabled.value = Boolean(data.is_locked)
    initialLocked.value = Boolean(data.is_locked)
    lockReason.value = data.lock_reason || ''
  } catch (error) {
    effectiveFrom.value = getMonday(props.referenceDate)
    days.value = defaultDays()
    syncWorkdayDraft()
    lockEnabled.value = false
    initialLocked.value = false
    lockReason.value = ''
    ElMessage.error(error.detail || '读取常规排班失败')
  } finally {
    loading.value = false
  }
}

async function saveTemplate() {
  if (!effectiveFrom.value) {
    ElMessage.warning('请选择生效周')
    return
  }
  const customInvalid = days.value.some(day => day.shift_code === 'custom' && (!day.start_time || !day.end_time || day.end_time <= day.start_time))
  if (customInvalid) {
    ElMessage.warning('请完整填写自定义班次，且结束时间必须晚于开始时间')
    return
  }
  if ((lockEnabled.value || lockEnabled.value !== initialLocked.value) && !lockReason.value.trim()) {
    ElMessage.warning('请填写锁定或解锁原因')
    return
  }
  saving.value = true
  try {
    const userId = props.employee.id || props.employee.user_id
    if (initialLocked.value && !lockEnabled.value) {
      await saveEmployeeShiftLock(userId, { effective_from: effectiveFrom.value, is_locked: false, reason: lockReason.value.trim() })
    }
    if (!initialLocked.value || !lockEnabled.value) {
      await saveEmployeeShiftTemplate(userId, {
        effective_from: effectiveFrom.value,
        days: days.value.map(({ weekday, shift_code, start_time, end_time }) => ({ weekday, shift_code, start_time, end_time }))
      })
    }
    if ((!initialLocked.value && lockEnabled.value) || (initialLocked.value && lockEnabled.value && lockReason.value.trim())) {
      await saveEmployeeShiftLock(userId, { effective_from: effectiveFrom.value, is_locked: true, reason: lockReason.value.trim() })
    }
    ElMessage.success('常规排班已保存')
    dialogVisible.value = false
    emit('saved')
  } catch (error) {
    ElMessage.error(error.detail || '保存常规排班失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-hint { margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.workday-quick-set { margin-bottom: 14px; padding: 14px; border: 1px solid var(--el-color-primary-light-7); border-radius: 8px; background: var(--el-color-primary-light-9); }
.workday-quick-set__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.workday-quick-set__header p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.workday-quick-set__controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.workday-quick-set__controls > .el-select { width: 230px; }
.workday-quick-set__controls > .el-time-select { width: 126px; }
:global(.shift-template-dialog) { max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
:global(.shift-template-dialog .el-dialog__header),
:global(.shift-template-dialog .el-dialog__footer) { flex: none; }
:global(.shift-template-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.shift-template-dialog .el-dialog__footer) { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-extra-light); }
@media (max-width: 720px) {
  .form-hint { display: block; margin: 6px 0 0; }
  .workday-quick-set__header { flex-direction: column; }
  .workday-quick-set__controls > * { width: 100% !important; }
}
</style>
