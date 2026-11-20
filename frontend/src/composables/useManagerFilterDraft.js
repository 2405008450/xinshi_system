import { ref, watch } from 'vue'

export function useManagerFilterDraft(getApplied) {
  const managerPickerVisible = ref(false)
  const managerDraftScope = ref('all')
  const managerDraftIds = ref([])

  function resetManagerDraft() {
    const { only_mine, manager_ids } = getApplied()
    managerDraftIds.value = [...(manager_ids || [])]
    managerDraftScope.value = only_mine ? 'self' : managerDraftIds.value.length ? 'name' : 'all'
  }

  watch(() => JSON.stringify(getApplied()), resetManagerDraft, { immediate: true })

  function cancelManagerPicker() {
    resetManagerDraft()
    managerPickerVisible.value = false
  }

  function getManagerSelection() {
    const ids = managerDraftScope.value === 'name' ? [...managerDraftIds.value] : []
    const scope = managerDraftScope.value === 'self' ? 'self' : ids.length ? 'name' : 'all'
    return { scope, ids }
  }

  return { managerPickerVisible, managerDraftScope, managerDraftIds, resetManagerDraft, cancelManagerPicker, getManagerSelection }
}
