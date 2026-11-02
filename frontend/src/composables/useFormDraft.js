import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {chooseDraft} from '@/utils/draftRecovery'
import {readCloudDraft,queueCloudDraft,clearCloudDraft} from '@/utils/cloudDrafts'
import {markManagedDraft} from '@/utils/autoDrafts'
import {draftBusinessNow,sanitizeDraft,AUTO_DRAFT_TTL} from '@/utils/autoDraftStore'

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
 * 草稿保留在当前浏览器本机，并按模块、用户、创建/记录 ID 隔离。
 * 关闭弹窗会保留草稿；再次打开自动恢复，正式保存成功后清除。
 */
export const useFormDraft = ({
  namespace,
  form,
  createDefault,
  formRef,
  applyDraft,
  legacyStorageKeys = [],
  saveDelay = 400,
}) => {
  markManagedDraft(form)
  const storageKey = `form-drafts:${namespace}:${currentUserKey()}`
  const activeDraftKey = ref('')
  const savingEnabled = ref(false)
  let saveTimer = null
  let generation=0
  const cloudNamespace=`form:${namespace}`

  const readDrafts = () => {
    try {
      let raw = localStorage.getItem(storageKey)||sessionStorage.getItem(storageKey)
      if (!raw) {
        const legacyKey = legacyStorageKeys.find((key) => sessionStorage.getItem(key))
        if (legacyKey) {
          raw = sessionStorage.getItem(legacyKey)
          localStorage.setItem(storageKey, raw)
          sessionStorage.removeItem(legacyKey)
        }
      }
      const value = JSON.parse(raw || '{}')
      return value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value).filter(([,draft])=>!draft.savedAt||Date.now()-Date.parse(draft.savedAt)<AUTO_DRAFT_TTL)) : {}
    } catch {
      localStorage.removeItem(storageKey)
      return {}
    }
  }

  const writeDrafts = (drafts) => {
    try {
      if (Object.keys(drafts).length) localStorage.setItem(storageKey, JSON.stringify(drafts))
      else localStorage.removeItem(storageKey)
      sessionStorage.removeItem(storageKey)
    } catch {
      ElMessage.warning('本机草稿保存失败，可能存储空间不足；请使用正式保存按钮保留内容')
    }
  }

  const removeDraft = (key = activeDraftKey.value) => {
    if (!key) return
    const drafts = readDrafts()
    delete drafts[key]
    writeDrafts(drafts)
    clearCloudDraft(cloudNamespace,key)
  }

  const saveActiveDraft = () => {
    if (!savingEnabled.value || !activeDraftKey.value) return
    const drafts = readDrafts()
    drafts[activeDraftKey.value] = {
      form: sanitizeDraft(form),
      savedAt: draftBusinessNow(),
    }
    writeDrafts(drafts)
    queueCloudDraft(cloudNamespace,activeDraftKey.value,drafts[activeDraftKey.value])
  }

  const cancelScheduledSave = () => {
    if (saveTimer !== null) window.clearTimeout(saveTimer)
    saveTimer = null
  }

  const scheduleActiveDraft = () => {
    if (!savingEnabled.value || !activeDraftKey.value) return
    cancelScheduledSave()
    saveTimer = window.setTimeout(() => {
      saveTimer = null
      saveActiveDraft()
    }, saveDelay)
  }

  const flushDraft = () => {
    if (saveTimer === null) return
    cancelScheduledSave()
    saveActiveDraft()
  }

  const beginDraft = async (key) => {
    cancelScheduledSave()
    savingEnabled.value = false
    activeDraftKey.value = key
    const current=++generation
    const initial=clone(form),local=readDrafts()[key]
    const restore=(draft)=>{if(draft?.form){const restored=clone(draft.form);if(applyDraft)applyDraft(restored);else Object.assign(form,createDefault(),restored)}}
    try{restore(local)}catch{ElMessage.warning('草稿自动恢复失败，原内容仍保留，请勿覆盖')}
    const baseline=JSON.stringify(sanitizeDraft(form))
    void readCloudDraft(cloudNamespace,key).then(cloud=>{
      if(current!==generation||activeDraftKey.value!==key||JSON.stringify(sanitizeDraft(form))!==baseline)return
      const chosen=chooseDraft(local,cloud)
      savingEnabled.value=false
      try{if(chosen)restore(chosen);else if(local){Object.assign(form,initial);const drafts=readDrafts();delete drafts[key];writeDrafts(drafts)}}
      finally{savingEnabled.value=true;formRef?.value?.clearValidate?.()}
    }).catch(()=>{/* 离线时即时使用本机内容，不阻塞打开表单。 */})

    savingEnabled.value = true
    formRef?.value?.clearValidate?.()
  }

  const pauseDraft = () => {
    generation++
    flushDraft()
    savingEnabled.value = false
    activeDraftKey.value = ''
  }

  const clearDraft = () => {
    generation++
    cancelScheduledSave()
    savingEnabled.value = false
    removeDraft()
    activeDraftKey.value = ''
  }
  // 同步阶段只重置轻量计时器，JSON 克隆与本机存储写入延后执行。
  watch(form, scheduleActiveDraft, { deep: true, flush: 'sync' })
  const persist=()=>flushDraft()
  const hidden=()=>{if(document.hidden)flushDraft()}
  window.addEventListener('pagehide',persist)
  document.addEventListener('visibilitychange',hidden)
  onBeforeUnmount(()=>{flushDraft();generation++;window.removeEventListener('pagehide',persist);document.removeEventListener('visibilitychange',hidden)})

  return { beginDraft, pauseDraft, clearDraft, flushDraft, removeDraft }
}
