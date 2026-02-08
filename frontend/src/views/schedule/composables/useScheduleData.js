import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getDefaultScheduleData } from '../scheduleDefaultData'

const SCHEDULE_STORAGE_PREFIX = 'work_schedule_'
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export function useScheduleData() {
  const scheduleDate = ref('')
  const deptPersonData = ref([])
  const notScheduledTasks = ref([])
  const pmRotationOrder = ref('伟琪 / 李娴 / 孟花')
  const shiftTableData = ref([])
  const leaveNotes = ref([])
  const urgentTableZhEn = ref([])
  const urgentTableEnZh = ref([])

  const weekdayLabel = computed(() => {
    if (!scheduleDate.value) return ''
    return WEEKDAYS[new Date(scheduleDate.value).getDay()]
  })

  function getScheduleFromStorage(date) {
    try {
      const raw = localStorage.getItem(SCHEDULE_STORAGE_PREFIX + date)
      if (!raw) return null
      return JSON.parse(raw)
    } catch {
      return null
    }
  }

  function saveScheduleForDate() {
    const date = scheduleDate.value
    if (!date) return
    try {
      const data = {
        deptPersonData: deptPersonData.value,
        notScheduledTasks: notScheduledTasks.value,
        pmRotationOrder: pmRotationOrder.value,
        shiftTableData: shiftTableData.value,
        leaveNotes: leaveNotes.value,
        urgentTableZhEn: urgentTableZhEn.value,
        urgentTableEnZh: urgentTableEnZh.value
      }
      localStorage.setItem(SCHEDULE_STORAGE_PREFIX + date, JSON.stringify(data))
    } catch (e) {
      console.error('保存工作安排失败', e)
    }
  }

  function loadScheduleForDate(date, onLoaded) {
    const stored = getScheduleFromStorage(date)
    const defaultData = getDefaultScheduleData()
    if (stored) {
      deptPersonData.value = stored.deptPersonData ?? defaultData.deptPersonData
      notScheduledTasks.value = stored.notScheduledTasks ?? defaultData.notScheduledTasks
      pmRotationOrder.value = stored.pmRotationOrder ?? defaultData.pmRotationOrder
      shiftTableData.value = stored.shiftTableData ?? defaultData.shiftTableData
      leaveNotes.value = stored.leaveNotes ?? defaultData.leaveNotes
      urgentTableZhEn.value = stored.urgentTableZhEn ?? defaultData.urgentTableZhEn
      urgentTableEnZh.value = stored.urgentTableEnZh ?? defaultData.urgentTableEnZh
    } else {
      deptPersonData.value = defaultData.deptPersonData
      notScheduledTasks.value = defaultData.notScheduledTasks
      pmRotationOrder.value = defaultData.pmRotationOrder
      shiftTableData.value = defaultData.shiftTableData
      leaveNotes.value = defaultData.leaveNotes
      urgentTableZhEn.value = defaultData.urgentTableZhEn
      urgentTableEnZh.value = defaultData.urgentTableEnZh
    }
    onLoaded?.()
  }

  function getYesterdayDate(dateStr) {
    const d = new Date(dateStr)
    d.setDate(d.getDate() - 1)
    return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
  }

  function copyFromYesterday() {
    const yesterday = getYesterdayDate(scheduleDate.value)
    const data = getScheduleFromStorage(yesterday)
    if (!data) {
      ElMessage.warning('昨日无安排数据可复制，请先保存昨日安排或选择其他日期')
      return
    }
    const defaultData = getDefaultScheduleData()
    deptPersonData.value = data.deptPersonData ?? defaultData.deptPersonData
    notScheduledTasks.value = data.notScheduledTasks ?? defaultData.notScheduledTasks
    pmRotationOrder.value = data.pmRotationOrder ?? defaultData.pmRotationOrder
    shiftTableData.value = data.shiftTableData ?? defaultData.shiftTableData
    leaveNotes.value = data.leaveNotes ?? defaultData.leaveNotes
    urgentTableZhEn.value = data.urgentTableZhEn ?? defaultData.urgentTableZhEn
    urgentTableEnZh.value = data.urgentTableEnZh ?? defaultData.urgentTableEnZh
    saveScheduleForDate()
    ElMessage.success('已从昨日复制并保存为当日安排')
  }

  return {
    scheduleDate,
    weekdayLabel,
    deptPersonData,
    notScheduledTasks,
    pmRotationOrder,
    shiftTableData,
    leaveNotes,
    urgentTableZhEn,
    urgentTableEnZh,
    getScheduleFromStorage,
    saveScheduleForDate,
    loadScheduleForDate,
    getYesterdayDate,
    copyFromYesterday
  }
}
