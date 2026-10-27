<template>
  <section class="issue-panel">
    <div class="issue-panel-heading">
      <p class="issue-hint">保存聊天中的信息、需求、讨论、决策、任务、异常、风险及标准。仅显示你有权查看的总结。</p>
      <div class="issue-panel-actions">
        <TableColumnSettings settings-key="resource-development-issues"
          v-model="columns"
          :columns="issueColumns"
          :column-count="2"
          title="总结字段"
          @reset="columns=[...defaultIssueColumns]"
        />
        <BatchDeleteToolbar v-if="rows.some(row=>row.can_delete) || deleteMode" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
        <el-button v-if="access.can_collect && !deleteMode" type="primary" @click="editorRef.open(null, null, 'arrangement')">新增总结</el-button>
      </div>
    </div>
    <el-alert v-if="!access.summary_ready" title="总结功能尚未完成数据库初始化，请联系管理员。" type="info" :closable="false" />
    <template v-else>
      <div class="issue-filters search-bar">
        <el-input v-model="filters.keyword" placeholder="内容、具体分类、来源、提出人、进展、备注" clearable @input="keywordChanged" @keyup.enter="query" />
        <el-select v-model="filters.category" placeholder="类别" clearable @change="query"><el-option v-for="category in issueCategories" :key="category.value" :value="category.value" :label="category.label" /></el-select>
        <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advanced" :count="advancedCount" popper-class="issue-advanced" @clear="clearAdvanced" @reset="reset">
          <div @focusin.stop>
            <AppForm :model="filters" label-position="top">
              <div class="issue-grid">
                <el-form-item label="执行/同步部门"><el-select v-model="filters.department_id" clearable filterable @change="query"><el-option v-for="department in departments" :key="department.id" :value="department.id" :label="department.name" /></el-select></el-form-item>
                <el-form-item label="提出人"><el-select v-model="filters.proposer_id" clearable filterable @change="query"><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
                <el-form-item label="执行/跟进人"><el-select v-model="filters.executor_id" clearable filterable @change="query"><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
                <el-form-item label="保存时间段" class="wide"><el-date-picker v-model="filters.saved_range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" clearable @change="query" /></el-form-item>
                <el-form-item label="预定完成日期" class="wide"><el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" clearable @change="query" /></el-form-item>
              </div>
            </AppForm>
          </div>
        </AdvancedFilterPopover>
        <el-button :type="filters.notified_me ? 'primary' : 'default'" :plain="filters.notified_me" :aria-pressed="filters.notified_me" title="查看通知对象包含我的总结（含多人、部门通知）" @click="filters.notified_me=!filters.notified_me;query()">@我</el-button>
        <el-button :type="filters.created_by_me ? 'primary' : 'default'" :plain="filters.created_by_me" :aria-pressed="filters.created_by_me" title="查看我新增或从聊天保存的总结" @click="filters.created_by_me=!filters.created_by_me;query()">我创建</el-button>
        <el-button :type="filters.proposer_id === access.user_id ? 'primary' : 'default'" :plain="filters.proposer_id === access.user_id" :aria-pressed="filters.proposer_id === access.user_id" title="查看提出人是我的总结" @click="filters.proposer_id=filters.proposer_id === access.user_id ? '' : access.user_id;query()">我提出</el-button>
      </div>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button text @click="reload">重试</el-button></el-alert>
      <el-table :row-class-name="({row})=>row.id===openIssueId?'summary-notification-target':''" ref="tableRef" v-loading="loading" :data="rows" row-key="id" border @selection-change="handleDeleteSelectionChange">
<OrderedTableColumns settings-key="resource-development-issues">
        <el-table-column v-if="deleteMode" type="selection" width="48" :selectable="row=>row.can_delete" />
        <el-table-column label="序号" width="70"><template #default="{ $index }">{{ (pagination.page-1)*pagination.limit+$index+1 }}</template></el-table-column>
        <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip>
          <template #default="{row}">
            <DevelopmentIssueDetail v-if="column.key==='content'" :row="row" :version="detailVersion" @source="locateSource"><template #reference><el-button link type="primary" class="summary-content-detail" aria-label="查看总结详情" title="点击内容查看总结详情">{{ row.content || '-' }}</el-button></template></DevelopmentIssueDetail>
            <template v-else-if="column.key==='source_title' && row.source_type==='manual'">手工新增</template>
            <el-button v-else-if="column.key==='source_title'" link type="primary" @click="locateSource(row)">{{ row.source_title }}</el-button>
            <template v-else>{{ cell(row,column.key) }}</template>
          </template>
        </el-table-column>
        <el-table-column v-if="!deleteMode" label="操作" fixed="right" width="170"><template #default="{row}"><el-button v-if="row.can_edit" link type="primary" @click="editorRef.open(row)">编辑</el-button><el-button v-if="row.category==='execution' && row.can_update_progress" link type="primary" @click="progressRef.open(row)">更新进度</el-button></template></el-table-column>
      </OrderedTableColumns>
</el-table>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" @current-change="pageChanged" @size-change="sizeChanged" />
    </template>
    <DevelopmentIssueEditor ref="editorRef" @saved="saved" /><IssueProgressEditor ref="progressRef" @saved="saved" />
  </section>
