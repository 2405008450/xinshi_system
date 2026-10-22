import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/annotationOps'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { appendProgressDraft } from '@/utils/annotationCustomerProgress'

// 录入区和记录区共享一个控制器，切换展示时不销毁草稿或重复请求。
export function useAnnotationCustomerProgress({ projectId, active, busy, entryRef, onSaved, onEdit, beforeSave }) {
  const loading = ref(false), validating = ref(false), submitting = ref(false), loadError = ref(''), rows = ref([])
  const editingId = ref(''), expectedUpdatedAt = ref(''), draftSource = ref(null)
  const form = reactive({ effectiveOn: businessDateTimeInputValue(), changeNote: '' })
  let baseline = JSON.stringify(form), loadedProject = '', requestId = 0, controller, pendingLoad
  const hasDraft = () => Boolean(draftSource.value) || JSON.stringify(form) !== baseline
  const getDraft = () => ({ ...form, source: draftSource.value, editingId: editingId.value })
  const clearDraft = () => {
    editingId.value = ''; expectedUpdatedAt.value = ''; draftSource.value = null
    Object.assign(form, { effectiveOn: businessDateTimeInputValue(), changeNote: '' })
    baseline = JSON.stringify(form); entryRef.value?.clearValidate()
  }
  const reset = () => {
    controller?.abort(); requestId++; loading.value = false
    rows.value = []; loadedProject = ''; loadError.value = ''; clearDraft()
  }
  const reload = () => {
    const id = projectId.value
    if (!id) return Promise.resolve(false)
    controller?.abort(); controller = new AbortController()
    const current = ++requestId; loading.value = true; loadError.value = ''
    const signal = controller.signal
    pendingLoad = (async () => {
      try {
        const result = await api.getCustomerProgress(id, { signal })
        if (current !== requestId || id !== projectId.value) return false
        rows.value = result; loadedProject = id
        if (editingId.value && !rows.value.some((row) => row.id === editingId.value)) clearDraft()
        return true
      } catch (error) {
        if (current === requestId && error?.code !== 'ERR_CANCELED') loadError.value = error?.detail || '客户进度加载失败，请重试'
        return false
      } finally { if (current === requestId) loading.value = false }
    })()
    return pendingLoad
  }
  const ensureLoaded = async () => {
    if (loadedProject === projectId.value && !loadError.value) return
    // 草稿带入可以与首次激活同时发生，复用正在进行的加载。
    await (loading.value ? pendingLoad : reload())
    if (loadedProject !== projectId.value || loadError.value) throw new Error(loadError.value || '客户进度尚未加载，请重试')
  }
  const focusEntry = async () => { await nextTick(); await entryRef.value?.focusEntry() }
  const edit = async (row) => {
    if (busy.value) return
    if (hasDraft()) {
      try { await ElMessageBox.confirm('录入区有未保存内容，是否放弃并编辑这条客户进度？', '编辑客户进度', { confirmButtonText: '放弃并编辑', cancelButtonText: '保留草稿', type: 'warning' }) } catch { return }
    }
    editingId.value = row.id; expectedUpdatedAt.value = row.updatedAt; draftSource.value = null
    Object.assign(form, { effectiveOn: businessDateTimeInputValue(row.effectiveOn), changeNote: row.changeNote })
    baseline = JSON.stringify(form); onEdit(); await focusEntry()
  }
  const acceptDraft = async (draft) => {
    const id = projectId.value
    await ensureLoaded()
    if (id !== projectId.value) throw new Error('项目已切换，请重新带入沟通消息')
    if (editingId.value) throw new Error('请先保存或取消当前客户进度编辑，再带入沟通消息')
    const note = appendProgressDraft(form.changeNote, draft.changeNote)
    if (!form.changeNote.trim()) form.effectiveOn = draft.effectiveOn
    form.changeNote = note
    draftSource.value = draftSource.value && draft.source
      ? { messageCount: draftSource.value.messageCount + draft.source.messageCount, senderSummary: [...new Set([...draftSource.value.senderSummary.split('、'), ...draft.source.senderSummary.split('、')])].join('、') }
      : draft.source || draftSource.value
    await focusEntry()
  }
  // 归属转移由调用方完成冲突确认；此处只接收完整草稿，不触发保存。
  const setDraft = (draft) => {
    if (editingId.value) throw new Error('请先保存或取消客户进度编辑，再切换进度归属')
    Object.assign(form, { changeNote: draft.changeNote, effectiveOn: draft.effectiveOn })
    draftSource.value = draft.source || null
  }
  const save = async () => {
    if (validating.value || submitting.value || busy.value || loading.value || loadError.value) return
    // 在异步校验前锁定提交，防止连续点击发出多次写入。
    validating.value = true
    try {
      if (!await entryRef.value?.validate().catch(() => false)) return
      const chatDelivery=beforeSave?await beforeSave():undefined
      if(beforeSave&&!chatDelivery)return
      submitting.value = true; validating.value = false
      const payload = { ...form, effectiveOn: form.effectiveOn.replace(' ', 'T') + '+08:00', changeNote: form.changeNote.trim(), ...(chatDelivery?{chatDelivery}:{}) }
      const saved = editingId.value ? await api.updateCustomerProgress(editingId.value, { ...payload, expectedUpdatedAt: expectedUpdatedAt.value }) : await api.createCustomerProgress(projectId.value, payload)
      clearDraft(); ElMessage.success('客户进度已保存')
      // 写入成功与刷新失败分开处理，避免提示失败后重复提交已经保存的记录。
      await reload()
      try { await onSaved(saved) } catch { ElMessage.warning('客户进度已保存，刷新失败，请重新加载记录') }
    } catch (error) {
      // 服务端字段错误也需要聚焦；保持操作锁定，但先恢复输入控件。
      validating.value = true; submitting.value = false
      await entryRef.value?.applyServerErrors(error)
      ElMessage.error(error?.detail || '客户进度保存失败，请重试')
    } finally { validating.value = false; submitting.value = false }
  }
  watch(projectId, reset, { flush: 'sync' })
  watch([active, projectId], ([enabled, id]) => { if (enabled && id && loadedProject !== id && !loading.value) void reload() }, { immediate: true })
  onBeforeUnmount(() => { controller?.abort(); requestId++ })
  return reactive({ loading, validating, submitting, loadError, rows, form, editingId, draftSource, reload, ensureLoaded, hasDraft, getDraft, clearDraft, reset, acceptDraft, setDraft, save, edit })
}
