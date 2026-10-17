import { computed, reactive, ref } from 'vue'
import { businessDateTimeInputValue } from '../utils/dateTime.js'

// 两类项目录入各自保存表单与来源，切换模式只改变当前引用。
export function useAnnotationProgressEntryDrafts({ now = businessDateTimeInputValue } = {}) {
  const mode = ref('progress')
  const drafts = reactive({ progress: {}, status: {} })
  const clear = (targetMode, projectStatus = '') => {
    const form = { projectStatus: targetMode === 'progress' ? projectStatus : '', effectiveOn: now(), changeNote: '' }
    Object.assign(drafts[targetMode], { form, baseline: { ...form }, source: null, stageKey: '' })
  }
  const reset = (projectStatus = '') => {
    clear('progress', projectStatus); clear('status'); mode.value = 'progress'
  }
  reset()
  const form = computed(() => drafts[mode.value].form)
  const source = computed({ get: () => drafts[mode.value].source, set: (value) => { drafts[mode.value].source = value } })
  const stageKey = computed({ get: () => drafts[mode.value].stageKey, set: (value) => { drafts[mode.value].stageKey = value } })
  const hasDraft = (targetMode) => {
    const draft = drafts[targetMode]
    return Boolean(draft.source || Object.keys(draft.baseline).some((key) => draft.form[key] !== draft.baseline[key]))
  }
  // 首次详情加载只修正默认状态，不覆盖用户已选择的历史节点。
  const setInitialProjectStatus = (projectStatus) => {
    const draft = drafts.progress
    if (draft.form.projectStatus === draft.baseline.projectStatus && !draft.stageKey) draft.form.projectStatus = projectStatus
    draft.baseline.projectStatus = projectStatus
  }
  return { mode, form, source, stageKey, drafts, clear, reset, hasDraft, setInitialProjectStatus }
}
