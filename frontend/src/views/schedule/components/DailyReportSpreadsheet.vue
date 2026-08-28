<template>
  <div class="daily-report-sheet">
    <div ref="container" class="daily-report-sheet__canvas" v-loading="loading" />
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets'
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import '@univerjs/preset-sheets-core/lib/index.css'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  editable: { type: Boolean, default: true },
  mailMode: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '430px' }
})

const emit = defineEmits(['dirty-change', 'selection-change'])
const container = ref(null)
const dirtyRows = ref(new Set())
const selectedIndexes = ref([])
let univer = null
let univerAPI = null
let worksheet = null
let disposables = []
let disposed = false
let rebuildSequence = 0
let textMeasureContext = null
let activeColumnWidths = []

const columns = [
  { key: 'index', label: '序号', width: 64, minWidth: 64, maxWidth: 80, editable: false },
  { key: 'order_no', label: '订单号', width: 132, minWidth: 120, maxWidth: 200, editable: false },
  { key: 'task_name', label: '项目 / 任务', width: 220, minWidth: 160, maxWidth: 320, editable: true },
  { key: 'client_name', label: '客户', width: 110, minWidth: 100, maxWidth: 220, editable: false },
  { key: 'task_type', label: '任务类型', width: 110, minWidth: 100, maxWidth: 180, editable: true },
  { key: 'progress_content', label: '工作进展', width: 260, minWidth: 180, maxWidth: 360, editable: true },
  { key: 'result_content', label: '工作成果', width: 230, minWidth: 180, maxWidth: 360, editable: true },
  { key: 'duration_minutes', label: '耗时（分钟）', width: 120, minWidth: 120, maxWidth: 200, editable: true },
  { key: 'source_label', label: '来源', width: 110, minWidth: 100, maxWidth: 160, editable: false }
]

const sourceLabels = { project: '项目任务', non_project: '非项目任务', manual: '手工补充', system_event: '系统事件' }
const durationColumnIndex = columns.findIndex(column => column.key === 'duration_minutes')
const summaryLabelColumnIndex = durationColumnIndex - 1
const columnWidthsStorageKey = `daily-report-column-widths:${localStorage.getItem('user_id') || 'anonymous'}`

function measureTextWidth(value) {
  if (!textMeasureContext) {
    textMeasureContext = document.createElement('canvas').getContext('2d')
    if (textMeasureContext) textMeasureContext.font = '11px Arial'
  }
  return textMeasureContext?.measureText(String(value ?? '')).width || String(value ?? '').length * 11
}

function contentFitColumnWidths(matrix) {
  return columns.map((column, columnIndex) => {
    const contentWidth = matrix.reduce((maximum, row) => {
      const longestLine = String(row[columnIndex] ?? '').split(/\r?\n/)
        .reduce((lineMaximum, line) => Math.max(lineMaximum, measureTextWidth(line)), 0)
      return Math.max(maximum, longestLine)
    }, 0) + 24
    return Math.round(Math.min(column.maxWidth, Math.max(column.minWidth, contentWidth)))
  })
}

function resolveColumnWidths(matrix) {
  const fittedWidths = contentFitColumnWidths(matrix)
  try {
    const saved = JSON.parse(localStorage.getItem(columnWidthsStorageKey) || '{}')
    return columns.map((column, index) => {
      const width = Number(saved[column.key])
      return Number.isFinite(width) && width >= 48 && width <= 800 ? Math.round(width) : fittedWidths[index]
    })
  } catch {
    localStorage.removeItem(columnWidthsStorageKey)
    return fittedWidths
  }
}

function rememberColumnWidths(reflowRows = true) {
  if (!worksheet) return
  activeColumnWidths = columns.map((column, index) => {
    const width = Math.round(worksheet.getColumnWidth(index))
    return Number.isFinite(width) && width > 0 ? width : (activeColumnWidths[index] || column.width)
  })
  if (!props.mailMode) {
    try {
      localStorage.setItem(columnWidthsStorageKey, JSON.stringify(Object.fromEntries(
        columns.map((column, index) => [column.key, activeColumnWidths[index]])
      )))
    } catch {
      // 浏览器禁用本地存储时仍保留当前会话内的列宽。
    }
  }
  if (reflowRows) autoFitRows(1, summaryRowIndex())
}