</template>
<script setup>
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import { useResourceIssues } from '@/composables/useResourceIssues'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { issueCategories, issueStatuses, issueColumns, defaultIssueColumns, cleanIssueColumns, issueParams, issueCategoryLabel, issueStatusSummary } from '@/utils/resourceIssues'
import { formatBusinessDateTime } from '@/utils/dateTime'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import DevelopmentIssueDetail from './DevelopmentIssueDetail.vue'
import DevelopmentIssueEditor from './DevelopmentIssueEditor.vue'
import IssueProgressEditor from './IssueProgressEditor.vue'
import './issueDialogs.css'
const {access,refreshIssueAccess}=useResourceIssues(), {openChat}=useProjectChatDock()
const props=defineProps({openIssueId:{type:String,default:''}})
const filters=reactive({keyword:'',category:'',department_id:'',proposer_id:'',executor_id:'',status:'',range:null,saved_range:null,notified_me:false,created_by_me:false}),pagination=reactive({page:1,limit:20,total:0})
const rows=ref([]),users=ref([]),departments=ref([]),tableRef=ref(),editorRef=ref(),progressRef=ref(),loading=ref(false),error=ref(''),advanced=ref(false),detailVersion=ref(0),columns=ref([...defaultIssueColumns])
const advancedCount=computed(()=>['department_id','proposer_id','executor_id','range','saved_range'].filter(key=>filters[key]?.length).length)
const visibleColumns=computed(()=>issueColumns.filter(c=>columns.value.includes(c.key)))
const columnKey=()=>`resource-development:issues:columns:v3:${access.user_id}`
watch(columns,value=>{if(access.user_id)localStorage.setItem(columnKey(),JSON.stringify(value))},{deep:true})
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:issueApi.remove,getLabel:row=>row.content.slice(0,60),reload:()=>reload(true),onDeleted:()=>detailVersion.value++,entityName:'开拓问题'})
let controller,sequence=0,timer,disposed=false
const cancelled=e=>['ERR_CANCELED','CanceledError','AbortError'].includes(e.code||e.name)
async function reload(keepDelete=false){
  clearTimeout(timer);controller?.abort();const seq=++sequence;if(!access.ready)return
  controller=new AbortController();loading.value=true;error.value='';if(!keepDelete)exitDeleteMode()
  try{const data=await issueApi.list(issueParams(filters,pagination),controller.signal);if(seq!==sequence)return;pagination.total=data.total;const last=Math.max(1,Math.ceil(data.total/pagination.limit));if(pagination.page>last){pagination.page=last;return reload(keepDelete)}rows.value=data.items;detailVersion.value++}
  catch(e){if(seq===sequence&&!cancelled(e))error.value=e.message}finally{if(seq===sequence)loading.value=false}
}
function query(){pagination.page=1;reload()}
function keywordChanged(value){clearTimeout(timer);controller?.abort();sequence++;if(!value)query();else timer=setTimeout(query,400)}
function clearAdvanced(){Object.assign(filters,{department_id:'',proposer_id:'',executor_id:'',status:'',range:null,saved_range:null});query()}
function reset(){Object.assign(filters,{keyword:'',category:'',department_id:'',proposer_id:'',executor_id:'',status:'',range:null,saved_range:null,notified_me:false,created_by_me:false});query()}
function pageChanged(){exitDeleteMode();reload()}
function sizeChanged(){pagination.page=1;pageChanged()}
function saved(){detailVersion.value++;reload();refreshIssueAccess(true).catch(()=>{})}
function cell(row,key){if(key==='category')return issueCategoryLabel(row.category);if(key.endsWith('_names'))return (row[key]||[]).join('、')||'-';if(key.endsWith('_at'))return formatBusinessDateTime(row[key]);return row[key]||'-'}
async function locateSource(row){try{const source=await issueApi.locateSource(row.id);if(!source.available){ElMessage.warning(source.reason);return}openChat({projectId:source.source_conversation_id,projectType:source.source_type,title:source.source_title,subtitle:'来源对话',messageId:source.source_message_id})}catch(e){ElMessage.error(e.message)}}
onMounted(async()=>{
  window.addEventListener('resource-issue-saved',saved)
  try{
    await refreshIssueAccess(true);if(disposed)return
    const raw=localStorage.getItem(columnKey()),legacy=localStorage.getItem(`resource-development:issues:columns:v2:${access.user_id}`)??localStorage.getItem(`resource-development:issues:columns:${access.user_id}`);try{const previous=legacy?cleanIssueColumns(JSON.parse(legacy)):null;columns.value=raw?cleanIssueColumns(JSON.parse(raw)):previous?.length?[...new Set([...previous,'notified_user_names'])]:previous||[...defaultIssueColumns];localStorage.setItem(columnKey(),JSON.stringify(columns.value))}catch{localStorage.removeItem(columnKey());columns.value=[...defaultIssueColumns]}
    if(access.ready&&access.can_enter){const options=await issueApi.options();if(disposed)return;users.value=options.users;departments.value=options.departments||[];await reload()}
  }catch(e){if(!disposed)error.value=e.message}
})
onBeforeUnmount(()=>{window.removeEventListener('resource-issue-saved',saved);disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
</script>
<style scoped>
.issue-panel-heading,.issue-panel-actions,.issue-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.issue-panel-heading{justify-content:space-between;margin-bottom:10px}.issue-hint{margin:0;color:var(--el-text-color-secondary);font-size:13px}.issue-filters{margin:0 0 14px;padding:12px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-page-bg)}.issue-filters>.el-input{width:340px}.issue-filters>.el-select{width:150px}.issue-panel .el-pagination{max-width:100%;overflow-x:auto}.issue-panel .el-alert{margin:12px 0}
@media(max-width:700px){.issue-filters>.el-input,.issue-filters>.el-select{width:100%}}
</style>
<style>.issue-advanced{max-width:calc(100vw - 32px)!important}</style>

<style scoped>.issue-panel :deep(.summary-notification-target>td.el-table__cell){background:var(--el-color-primary-light-9)}</style>

<style scoped>.summary-content-detail{width:100%;height:auto;justify-content:flex-start;text-align:left;white-space:pre-wrap;line-height:1.6}.summary-content-detail :deep(>span){display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;overflow-wrap:anywhere}</style>
