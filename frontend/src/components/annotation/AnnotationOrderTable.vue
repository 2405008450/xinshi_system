<template>
  <div v-if="isMobile" class="order-cards" :class="{ 'is-nested': nested }">
    <div v-if="!rows.length" class="order-cards__empty">暂无数据</div>
    <article
      v-for="(row, index) in rows"
      :key="row.id"
      class="order-card"
      :class="[cardRowClass(row, index), { 'is-selected': selectedIds.includes(row.id) }]"
    >
      <header class="order-card__head">
        <el-checkbox v-if="deleteMode && !nested" :model-value="selectedIds.includes(row.id)" @change="toggleSelected(row)" />
        <span class="order-card__index">{{ index + 1 }}</span>
        <div class="order-card__order"><slot name="order" :row="row" :toggle="() => toggleRow(row)" /></div>
      </header>
      <dl v-if="columns.length" class="order-card__fields">
        <div v-for="column in columns" :key="column.key" class="order-card__field" :class="{ 'is-wide': isWideColumn(column) }">
          <dt><slot v-if="column.key === 'regionSummary'" name="header" :column="column" /><template v-else>{{ column.label }}</template></dt>
          <dd><slot name="cell" :row="row" :column="column" /></dd>
        </div>
      </dl>
      <footer class="order-card__foot">
        <div v-if="canExpand(row)" class="order-card__expand" @click="toggleRow(row)">
          <TableExpandButton :expanded="expanded.includes(row.id)" :expand-label="row.orderLevel === 1 ? '展开三级订单' : '展开子订单'" collapse-label="收起下级订单" @click="toggleRow(row)" />
          <span>{{ expanded.includes(row.id) ? '收起' : '展开' }}{{ row.orderLevel === 1 ? '三级订单' : '子订单' }}（{{ row.childCount || 0 }}）</span>
        </div>
        <span class="order-card__spacer" />
        <div v-if="!deleteMode" class="order-card__actions"><slot name="actions" :row="row" /></div>
      </footer>
      <div v-if="canExpand(row) && expanded.includes(row.id)" class="order-children order-children--card" v-loading="loadingIds.has(row.id)">
        <div class="order-children-toolbar">
          <span>{{ row.orderLevel === 1 ? '三级订单' : '子订单' }} · 共 {{ totals[row.id] ?? row.childCount ?? 0 }} 条</span>
          <el-button v-if="editable && !deleteMode" size="small" @click="$emit('create', row, true)">新增</el-button>
          <el-button v-if="editable && !deleteMode" size="small" @click="$emit('create', row, false)">批量新增</el-button>
          <el-button v-if="!conversationPicker" size="small" @click="$emit('manage', row)">管理全部</el-button>
        </div>
        <el-alert v-if="errors[row.id]" :title="errors[row.id]" type="error" :closable="false"><el-button link @click="load(row)">重试</el-button></el-alert>
        <AnnotationOrderTable :column-settings-key="columnSettingsKey" :rows="children[row.id] || []" :columns="columns" :editable="editable" :delete-mode="deleteMode" :conversation-picker="conversationPicker" :picker-action-label="pickerActionLabel" nested
          :revision="revision" :area-ids="areaIds" :supports-grandchild-orders="supportsGrandchildOrders" @create="(...args) => $emit('create', ...args)" @manage="$emit('manage', $event)" @updated="$emit('updated', $event)">
          <template #header="scope"><slot name="header" v-bind="scope" /></template>
          <template #cell="scope"><slot name="cell" v-bind="scope" /></template>
          <template #order="scope"><slot name="order" v-bind="scope" /></template>
          <template #actions="scope"><slot name="actions" v-bind="scope" /></template>
        </AnnotationOrderTable>
        <el-pagination v-if="(totals[row.id] || 0) > 10" :current-page="pages[row.id] || 1" :page-size="10" :total="totals[row.id]" small :pager-count="5"
          layout="prev, pager, next" @current-change="page => { pages[row.id] = page; load(row) }" />
      </div>
    </article>
  </div>
  <el-table v-else ref="tableRef" :data="rows" :height="nested ? undefined : '100%'" row-key="id" border
    :size="nested ? 'small' : undefined" :expand-row-keys="expanded" :row-class-name="rowClass"
    class="annotation-order-table project-detail-list-table" @expand-change="expandChanged" @selection-change="$emit('selection-change', $event)">