function normalizeDurationMinutes(value) {
  const minutes = Number(value || 0)
  if (!Number.isFinite(minutes)) return 0
  return Math.max(0, Math.min(1440, Math.round(minutes)))
}

function formatDurationTotal(totalMinutes) {
  const hours = Number((totalMinutes / 60).toFixed(2))
  return `${hours} 小时（${totalMinutes} 分钟）`
}

function summaryRowIndex() {
  return props.rows.length + 1
}

function displayRow(row, index) {
  if (props.mailMode) return { index: index + 1, ...row }
  const metadata = row.display_metadata || {}
  return {
    index: index + 1,
    order_no: metadata.order_no || '',
    task_name: row.task_name || '',
    client_name: metadata.client_short_name || '',
    task_type: row.task_type || '',
    progress_content: row.progress_content || '',
    result_content: row.result_content || '',
    duration_minutes: Number(row.duration_minutes || 0),
    source_label: sourceLabels[row.source_type] || row.source_type || ''
  }
}

function sourceMatrix() {
  const detailRows = props.rows.map((row, index) => {
    const display = displayRow(row, index)
    return columns.map(column => display[column.key] ?? '')
  })
  const totalMinutes = detailRows.reduce(
    (total, row) => total + normalizeDurationMinutes(row[durationColumnIndex]),
    0
  )
  const summaryRow = Array(columns.length).fill('')
  summaryRow[summaryLabelColumnIndex] = '当日工作耗时合计'
  summaryRow[durationColumnIndex] = formatDurationTotal(totalMinutes)
  return [
    columns.map(column => column.label),
    ...detailRows,
    summaryRow
  ]
}

function canEditColumn(column) {
  return props.editable && (props.mailMode ? column.key !== 'index' : column.editable)
}

function canEditCell(rowIndex, column) {
  if (!canEditColumn(column)) return false
  if (props.mailMode) return true
  return props.rows[rowIndex - 1]?.source_type !== 'system_event'
}

function disposeGrid() {
  disposables.forEach(item => item?.dispose?.())
  disposables = []
  univerAPI?.dispose?.()
  univer?.dispose?.()
  univer = null
  univerAPI = null
  worksheet = null
  if (container.value) container.value.innerHTML = ''
}

function markDirty(startRow, endRow = startRow) {
  const next = new Set(dirtyRows.value)
  for (let row = Math.max(1, startRow); row <= Math.min(props.rows.length, endRow); row += 1) {
    next.add(row - 1)
  }
  dirtyRows.value = next
  emit('dirty-change', next.size)
}

function autoFitRows(startRow, endRow = startRow) {
  if (!worksheet) return
  const normalizedStart = Math.max(1, startRow)
  const normalizedEnd = Math.min(summaryRowIndex(), endRow)
  if (normalizedStart > normalizedEnd) return
  const values = worksheet.getRange(
    normalizedStart,
    0,
    normalizedEnd - normalizedStart + 1,
    columns.length
  ).getValues()
  values.forEach((cells, rowOffset) => {
    let maxLines = 1
    cells.forEach((cell, columnIndex) => {
      const text = String(cell ?? '')
      const availableWidth = Math.max(24, (activeColumnWidths[columnIndex] || columns[columnIndex].width) - 16)
      const lineCount = text.split(/\r?\n/).reduce((total, paragraph) => {
        if (!paragraph) return total + 1
        let lines = 1
        let lineWidth = 0
        for (const character of paragraph) {
          const characterWidth = measureTextWidth(character)
          if (lineWidth > 0 && lineWidth + characterWidth > availableWidth) {
            lines += 1
            lineWidth = characterWidth
          } else {
            lineWidth += characterWidth
          }
        }
        return total + lines
      }, 0)
      maxLines = Math.max(maxLines, lineCount)
    })
    const rowHeight = Math.min(540, Math.max(24, maxLines * 18 + 8))
    worksheet.setRowHeightsForced(normalizedStart + rowOffset, 1, rowHeight)
  })
}

