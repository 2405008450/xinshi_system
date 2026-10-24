<template>
  <div>
    <div class="paired-toolbar">
      <el-input v-model="keyword" :placeholder="searchPlaceholder" clearable style="width:260px" @input="schedule" @keyup.enter="query" />
      <el-button @click="query">查询</el-button><el-button @click="reset">重置</el-button>
      <span class="spacer" />
      <TableColumnSettings v-model="selectedKeys" :columns="columns" @reset="resetColumns" />
      <BatchDeleteToolbar v-if="editable" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
      <slot v-if="!deleteMode" name="toolbar" />
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table ref="tableRef" :data="rows" row-key="id" border v-loading="loading" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="index" label="序号" width="65" />
      <el-table-column v-for="column in shownColumns" :key="column.key" :label="column.label" :min-width="column.width || 160" show-overflow-tooltip>
        <template #header><ConfiguredColumnHeaderFilter v-if="column.filter" :definition="column.filter" :model-value="filters[column.key]" @update:model-value="filters[column.key]=$event" @text-input="schedule" @change="query" @enter="query" @clear="query" /><span v-else>{{column.label}}</span></template>
        <template #default="{row}"><slot name="cell" :row="row" :column="column"><span>{{display(row,column)}}</span></slot></template>
      </el-table-column>
      <el-table-column label="详情" width="100" fixed="right"><template #default="{row}"><BusinessDetailPopover :row="row" title="双人采标详情"><template #content><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="column in columns" :key="column.key" :label="column.label">{{display(row,column)}}</el-descriptions-item><slot name="details" :row="row" /></el-descriptions></template></BusinessDetailPopover></template></el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" width="250" fixed="right"><template #default="{row}"><slot name="actions" :row="row" /></template></el-table-column>
    </el-table>
    <el-pagination :current-page="pagination.page" :page-size="pagination.limit" :total="pagination.total" layout="total, prev, pager, next" @current-change="changePage" />
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {useBatchDelete} from '@/composables/useBatchDelete'
import * as api from '@/api/annotationPaired'
const props=defineProps({projectId:String,kind:String,columns:Array,editable:Boolean,searchPlaceholder:{type:String,default:'搜索名称'}})
const rows=ref([]),tableRef=ref(),loading=ref(false),error=ref(''),keyword=ref(''),filters=reactive({}),pagination=reactive({page:1,limit:20,total:0})
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns(`paired-${props.kind}`,props.columns,props.columns.filter(item=>item.default!==false).map(item=>item.key))
const shownColumns=computed(()=>props.columns.filter(item=>isVisible(item.key)))
const display=(row,column)=>{const value=column.format ? column.format(row) : column.key.split('.').reduce((value,key)=>value?.[key],row);return value==null||value===''?'-':value}
let controller,sequence=0,timer
const reload=async()=>{clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;error.value='';try{const page=await api.list(props.projectId,props.kind,{keyword:keyword.value,statuses:filters.status || filters.willingness || [],skip:(pagination.page-1)*pagination.limit,limit:pagination.limit},controller.signal);if(current!==sequence)return;rows.value=page.items;pagination.total=page.total;if(!rows.value.length&&pagination.page>1){pagination.page=Math.max(1,Math.ceil(page.total/pagination.limit));await reload()}}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=typeof e.detail==='string'?e.detail:'加载失败'}finally{if(current===sequence)loading.value=false}}
const query=()=>{pagination.page=1;return reload()}
const schedule=()=>{clearTimeout(timer);if(!keyword.value)query();else timer=setTimeout(query,400)}
const reset=()=>{keyword.value='';Object.keys(filters).forEach(key=>delete filters[key]);query()}
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:row=>api.deleteRow(props.projectId,['collection','annotation'].includes(props.kind)?'tasks':props.kind,row.id),getLabel:row=>row.name || row.person?.full_name || '联系人',reload,entityName:'双人采标记录'})
const changePage=page=>{exitDeleteMode();pagination.page=page;reload()}
watch(()=>props.editable,value=>{if(!value)exitDeleteMode()})
onMounted(reload)
onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort();sequence++})
defineExpose({reload,query})
</script>
<style scoped>.paired-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}.spacer{flex:1}.el-pagination{margin-top:12px}.el-table :deep(.cell){white-space:normal;overflow-wrap:anywhere}</style>