<OrderedTableColumns :settings-key="columnSettingsKey">
    <el-table-column v-if="deleteMode && !nested" type="selection" width="48" fixed="left" />
    <el-table-column type="expand" width="1" class-name="annotation-expand-column" label-class-name="annotation-expand-column">
      <template #default="{ row }">
        <div v-if="row.orderLevel < (supportsGrandchildOrders ? 2 : 1)" class="order-children" :style="containerWidth ? {width: `${containerWidth - 2}px`} : undefined" v-loading="loadingIds.has(row.id)">
          <div class="order-children-toolbar">
            <span>{{ row.orderLevel === 1 ? '三级订单' : '子订单' }} · 共 {{ totals[row.id] ?? row.childCount ?? 0 }} 条</span>
            <el-button v-if="editable && !deleteMode" @click="$emit('create', row, true)">新增{{ row.orderLevel === 1 ? '三级订单' : '子订单' }}</el-button>
            <el-button v-if="editable && !deleteMode" @click="$emit('create', row, false)">批量新增{{ row.orderLevel === 1 ? '三级订单' : '子订单' }}</el-button>
            <el-button v-if="!conversationPicker" @click="$emit('manage', row)">管理全部</el-button>
          </div>
          <el-alert v-if="errors[row.id]" :title="errors[row.id]" type="error" :closable="false"><el-button link @click="load(row)">重试</el-button></el-alert>
          <AnnotationOrderTable :column-settings-key="columnSettingsKey" :rows="children[row.id] || []" :columns="columns" :editable="editable" :delete-mode="deleteMode" :conversation-picker="conversationPicker" :picker-action-label="pickerActionLabel" nested
            :revision="revision" :area-ids="areaIds" :supports-grandchild-orders="supportsGrandchildOrders" @create="(...args) => $emit('create', ...args)" @manage="$emit('manage', $event)" @updated="$emit('updated', $event)">
            <template #header="scope"><slot name="header" v-bind="scope" /></template>
            <template #cell="scope"><slot name="cell" v-bind="scope" /></template>
            <template #order="scope"><slot name="order" v-bind="scope" /></template>
            <template #actions="scope"><slot name="actions" v-bind="scope" /></template>
          </AnnotationOrderTable>
          <el-pagination v-if="(totals[row.id] || 0) > 10" :current-page="pages[row.id] || 1" :page-size="10" :total="totals[row.id]" small
            layout="total, prev, pager, next" @current-change="page => { pages[row.id] = page; load(row) }" />
        </div>
      </template>
    </el-table-column>
    <el-table-column label="序号" width="65" :fixed="nested ? false : 'left'">
      <template #default="{ row, $index }"><div class="order-index"><span>{{ $index + 1 }}</span>
        <TableExpandButton v-if="row.orderLevel < (supportsGrandchildOrders ? 2 : 1)" :expanded="expanded.includes(row.id)" :expand-label="row.orderLevel === 1 ? '展开三级订单' : '展开子订单'" collapse-label="收起下级订单" @click="tableRef.toggleRowExpansion(row)" />
      </div></template>
    </el-table-column>
    <el-table-column label="订单号" :width="nested || rows.some(row => row.parentProjectId) ? 240 : 200" :fixed="nested ? false : 'left'"><template #header><slot name="header" :column="{key:'orderNo',label:'订单号'}" /></template><template #default="{ row }"><slot name="order" :row="row" :toggle="() => tableRef.toggleRowExpansion(row)" /></template></el-table-column>
    <el-table-column v-for="column in columns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="!['projectName','projectStatus'].includes(column.key)">
      <template #header><slot name="header" :column="column" /></template><template #default="{ row }"><slot name="cell" :row="row" :column="column" /></template>
    </el-table-column>
    <el-table-column v-if="!deleteMode" :label="conversationPicker ? pickerActionLabel : '操作'" width="120" fixed="right"><template #default="{ row }"><slot name="actions" :row="row" /></template></el-table-column>
  </OrderedTableColumns>