function updateDurationSummary() {
  if (!worksheet) return
  const totalMinutes = props.rows.length
    ? worksheet.getRange(1, durationColumnIndex, props.rows.length, 1).getValues()
      .reduce((total, row) => total + normalizeDurationMinutes(row[0]), 0)
    : 0
  const rowIndex = summaryRowIndex()
  const summaryRow = Array(columns.length).fill('')
  summaryRow[summaryLabelColumnIndex] = '当日工作耗时合计'
  summaryRow[durationColumnIndex] = formatDurationTotal(totalMinutes)
  worksheet.getRange(rowIndex, 0, 1, columns.length).setValues([summaryRow])
  autoFitRows(rowIndex)
}

async function rebuild() {
  const sequence = ++rebuildSequence
  await nextTick()
  if (disposed || sequence !== rebuildSequence || !container.value) return
  // 保存草稿、切换日期等操作会重建工作簿，销毁前先兜底保存当前列宽。
  rememberColumnWidths(false)
  disposeGrid()
  const created = createUniver({
    locale: LocaleType.ZH_CN,
    locales: { [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN) },
    presets: [UniverSheetsCorePreset({ container: container.value })]
  })
  univer = created.univer
  univerAPI = created.univerAPI
  const workbook = univerAPI.createWorkbook({ name: props.mailMode ? '工作报告邮件预览' : '个人工作日报' })
  worksheet = workbook.getActiveSheet()
  const matrix = sourceMatrix()
  activeColumnWidths = resolveColumnWidths(matrix)
  worksheet.getRange(0, 0, matrix.length, columns.length).setValues(matrix)
  worksheet.setFrozenRows(1)
  worksheet.setFrozenColumns(2)
  worksheet.setRowHeight(0, 36)
  columns.forEach((_column, index) => worksheet.setColumnWidth(index, activeColumnWidths[index]))
  worksheet.getRange(0, 0, 1, columns.length)
    .setBackground('#dbeafe')
    .setFontColor('#1e3a5f')
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
  const totalRow = summaryRowIndex()
  worksheet.getRange(totalRow, 0, 1, columns.length)
    .setBackground('#ecfdf5')
    .setFontColor('#166534')
    .setFontWeight('bold')
    .setVerticalAlignment('middle')
  worksheet.getRange(totalRow, summaryLabelColumnIndex, 1, 2).setHorizontalAlignment('center').setWrap(true)
  if (props.rows.length) {
    worksheet.getRange(1, 0, props.rows.length, columns.length).setWrap(true).setVerticalAlignment('middle')
    columns.forEach((column, index) => {
      if (!canEditColumn(column)) {
        worksheet.getRange(1, index, props.rows.length, 1).setBackground('#f1f5f9').setFontColor('#475569')
      }
    })
    props.rows.forEach((row, index) => {
      if (row.source_type === 'system_event') {
        worksheet.getRange(index + 1, 0, 1, columns.length).setBackground('#f1f5f9').setFontColor('#475569')
      }
    })
    // Univer 初始化阶段的原生自动行高不会主动测量内容，这里按实际字体宽度计算并固定行高。
    autoFitRows(1, props.rows.length)
  }
  autoFitRows(totalRow)
  disposables.push(univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, params => {
    const column = columns[params.column]
    if (params.row === 0 || params.row > props.rows.length || !column || !canEditCell(params.row, column)) params.cancel = true
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SheetEditEnded, params => {
    if (params.isConfirm && params.row > 0 && canEditCell(params.row, columns[params.column])) {
      autoFitRows(params.row)
      if (params.column === durationColumnIndex) updateDurationSummary()
      markDirty(params.row)
    }
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.ClipboardPasted, () => {
    if (selectedIndexes.value.length) {
      autoFitRows(selectedIndexes.value[0] + 1, selectedIndexes.value[selectedIndexes.value.length - 1] + 1)
    }
    updateDurationSummary()
    selectedIndexes.value.forEach(index => markDirty(index + 1))
  }))
  disposables.push(univerAPI.addEvent(univerAPI.Event.SelectionChanged, params => {
    const indexes = new Set()
    for (const selection of params.selections || []) {
      for (let row = Math.max(1, selection.startRow); row <= Math.min(props.rows.length, selection.endRow); row += 1) {
        indexes.add(row - 1)
      }
    }
    selectedIndexes.value = [...indexes].sort((a, b) => a - b)
    emit('selection-change', selectedIndexes.value)
  }))
  const structuralCommands = new Set([
    'sheet.command.insert-row', 'sheet.command.insert-row-before', 'sheet.command.insert-row-after',
    'sheet.command.remove-row', 'sheet.command.insert-column', 'sheet.command.remove-column',
    'sheet.command.sort-range', 'sheet.command.move-rows', 'sheet.command.move-columns'
  ])
  disposables.push(univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute, event => {
    if (structuralCommands.has(event.id)) event.cancel = true
  }))
  const columnWidthEvents = new Set([
    'sheet.command.delta-column-width',
    'sheet.command.set-worksheet-col-width',
    'sheet.command.set-col-auto-width',
    'sheet.mutation.set-worksheet-col-width'
  ])
  disposables.push(univerAPI.addEvent(univerAPI.Event.CommandExecuted, event => {
    if (columnWidthEvents.has(event.id)) {
      rememberColumnWidths(event.id !== 'sheet.mutation.set-worksheet-col-width')
    }
  }))
  dirtyRows.value = new Set()
  selectedIndexes.value = []
  emit('dirty-change', 0)
  emit('selection-change', [])
}

