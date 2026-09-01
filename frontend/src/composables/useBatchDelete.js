import { h, nextTick, ref, unref, watch } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const resolveValue = (source) => (typeof source === 'function' ? source() : unref(source))

const errorMessage = (error) => getLocalizedErrorMessage(error, '该记录可能已被删除，或存在关联数据限制')

export function useBatchDelete({
  rows,
  tableRef,
  pagination,
  deleteRow,
  getLabel,
  reload,
  onDeleted,
  entityName = '记录',
}) {
  const deleteMode = ref(false)
  const deleting = ref(false)
  const selectedRows = ref([])

  const clearTableSelection = () => resolveValue(tableRef)?.clearSelection?.()

  const enterDeleteMode = () => {
    clearTableSelection()
    selectedRows.value = []
    deleteMode.value = true
  }

  const exitDeleteMode = () => {
    deleteMode.value = false
    selectedRows.value = []
    nextTick(clearTableSelection)
  }

  const handleDeleteSelectionChange = (selection) => {
    selectedRows.value = Array.isArray(selection) ? selection : []
  }

  const labelOf = (row) => getLabel?.(row) || row?.orderNo || row?.order_no || row?.name || row?.id || entityName

  const confirmSelection = async (selection) => {
    if (selection.length === 1) {
      await ElMessageBox.confirm(
        `确定删除${entityName}“${labelOf(selection[0])}”吗？删除后无法恢复。`,
        '删除确认',
        { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
      )
      return
    }

    const preview = selection.slice(0, 5).map((row) => labelOf(row)).join('、')
    const remaining = selection.length > 5 ? `等 ${selection.length} 条` : `共 ${selection.length} 条`
    await ElMessageBox.prompt(
      `即将删除${entityName}${remaining}：${preview}。此操作无法恢复，请输入“删除”继续。`,
      '批量删除确认',
      {
        type: 'warning',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入“删除”',
        inputValidator: (value) => value === '删除' || '请输入“删除”以确认操作',
      },
    )
  }

  const showFailures = (failures) => {
    if (!failures.length) return
    const lines = failures.slice(0, 6).map(({ row, error }) =>
      h('div', { style: 'margin-bottom: 4px; word-break: break-word;' }, `${labelOf(row)}：${errorMessage(error)}`),
    )
    if (failures.length > 6) {
      lines.push(h('div', `另有 ${failures.length - 6} 条删除失败`))
    }
    ElNotification({
      title: `${failures.length} 条${entityName}删除失败`,
      message: h('div', lines),
      type: 'warning',
      duration: 10000,
    })
  }

  const restoreFailedSelection = async (failures) => {
    selectedRows.value = failures.map(({ row }) => row)
    const failedIds = new Set(failures.map(({ row }) => row?.id))
    await nextTick()
    clearTableSelection()
    const currentRows = resolveValue(rows) || []
    currentRows.forEach((row) => {
      if (failedIds.has(row?.id)) resolveValue(tableRef)?.toggleRowSelection?.(row, true)
    })
  }

  const confirmBatchDelete = async () => {
    const selection = [...selectedRows.value]
    if (!selection.length || deleting.value) return

    try {
      await confirmSelection(selection)
    } catch (action) {
      if (action !== 'cancel' && action !== 'close') ElMessage.error('无法打开删除确认')
      return
    }

    deleting.value = true
    const successes = []
    const failures = []
    for (const row of selection) {
      try {
        await deleteRow(row)
        successes.push(row)
        onDeleted?.(row)
      } catch (error) {
        failures.push({ row, error })
      }
    }

    if (successes.length && pagination) {
      const remainingTotal = Math.max(0, Number(pagination.total || 0) - successes.length)
      const lastPage = Math.max(1, Math.ceil(remainingTotal / Number(pagination.limit || 1)))
      if (pagination.page > lastPage) pagination.page = lastPage
    }

    if (successes.length) await reload?.()

    if (failures.length) {
      await restoreFailedSelection(failures)
      showFailures(failures)
    } else {
      exitDeleteMode()
    }

    if (successes.length && failures.length) {
      ElMessage.warning(`已删除 ${successes.length} 条，${failures.length} 条失败`)
    } else if (successes.length) {
      ElMessage.success(`已删除 ${successes.length} 条${entityName}`)
    } else {
      ElMessage.error(`所选${entityName}均未删除`)
    }
    deleting.value = false
  }

  if (pagination) {
    watch(
      () => [pagination.page, pagination.limit],
      () => {
        if (deleteMode.value && !deleting.value) exitDeleteMode()
      },
    )
  }

  return {
    deleteMode,
    deleting,
    selectedRows,
    enterDeleteMode,
    exitDeleteMode,
    handleDeleteSelectionChange,
    confirmBatchDelete,
  }
}
