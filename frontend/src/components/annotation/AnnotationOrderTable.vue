<template>
  <el-table ref="tableRef" :data="rows" :height="nested ? undefined : '100%'" row-key="id" border
    :size="nested ? 'small' : undefined" :expand-row-keys="expanded" :row-class-name="rowClass"
    class="annotation-order-table project-detail-list-table" @expand-change="expandChanged" @selection-change="$emit('selection-change', $event)">
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
          <AnnotationOrderTable :rows="children[row.id] || []" :columns="columns" :editable="editable" :delete-mode="deleteMode" :conversation-picker="conversationPicker" nested
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
    <el-table-column label="订单号" width="200" :fixed="nested ? false : 'left'"><template #header><slot name="header" :column="{key:'orderNo',label:'订单号'}" /></template><template #default="{ row }"><slot name="order" :row="row" :toggle="() => tableRef.toggleRowExpansion(row)" /></template></el-table-column>
    <el-table-column v-for="column in columns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="!['projectName','projectStatus'].includes(column.key)">
      <template #header><slot name="header" :column="column" /></template><template #default="{ row }"><slot name="cell" :row="row" :column="column" /></template>
    </el-table-column>
    <el-table-column v-if="!conversationPicker" label="详情" width="100" fixed="right"><template #default="{ row }"><AnnotationProjectDetailPopover v-if="row.id" :project-id="row.id" :summary="row" :editable="editable && !deleteMode" @updated="$emit('updated', $event)"><template #reference><el-button link type="primary">查看详情</el-button></template></AnnotationProjectDetailPopover></template></el-table-column>
    <el-table-column v-if="!deleteMode" :label="conversationPicker ? '加入关注' : '操作'" width="120" fixed="right"><template #default="{ row }"><slot name="actions" :row="row" /></template></el-table-column>
  </el-table>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getAnnotationChildren } from '@/api/annotationProjects'
import AnnotationProjectDetailPopover from './AnnotationProjectDetailPopover.vue'
import TableExpandButton from '@/components/common/TableExpandButton.vue'
const props = defineProps({ rows: {type:Array,default:()=>[]}, columns: {type:Array,default:()=>[]}, editable:Boolean, deleteMode:Boolean, nested:Boolean, conversationPicker:Boolean, revision:Number, areaIds:Array, rowClass:Function, supportsGrandchildOrders:{type:Boolean,default:true} })
const emit = defineEmits(['selection-change','create','manage','updated'])
const tableRef = ref(), expanded = ref([]), loadingIds = reactive(new Set())
const containerWidth=ref(0)
let resizeObserver
onMounted(()=>{
  const element=tableRef.value?.$el
  if(!element)return
  const measure=()=>{containerWidth.value=element.clientWidth}
  measure();resizeObserver=new ResizeObserver(measure);resizeObserver.observe(element)
})
const children = reactive({}), totals = reactive({}), pages = reactive({}), errors = reactive({})
const requests = new Map()
const load = async row => {
  requests.get(row.id)?.abort(); const controller = new AbortController(); requests.set(row.id, controller)
  loadingIds.add(row.id); errors[row.id] = ''
  try {
    const page = await getAnnotationChildren(row.id, {skip:((pages[row.id] || 1)-1)*10,limit:10,area_ids:props.areaIds?.length ? props.areaIds : undefined}, {signal:controller.signal})
    if (requests.get(row.id) !== controller) return
    children[row.id] = page.items; totals[row.id] = page.total
  } catch (error) { if (requests.get(row.id) === controller && error.code !== 'ERR_CANCELED') errors[row.id] = error.detail || '下级订单加载失败' }
  finally { if (requests.get(row.id) === controller) loadingIds.delete(row.id) }
}
const expandChanged = (row, rows) => { expanded.value = rows.filter(item=>item.orderLevel<2).map(item=>item.id); if (expanded.value.includes(row.id)) void load(row) }
watch(()=>[props.revision, JSON.stringify(props.areaIds)],()=>{ for (const row of props.rows.filter(item=>expanded.value.includes(item.id))) { pages[row.id]=1; void load(row) } })
watch(()=>props.rows,()=>{ expanded.value=expanded.value.filter(id=>props.rows.some(row=>row.id===id)) })
onBeforeUnmount(()=>{resizeObserver?.disconnect();requests.forEach(controller=>controller.abort())})
defineExpose({clearSelection:()=>tableRef.value?.clearSelection(),toggleRowExpansion:(...args)=>tableRef.value?.toggleRowExpansion(...args)})
</script>

<style scoped>
.order-children{box-sizing:border-box;padding:12px;overflow:hidden}.order-children-toolbar{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}.order-children-toolbar>span{margin-right:auto}.order-index{display:flex;align-items:center;justify-content:center;gap:4px}
.annotation-order-table :deep(.annotation-expand-column){padding:0!important}.annotation-order-table :deep(.annotation-expand-column .cell){padding:0!important}.annotation-order-table :deep(.annotation-expand-column .el-table__expand-icon){display:none}
</style>
