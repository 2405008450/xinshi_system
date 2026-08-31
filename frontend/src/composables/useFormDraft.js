import { ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'

// Vue reactive Proxy 不能直接 structuredClone；表单草稿只包含可 JSON 化字段。
const clone = (value) => JSON.parse(JSON.stringify(value))

const currentUserKey = () => (
  localStorage.getItem('user_id')
  || localStorage.getItem('user_name')
  || 'anonymous'
)

/**
 * 弹窗表单草稿缓存。
 *
 * 草稿仅保留在当前浏览器会话中，并按模块、用户、创建/记录 ID 隔离。
 * 关闭弹窗会保留草稿；保存成功或用户明确放弃恢复时才清除。
 */
export const useFormDraft = ({
  namespace,
  form,
  createDefault,
  formRef,
  applyDraft,
  legacyStorageKeys = [],
}) => {
  const storageKey = `form-drafts:${namespace}:${currentUserKey()}`
  const activeDraftKey = ref('')
  const savingEnabled = ref(false)

  const readDrafts = () => {
    try {
      let raw = sessionStorage.getItem(storageKey)
      if (!raw) {
        const legacyKey = legacyStorageKeys.find((key) => sessionStorage.getItem(key))
        if (legacyKey) {
          raw = sessionStorage.getItem(legacyKey)
          sessionStorage.setItem(storageKey, raw)
          sessionStorage.removeItem(legacyKey)
        }
      }
      const value = JSON.parse(raw || '{}')
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
    } catch {
      sessionStorage.removeItem(storageKey)
      return {}
    }
  }

  const writeDrafts = (drafts) => {
    try {
      if (Object.keys(drafts).length) sessionStorage.setItem(storageKey, JSON.stringify(drafts))
      else sessionStorage.removeItem(storageKey)
    } catch {
      // 存储空间不足或浏览器禁用会话存储时，不影响正常填写和提交。
    }
  }

  const removeDraft = (key = activeDraftKey.value) => {
    if (!key) return
    const drafts = readDrafts()
    delete drafts[key]
    writeDrafts(drafts)
  }

  const saveActiveDraft = () => {
    if (!savingEnabled.value || !activeDraftKey.value) return
    const drafts = readDrafts()
    drafts[activeDraftKey.value] = {
      form: clone(form),
      savedAt: new Date().toISOString(),
    }
    writeDrafts(drafts)
  }

  const beginDraft = async (key) => {
    savingEnabled.value = false
    activeDraftKey.value = key
    const draft = readDrafts()[key]

    if (draft?.form) {
      try {
        await ElMessageBox.confirm(
          '检测到该表单有未提交的草稿，是否恢复上次填写的内容？',
          '恢复未提交草稿',
          {
            confirmButtonText: '恢复草稿',
            cancelButtonText: '放弃草稿',
            type: 'info',
            showClose: false,
            closeOnClickModal: false,
            closeOnPressEscape: false,
          },
        )
        const restored = clone(draft.form)
        if (applyDraft) applyDraft(restored)
        else Object.assign(form, createDefault(), restored)
      } catch {
        removeDraft(key)
      }
    }

    savingEnabled.value = true
    formRef?.value?.clearValidate?.()
  }

  const pauseDraft = () => {
    savingEnabled.value = false
    activeDraftKey.value = ''
  }

  const clearDraft = () => {
    savingEnabled.value = false
    removeDraft()
    activeDraftKey.value = ''
  }

  watch(form, saveActiveDraft, { deep: true, flush: 'sync' })

  return { beginDraft, pauseDraft, clearDraft, removeDraft }
}
