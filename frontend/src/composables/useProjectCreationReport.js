import { onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

export function useProjectCreationReport(projectType, { restore = true } = {}) {
  const pendingReportId = ref('')
  let afterReport
  let active = true
  async function restorePending() {
    try {
      const rows = await api.get(`/projects/${projectType}/work-report/pending`)
      if (active && !pendingReportId.value) pendingReportId.value = rows[0]?.id || ''
    } catch (error) {
      if (active) ElMessage.error(getLocalizedErrorMessage(error, '待填写工作报告加载失败，请刷新重试'))
    }
  }
  function requireReport(project) { pendingReportId.value = project.id }
  function afterReportSaved(callback) {
    if (pendingReportId.value) afterReport = callback
    else callback()
  }
  async function completeReport() {
    pendingReportId.value = ''
    const callback = afterReport
    afterReport = undefined
    callback?.()
    if (restore) await restorePending()
  }
  function beforeUnload(event) {
    if (pendingReportId.value) { event.preventDefault(); event.returnValue = '' }
  }
  onBeforeRouteLeave(() => {
    if (!pendingReportId.value) return true
    ElMessage.warning('请先填写并保存本次新增项目工作报告')
    return false
  })
  onMounted(() => {
    window.addEventListener('beforeunload', beforeUnload)
    if (restore) void restorePending()
  })
  onBeforeUnmount(() => { active = false; window.removeEventListener('beforeunload', beforeUnload) })
  return { pendingReportId, requireReport, afterReportSaved, completeReport }
}