function getRows() {
  if (!worksheet) return props.rows.map(row => ({ ...row }))
  // 点击“保存草稿”一定会经过这里，确保请求发出前列宽已经落盘。
  rememberColumnWidths(false)
  const values = props.rows.length
    ? worksheet.getRange(1, 0, props.rows.length, columns.length).getValues()
    : []
  return values.map((cells, index) => {
    if (!props.mailMode && props.rows[index]?.source_type === 'system_event') {
      return { ...props.rows[index], duration_minutes: 0 }
    }
    const value = Object.fromEntries(columns.map((column, columnIndex) => [column.key, cells[columnIndex]]))
    const duration = normalizeDurationMinutes(value.duration_minutes)
    if (props.mailMode) {
      return {
        order_no: String(value.order_no || '').trim(),
        task_name: String(value.task_name || '').trim(),
        client_name: String(value.client_name || '').trim(),
        task_type: String(value.task_type || '').trim(),
        progress_content: String(value.progress_content || '').trim(),
        result_content: String(value.result_content || '').trim(),
        duration_minutes: duration,
        source_label: String(value.source_label || '').trim()
      }
    }
    return {
      ...props.rows[index],
      task_name: String(value.task_name || '').trim(),
      task_type: String(value.task_type || '').trim(),
      progress_content: String(value.progress_content || '').trim(),
      result_content: String(value.result_content || '').trim(),
      duration_minutes: duration
    }
  })
}

function clearDirty() {
  dirtyRows.value = new Set()
  emit('dirty-change', 0)
}

function handleBeforeUnload() {
  rememberColumnWidths(false)
}

watch(() => props.rows, rebuild, { deep: true })
watch(() => [props.editable, props.mailMode], rebuild)
onMounted(() => {
  disposed = false
  window.addEventListener('beforeunload', handleBeforeUnload)
  rebuild()
})
onBeforeUnmount(() => {
  rememberColumnWidths(false)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  disposed = true
  rebuildSequence += 1
  disposeGrid()
})
defineExpose({ getRows, getSelectedIndexes: () => [...selectedIndexes.value], rebuild, clearDirty })
</script>

<style scoped>
.daily-report-sheet{min-width:0}.daily-report-sheet__canvas{height:v-bind(height);min-height:320px;border:1px solid var(--el-border-color);border-radius:6px;overflow:hidden;background:#fff}
@media(max-width:768px){.daily-report-sheet__canvas{height:420px}}
</style>