</el-table>
</template>

<script setup>
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { getAnnotationChildren } from '@/api/annotationProjects'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
const props = defineProps({ columnSettingsKey: { type: String, default: 'annotation-projects' }, rows: {type:Array,default:()=>[]}, columns: {type:Array,default:()=>[]}, editable:Boolean, deleteMode:Boolean, nested:Boolean, conversationPicker:Boolean, pickerActionLabel:{type:String,default:'加入会话'}, revision:Number, areaIds:Array, rowClass:Function, supportsGrandchildOrders:{type:Boolean,default:true} })
const emit = defineEmits(['selection-change','create','manage','updated'])
const { isMobile } = useMobileViewport()
const tableRef = ref(), expanded = ref([]), loadingIds = reactive(new Set())
const containerWidth=ref(0)
let resizeObserver
watch(()=>tableRef.value?.$el,element=>{
  resizeObserver?.disconnect();resizeObserver=undefined
  if(!element)return
  const measure=()=>{containerWidth.value=element.clientWidth}
  measure();resizeObserver=new ResizeObserver(measure);resizeObserver.observe(element)
},{flush:'post'})
const children = reactive({}), totals = reactive({}), pages = reactive({}), errors = reactive({})
const requests = new Map()
const load = async row => {
  requests.get(row.id)?.abort(); const controller = new AbortController(); requests.set(row.id, controller)
  loadingIds.add(row.id); errors[row.id] = ''
  try {
    const page = await getAnnotationChildren(row.id, {conversation_picker:props.conversationPicker ? '1' : undefined,skip:((pages[row.id] || 1)-1)*10,limit:10,area_ids:props.areaIds?.length ? props.areaIds : undefined}, {signal:controller.signal})
    if (requests.get(row.id) !== controller) return
    children[row.id] = page.items; totals[row.id] = page.total
  } catch (error) { if (requests.get(row.id) === controller && error.code !== 'ERR_CANCELED') errors[row.id] = error.detail || '下级订单加载失败' }
  finally { if (requests.get(row.id) === controller) loadingIds.delete(row.id) }
}
const expandChanged = (row, rows) => { expanded.value = rows.filter(item=>item.orderLevel<2).map(item=>item.id); if (expanded.value.includes(row.id)) void load(row) }
watch(()=>[props.revision, JSON.stringify(props.areaIds)],()=>{ for (const row of props.rows.filter(item=>expanded.value.includes(item.id))) { pages[row.id]=1; void load(row) } })
watch(()=>props.rows,()=>{ expanded.value=expanded.value.filter(id=>props.rows.some(row=>row.id===id)) })
onBeforeUnmount(()=>{resizeObserver?.disconnect();requests.forEach(controller=>controller.abort())})

// 手机端卡片模式：与表格共用展开、加载与选择语义，仅渲染方式不同。
const selectedIds = ref([])
const levelLimit = computed(() => (props.supportsGrandchildOrders ? 2 : 1))
const canExpand = row => row.orderLevel < levelLimit.value
const wideColumnKeys = new Set(['projectName','taskDescription','latestCustomerProgressNote','languageItemsDisplay','regionSummary','customerPriceSummary','assigneeSummary','projectPath','quotationPath','contractPath','clientFullName','customerOrderNo'])
const isWideColumn = column => wideColumnKeys.has(column.key) || Boolean(column.customField && column.minWidth > 110)
const cardRowClass = (row, index) => props.rowClass?.({ row, rowIndex: index }) || ''
const emitSelection = () => emit('selection-change', props.rows.filter(row => selectedIds.value.includes(row.id)))
const toggleSelected = row => {
  selectedIds.value = selectedIds.value.includes(row.id) ? selectedIds.value.filter(id => id !== row.id) : [...selectedIds.value, row.id]
  emitSelection()
}
const toggleRow = row => {
  if (!canExpand(row)) return
  if (expanded.value.includes(row.id)) expanded.value = expanded.value.filter(id => id !== row.id)
  else { expanded.value = [...expanded.value, row.id]; void load(row) }
}
const clearSelection = () => {
  if (isMobile.value) { if (selectedIds.value.length) { selectedIds.value = []; emitSelection() } }
  else tableRef.value?.clearSelection()
}
watch(() => props.rows, rows => {
  const kept = selectedIds.value.filter(id => rows.some(row => row.id === id))
  if (kept.length !== selectedIds.value.length) { selectedIds.value = kept; emitSelection() }
})
watch(() => props.deleteMode, value => { if (!value && isMobile.value) clearSelection() })
watch(isMobile, () => nextTick(() => { selectedIds.value = [] }))
defineExpose({clearSelection,toggleRowExpansion:(row,...args)=>isMobile.value?toggleRow(row):tableRef.value?.toggleRowExpansion(row,...args)})
</script>

