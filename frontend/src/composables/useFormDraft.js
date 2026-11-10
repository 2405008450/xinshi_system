import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {chooseDraft} from '@/utils/draftRecovery'
import {readCloudDraft,queueCloudDraft,clearCloudDraft} from '@/utils/cloudDrafts'
import {markManagedDraft} from '@/utils/autoDrafts'
import {draftBusinessNow,sanitizeDraft} from '@/utils/autoDraftStore'
import {withoutBusinessNumbers} from '@/utils/businessNumberLeases'

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
  createDrafts = true,
  requireUserId = true,
  retentionMs = null,
  draftComparison,
  createDraftVersion,
  draftVersion,
  captureContext,
  restoreContext,
  validateDraft,
}) => {
  markManagedDraft(form)
  const userKey = () => requireUserId ? localStorage.getItem('user_id') || '' : currentUserKey()
  let draftOwner = ''
  const storageKey = () => `form-drafts:${namespace}:${draftOwner || userKey()}`
  const sameOwner = () => Boolean(draftOwner) && draftOwner === userKey()
  const activeDraftKey = ref('')
  const savingEnabled = ref(false)
  let saveTimer = null
  let generation=0
  const cloudNamespace=`form:${namespace}`
  const comparison = () => JSON.stringify(withoutBusinessNumbers(form,sanitizeDraft(draftComparison ? draftComparison(form) : form),true))

  const readDrafts = () => {
    try {
      let raw = localStorage.getItem(storageKey())||sessionStorage.getItem(storageKey())
      if (!raw && !requireUserId) {
        const legacyKey = legacyStorageKeys.find((key) => sessionStorage.getItem(key))
        if (legacyKey) {
          raw = sessionStorage.getItem(legacyKey)
          localStorage.setItem(storageKey(), raw)
          sessionStorage.removeItem(legacyKey)
        }
      }
      const value = JSON.parse(raw || '{}')
      return value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value).filter(([,draft])=>retentionMs === null || !draft.savedAt || Date.now()-Date.parse(draft.savedAt)<retentionMs)) : {}
    } catch {
      localStorage.removeItem(storageKey())
      return {}
    }
  }

  const writeDrafts = (drafts) => {
    try {
      if (Object.keys(drafts).length) localStorage.setItem(storageKey(), JSON.stringify(drafts))
      else localStorage.removeItem(storageKey())
      sessionStorage.removeItem(storageKey())
    } catch {
      ElMessage.warning('本机草稿保存失败，可能存储空间不足；请使用正式保存按钮保留内容')
    }
  }

  const removeDraft = (key = activeDraftKey.value) => {
    if (!key || !sameOwner()) return
    const drafts = readDrafts()
    delete drafts[key]
    writeDrafts(drafts)
    clearCloudDraft(cloudNamespace,key)
  }

  const saveActiveDraft = () => {
    if (!savingEnabled.value || !activeDraftKey.value || !sameOwner()) return
    const drafts = readDrafts()
    const draft = {
      form: activeDraftKey.value === 'create' ? withoutBusinessNumbers(form,sanitizeDraft(form)) : sanitizeDraft(form),
      savedAt: draftBusinessNow(),
      ownerId: draftOwner,
      ...(captureContext ? { context: sanitizeDraft(captureContext()) } : {}),
      ...((activeDraftKey.value === 'create' && createDraftVersion) || draftVersion ? { version: activeDraftKey.value === 'create' && createDraftVersion || draftVersion } : {}),
    }
    if (validateDraft && !validateDraft(draft, activeDraftKey.value)) return
    drafts[activeDraftKey.value] = draft
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
    // 个别新增表单要求每次重新填写；即使入口误调用，也不读写新增草稿。
    if ((key === 'create' && !createDrafts) || !userKey()) {
      generation++
      cancelScheduledSave()
      savingEnabled.value = false
      activeDraftKey.value = ''
      return
    }
    cancelScheduledSave()
    savingEnabled.value = false
    draftOwner = userKey()
    activeDraftKey.value = key
    const current=++generation
    const usable = draft => draft?.form && (!validateDraft || validateDraft(draft,key)) && (!draft.ownerId || draft.ownerId === draftOwner) && (!draftVersion || draft.version === draftVersion && draft.ownerId === draftOwner) && (key !== 'create' || !createDraftVersion || (
      draft.version === createDraftVersion && draft.ownerId === draftOwner && !draft.form.id
    ))
    const initial=clone(form),stored=readDrafts()[key],local=usable(stored)?stored:undefined
    const restore=(draft)=>{if(draft?.form){const restored=key==='create'?withoutBusinessNumbers(form,clone(draft.form)):clone(draft.form);if(applyDraft)applyDraft(restored,key);else Object.assign(form,createDefault(),restored);if(draft.context&&restoreContext)restoreContext(clone(draft.context),key)}}
    try{restore(local)}catch{ElMessage.warning('草稿自动恢复失败，原内容仍保留，请勿覆盖')}
    const baseline=comparison()
    void readCloudDraft(cloudNamespace,key).then(cloud=>{
      if(current!==generation||!sameOwner()||activeDraftKey.value!==key||comparison()!==baseline)return
      // 旧格式或归属不明的新增草稿不能覆盖当前账号的新内容。
      const checkedCloud = cloud?.payload && !usable(cloud.payload) ? { ...cloud, payload: null, revision: 0 } : cloud
      const chosen=chooseDraft(local,checkedCloud)
      savingEnabled.value=false
      try{if(chosen){restore(chosen);const drafts=readDrafts();drafts[key]=chosen;writeDrafts(drafts)}else if(local){restore({form:initial});const drafts=readDrafts();delete drafts[key];writeDrafts(drafts)}}
      finally{savingEnabled.value=true;formRef?.value?.clearValidate?.()}
    }).catch(()=>{/* 离线时即时使用本机内容，不阻塞打开表单。 */})

    savingEnabled.value = true
    formRef?.value?.clearValidate?.()
  }

  const pauseDraft = () => {
    generation++
    cancelScheduledSave()
    saveActiveDraft()
    savingEnabled.value = false
    activeDraftKey.value = ''
    draftOwner = ''
  }

  const clearDraft = () => {
    generation++
    cancelScheduledSave()
    savingEnabled.value = false
    removeDraft()
    activeDraftKey.value = ''
  }
  // 正式保存后继续编辑同一窗口：换成编辑草稿，不读取已清除的旧草稿。
  const startFreshDraft = (key) => {
    generation++
    cancelScheduledSave()
    draftOwner=userKey()
    activeDraftKey.value=draftOwner?key:''
    savingEnabled.value=Boolean(draftOwner)
  }
  // 同步阶段只重置轻量计时器，JSON 克隆与本机存储写入延后执行。
  watch(form, scheduleActiveDraft, { deep: true, flush: 'sync' })
  const persist=()=>{cancelScheduledSave();saveActiveDraft()}
  const hidden=()=>{if(document.hidden)persist()}
  window.addEventListener('pagehide',persist)
  window.addEventListener('auth-session-clearing',pauseDraft)
  document.addEventListener('visibilitychange',hidden)
  onBeforeUnmount(()=>{persist();generation++;window.removeEventListener('pagehide',persist);window.removeEventListener('auth-session-clearing',pauseDraft);document.removeEventListener('visibilitychange',hidden)})

  return { beginDraft, pauseDraft, clearDraft, flushDraft, removeDraft, startFreshDraft }
}
