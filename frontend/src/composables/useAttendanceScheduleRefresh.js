import { onMounted, onBeforeUnmount } from 'vue'
import { subscribe } from '@/utils/realtimeSocket'

// 班次正式生效后，考勤及关联账本统一失效，沿用调用方的取消和序号保护。
export function useAttendanceScheduleRefresh(refresh) {
  let unsubscribe
  onMounted(() => { unsubscribe = subscribe('attendance_schedule_changed', refresh) })
  onBeforeUnmount(() => { unsubscribe?.() })
}