<style scoped>
.order-children{box-sizing:border-box;padding:12px;overflow:hidden}.order-children-toolbar{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}.order-children-toolbar>span{margin-right:auto}.order-index{display:flex;align-items:center;justify-content:center;gap:4px}
.annotation-order-table :deep(.annotation-expand-column){padding:0!important}.annotation-order-table :deep(.annotation-expand-column .cell){padding:0!important}.annotation-order-table :deep(.annotation-expand-column .el-table__expand-icon){display:none}

/* 手机端卡片列表 */
.order-cards{display:flex;flex-direction:column;gap:10px;min-width:0}
.order-cards.is-nested{gap:8px}
.order-cards__empty{padding:32px 0;color:var(--el-text-color-secondary);font-size:14px;text-align:center}
.order-card{min-width:0;padding:10px 12px;border:1px solid var(--el-border-color-lighter);border-radius:10px;background:var(--el-bg-color);box-shadow:0 1px 2px rgba(15,23,42,.04)}
.order-card.is-selected{border-color:var(--el-color-primary-light-5);background:var(--el-color-primary-light-9)}
.order-card.workbench-target-row{border-color:var(--el-color-primary);background:var(--el-color-primary-light-9)}
.order-card__head{display:flex;align-items:flex-start;gap:8px;min-width:0;padding-bottom:8px;border-bottom:1px dashed var(--el-border-color-lighter)}
.order-card__index{flex:none;min-width:22px;height:22px;border-radius:11px;background:var(--el-fill-color);color:var(--el-text-color-secondary);font-size:12px;line-height:22px;text-align:center}
.order-card__order{flex:1;min-width:0}
.order-card__fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px;margin:10px 0 0}
.order-card__field{min-width:0}
.order-card__field.is-wide{grid-column:1/-1}
.order-card__field dt{margin:0 0 2px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.4}
.order-card__field dd{margin:0;min-width:0;color:var(--el-text-color-primary);font-size:14px;line-height:1.5;word-break:break-word;overflow-wrap:anywhere}
.order-card__field dd :deep(.project-name-ellipsis){display:-webkit-box;max-width:100%;overflow:hidden;white-space:normal;text-align:left;-webkit-box-orient:vertical;-webkit-line-clamp:2}
.order-card__field dd :deep(.customer-progress-summary-link){display:-webkit-box;max-width:100%;overflow:hidden;white-space:normal;text-align:left;-webkit-box-orient:vertical;-webkit-line-clamp:3}
.order-card__foot{display:flex;align-items:center;gap:8px;min-width:0;margin-top:10px;padding-top:8px;border-top:1px solid var(--el-border-color-extra-light)}
.order-card__expand{display:inline-flex;align-items:center;gap:2px;color:var(--el-color-primary);font-size:13px;cursor:pointer}
.order-card__spacer{flex:1}
.order-card__actions{display:flex;align-items:center;justify-content:flex-end;min-width:0}
.order-children--card{margin-top:10px;padding:8px;border-radius:8px;background:var(--el-fill-color-lighter)}
.order-children--card .order-card{box-shadow:none}
</style>
