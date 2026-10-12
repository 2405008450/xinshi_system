<template>
  <section class="issue-panel">
    <div class="issue-panel-heading"><h3>开拓问题</h3><div class="issue-panel-actions">
      <el-button v-if="access.can_collect && !deleteMode" type="primary" @click="editorRef.open(null, null, 'problem')">新增开拓事项</el-button>
      <el-popover trigger="click" placement="bottom-end" :width="280"><template #reference><el-button>字段设置</el-button></template><div class="issue-column-options"><el-checkbox-group v-model="columns"><el-checkbox v-for="column in issueColumns" :key="column.key" :value="column.key">{{ column.label }}</el-checkbox></el-checkbox-group></div><el-button text type="primary" @click="columns=[...defaultIssueColumns]">恢复默认</el-button></el-popover>
      <BatchDeleteToolbar v-if="rows.some(row=>row.can_delete) || deleteMode" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
    </div></div>
    <el-alert v-if="!access.ready" title="开拓问题尚未完成数据库迁移，请联系管理员。" type="info" :closable="false" />
    <template v-else>
      <p class="issue-hint">可从聊天消息收录，或直接新增开拓事项。仅显示你有权查看的内容。</p>
      <div class="issue-filters">
        <el-input v-model="filters.keyword" placeholder="内容、来源、提出人、执行人、进展、备注" clearable @input="keywordChanged" @keyup.enter="query" />
        <el-select v-model="filters.category" placeholder="类别" clearable @change="query"><el-option v-for="category in issueCategories" :key="category.value" :value="category.value" :label="category.label" /></el-select>
        <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">重置</el-button>
        <el-popover v-model:visible="advanced" trigger="click" placement="bottom-end" :width="760" popper-class="issue-advanced"><template #reference><el-button>高级筛选{{ advancedCount ? `（${advancedCount}）` : '' }}</el-button></template>
          <div class="issue-advanced-body" @focusin.stop><AppForm :model="filters" label-position="top"><div class="issue-grid">
            <el-form-item label="讨论主题"><ChatTopicSelect v-model="filters.topic_id" @change="query" /></el-form-item>
            <el-form-item label="提出人"><el-select v-model="filters.proposer_id" clearable filterable @change="query"><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
            <el-form-item label="执行人"><el-select v-model="filters.executor_id" clearable filterable @change="query"><el-option v-for="person in users" :key="person.id" :value="person.id" :label="person.name" /></el-select></el-form-item>
            <el-form-item label="任务状态"><el-select v-model="filters.status" clearable @change="query"><el-option v-for="status in issueStatuses" :key="status.value" :value="status.value" :label="status.label" /></el-select></el-form-item>
            <el-form-item label="预定完成日期" class="wide"><el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" clearable @change="query" /></el-form-item>
          </div></AppForm><div class="issue-panel-actions"><el-button @click="clearAdvanced">清空高级条件</el-button><el-button @click="advanced=false">关闭</el-button></div></div>
        </el-popover>
      </div>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button text @click="reload">重试</el-button></el-alert>
      <el-table ref="tableRef" v-loading="loading" :data="rows" row-key="id" border @selection-change="handleDeleteSelectionChange">
        <el-table-column v-if="deleteMode" type="selection" width="48" :selectable="row=>row.can_delete" />
        <el-table-column label="序号" width="70"><template #default="{ $index }">{{ (pagination.page-1)*pagination.limit+$index+1 }}</template></el-table-column>
        <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width" show-overflow-tooltip>
          <template #default="{row}">
            <template v-if="column.key==='source_title' && row.source_type==='manual'">手工新增</template>
            <el-button v-else-if="column.key==='source_title'" link type="primary" @click="locateSource(row)">{{ row.source_title }}</el-button>
            <el-button v-else-if="column.key==='task_count'" link type="primary" @click="tasksRef.open(row)">{{ row.task_count }} 条 · 查看安排</el-button>
            <template v-else>{{ cell(row,column.key) }}</template>
          </template>
        </el-table-column>
        <el-table-column label="详情" fixed="right" width="105"><template #default="{row}"><DevelopmentIssueDetail :row="row" :version="detailVersion" @source="locateSource" /></template></el-table-column>
        <el-table-column v-if="!deleteMode" label="操作" fixed="right" width="170"><template #default="{row}"><el-button v-if="row.can_edit" link type="primary" @click="editorRef.open(row)">编辑</el-button><el-button link type="primary" @click="tasksRef.open(row)">后续安排</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" @current-change="pageChanged" @size-change="sizeChanged" />
    </template>
    <DevelopmentIssueEditor ref="editorRef" @saved="saved" /><DevelopmentIssueTasks ref="tasksRef" @saved="saved" />
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { issueApi } from '@/api/resourceIssues'
import { useResourceIssues } from '@/composables/useResourceIssues'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { issueCategories, issueStatuses, issueColumns, defaultIssueColumns, cleanIssueColumns, issueParams, issueCategoryLabel, issueStatusSummary } from '@/utils/resourceIssues'
import { formatBusinessDateTime } from '@/utils/dateTime'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import DevelopmentIssueDetail from './DevelopmentIssueDetail.vue'
import DevelopmentIssueEditor from './DevelopmentIssueEditor.vue'
import DevelopmentIssueTasks from './DevelopmentIssueTasks.vue'
import './issueDialogs.css'
import ChatTopicSelect from '@/components/chat/ChatTopicSelect.vue'
const {access,refreshIssueAccess}=useResourceIssues(), {openChat}=useProjectChatDock()
const filters=reactive({keyword:'',category:'',topic_id:null,proposer_id:'',executor_id:'',status:'',range:null}),pagination=reactive({page:1,limit:20,total:0})
const rows=ref([]),users=ref([]),tableRef=ref(),editorRef=ref(),tasksRef=ref(),loading=ref(false),error=ref(''),advanced=ref(false),detailVersion=ref(0),columns=ref([...defaultIssueColumns])
const advancedCount=computed(()=>['topic_id','proposer_id','executor_id','status','range'].filter(key=>filters[key]?.length).length)
const visibleColumns=computed(()=>issueColumns.filter(c=>columns.value.includes(c.key)))
const columnKey=()=>`resource-development:issues:columns:${access.user_id}`
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
function clearAdvanced(){Object.assign(filters,{topic_id:null,proposer_id:'',executor_id:'',status:'',range:null});query()}
function reset(){Object.assign(filters,{keyword:'',category:'',topic_id:null,proposer_id:'',executor_id:'',status:'',range:null});query()}
function pageChanged(){exitDeleteMode();reload()}
function sizeChanged(){pagination.page=1;pageChanged()}
function saved(){detailVersion.value++;reload();refreshIssueAccess(true).catch(()=>{})}
function cell(row,key){if(key==='category')return issueCategoryLabel(row.category);if(key==='executor_names')return row.executor_names.join('、')||'-';if(key==='task_status_counts')return issueStatusSummary(row.task_status_counts);if(key.endsWith('_at'))return formatBusinessDateTime(row[key]);return row[key]||'-'}
async function locateSource(row){try{const source=await issueApi.locateSource(row.id);if(!source.available){ElMessage.warning(source.reason);return}openChat({projectId:source.source_conversation_id,projectType:source.source_type,title:source.source_title,subtitle:'来源对话',messageId:source.source_message_id})}catch(e){ElMessage.error(e.message)}}
onMounted(async()=>{
  window.addEventListener('resource-issue-saved',saved)
  try{
    await refreshIssueAccess(true);if(disposed)return
    const raw=localStorage.getItem(columnKey());try{columns.value=raw?cleanIssueColumns(JSON.parse(raw)):[...defaultIssueColumns];if(raw)localStorage.setItem(columnKey(),JSON.stringify(columns.value))}catch{localStorage.removeItem(columnKey());columns.value=[...defaultIssueColumns]}
    if(access.ready){const options=await issueApi.options();if(disposed)return;users.value=options.users;await reload()}
  }catch(e){if(!disposed)error.value=e.message}
})
onBeforeUnmount(()=>{window.removeEventListener('resource-issue-saved',saved);disposed=true;clearTimeout(timer);sequence++;controller?.abort()})
</script>
<style scoped>
.issue-panel-heading,.issue-panel-actions,.issue-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.issue-panel-heading{justify-content:space-between}.issue-filters{margin:16px 0}.issue-filters>.el-input{width:340px}.issue-filters>.el-select{width:150px}.issue-column-options{max-height:400px;overflow:auto}.issue-column-options .el-checkbox{display:flex}.issue-advanced-body{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.issue-panel .el-pagination{max-width:100%;overflow-x:auto}.issue-panel .el-alert{margin:12px 0}
@media(max-width:700px){.issue-filters>.el-input,.issue-filters>.el-select{width:100%}}
</style>
<style>.issue-advanced{max-width:calc(100vw - 32px)!important}</style>
