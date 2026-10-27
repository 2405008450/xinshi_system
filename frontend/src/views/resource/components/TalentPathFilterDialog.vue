<template>
  <DraggableFormDialog v-model="visible" title="路径筛选" width="min(1600px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="talent-path-dialog" :before-close="beforeClose" @closed="cancelRequests">
    <div class="talent-path-filters">
      <label for="talent-path-registered">路径登记</label>
      <el-select id="talent-path-registered" v-model="registered" clearable placeholder="全部" aria-label="路径登记" :disabled="busy" @change="query"><el-option label="有" :value="true" /><el-option label="无" :value="false" /></el-select>
      <el-button type="primary" :disabled="busy" @click="query">查询</el-button><el-button :disabled="busy" @click="reset">重置</el-button>
      <span class="talent-path-hint">{{ canWrite ? '直接修改单元格后，点击本行“保存”；切换筛选、分页或关闭前请先保存或撤销。' : '当前账号为只读。' }}</span>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="talent-path-error"><el-button link type="primary" @click="load">重试</el-button></el-alert>
    <AppForm ref="formRef" :model="model" class="talent-path-table-form" @submit.prevent>
      <el-table v-loading="loading" :data="model.rows" border stripe row-key="id" height="100%" size="small" empty-text="暂无符合条件的人才记录">
        <el-table-column v-for="field in pathFields.filter(item=>item.key!=='resumePath')" :key="field.key" :label="field.label" :min-width="field.width">
          <template #default="{row,$index}"><el-form-item v-if="canWrite" class="talent-path-cell-form" :label="field.label" :prop="`rows.${$index}.${field.key}`" :rules="fieldRules(field)"><el-input v-model="row[field.key]" size="small" :maxlength="field.max" :aria-label="`${row.resourceCode} ${field.label}`" :disabled="row._saving" /></el-form-item><span v-else>{{ row[field.key] || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="联系方式" min-width="260">
          <template #default="{row,$index}"><details class="talent-path-contacts"><summary>点击展开联系方式</summary><dl>
            <template v-for="field in pathContactFields" :key="field.key"><dt>{{ field.label }}</dt><dd><el-form-item v-if="canWrite && !row.contactRestricted" class="talent-path-cell-form" :label="field.label" :prop="`rows.${$index}.${field.key}`" :rules="fieldRules(field)"><el-input v-model="row[field.key]" size="small" :maxlength="field.max" :aria-label="`${row.resourceCode} ${field.label}`" :disabled="row._saving" /></el-form-item><SensitiveContactValue v-else :value="row[field.key]" :restricted="row.contactRestricted === true" /></dd></template>
          </dl></details></template>
        </el-table-column>
        <el-table-column label="路径" min-width="300"><template #default="{row,$index}"><el-form-item v-if="canWrite" class="talent-path-cell-form" label="路径" :prop="`rows.${$index}.resumePath`" :rules="fieldRules(pathFields.find(item=>item.key==='resumePath'))"><el-input v-model="row.resumePath" size="small" maxlength="20000" :aria-label="`${row.resourceCode} 路径`" :disabled="row._saving" /></el-form-item><span v-else class="talent-path-value">{{ row.resumePath?.trim() || '-' }}</span></template></el-table-column>
        <el-table-column label="操作" width="155" fixed="right"><template #default="{row,$index}"><div class="talent-path-row-actions"><template v-if="canWrite"><el-button link type="primary" :loading="row._saving" :disabled="!isDirty(row)" @click="saveRow(row,$index)">保存</el-button><el-button link :disabled="row._saving || !isDirty(row)" @click="undoRow(row)">撤销</el-button></template><el-button link type="primary" @click="openHistory(row)">修改记录</el-button></div><p v-if="row._error" class="talent-path-save-error" role="alert">{{ row._error }}</p></template></el-table-column>
      </el-table>
    </AppForm>
    <template #footer><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :disabled="busy" :total="total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" @current-change="load" @size-change="query" /><el-button :disabled="busy" @click="requestClose">关闭</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="historyVisible" :title="`${historyName} · 修改记录`" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="talent-path-history-dialog" @closed="cancelHistory">
    <p class="talent-path-hint">记录本窗口保存的各字段修改；时间统一为 UTC+8。</p>
    <el-alert v-if="historyError" :title="historyError" type="error" :closable="false"><el-button link @click="loadHistory">重试</el-button></el-alert>
    <el-table v-loading="historyLoading" :data="historyRows" height="100%" border size="small" empty-text="暂无修改记录"><el-table-column prop="time" label="修改时间" width="180" /><el-table-column prop="actor" label="修改人" width="110" /><el-table-column prop="field" label="字段" width="120" /><el-table-column prop="before" label="修改前" min-width="200"><template #default="{row}"><span class="talent-path-value">{{ row.before || '-' }}</span></template></el-table-column><el-table-column prop="after" label="修改后" min-width="200"><template #default="{row}"><span class="talent-path-value">{{ row.after || '-' }}</span></template></el-table-column></el-table>
    <template #footer><el-pagination v-model:current-page="historyPage" :page-size="20" :total="historyTotal" layout="total, prev, pager, next" @current-change="loadHistory" /><el-button @click="historyVisible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTalentPathPage, patchTalentPathFields, getTalentPathHistory } from '@/api/talents'
import { pathFields, pathContactFields, allPathFields, pathSnapshot, pathChanges } from '@/utils/talentPathEditing'
import { formatBusinessDateTime } from '@/utils/dateTime'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
const props=defineProps({canWrite:Boolean})
const emit=defineEmits(['saved'])
const visible=ref(false),registered=ref(true),page=ref(1),pageSize=ref(20),total=ref(0),loading=ref(false),error=ref(''),formRef=ref(null)
const model=reactive({rows:[]}),busy=computed(()=>model.rows.some(row=>row._saving))
let controller,sequence=0,needsRefill=false,applied={page:1,pageSize:20,registered:true}
const isDirty=row=>Object.keys(pathChanges(row).changes).length>0
const fieldRules=field=>[...(field.required?[{required:true,whitespace:true,message:`请填写${field.label}`,trigger:'blur'}]:[]),{max:field.max,message:`最多${field.max}个字符`,trigger:'blur'}]
function dirtyGuard(){if(busy.value||model.rows.some(isDirty)){page.value=applied.page;pageSize.value=applied.pageSize;registered.value=applied.registered;ElMessage.warning('请先保存或撤销当前修改');return false}return true}
function cancelRequests(){controller?.abort();sequence++;loading.value=false}
function beforeClose(done){if(dirtyGuard())done()}
function requestClose(){beforeClose(()=>{visible.value=false})}
async function load(){
  if(!visible.value||!dirtyGuard())return
  controller?.abort();controller=new AbortController();const current=++sequence;error.value='';loading.value=true
  try{
    const result=await getTalentPathPage({registered:typeof registered.value==='boolean'?registered.value:undefined,skip:(page.value-1)*pageSize.value,limit:pageSize.value},{signal:controller.signal})
    if(current!==sequence)return
    const last=Math.max(1,Math.ceil(result.total/pageSize.value));if(page.value>last){page.value=last;return await load()}
    model.rows=(result.items||[]).map(row=>({...row,_original:pathSnapshot(row),_saving:false,_error:''}));total.value=result.total||0
    needsRefill=false
    applied={page:page.value,pageSize:pageSize.value,registered:registered.value}
    await nextTick();formRef.value?.clearValidate()
  }catch(failure){if(current===sequence&&failure.code!=='ERR_CANCELED')error.value=failure.detail||failure.message||'路径筛选加载失败，请重试'}
  finally{if(current===sequence)loading.value=false}
}
function query(){if(!dirtyGuard())return;page.value=1;return load()}
function reset(){if(!dirtyGuard())return;registered.value=null;return query()}
function open(){if(visible.value)return;registered.value=true;page.value=1;pageSize.value=20;total.value=0;model.rows=[];visible.value=true;return load()}
function undoRow(row){Object.assign(row,row._original);row._error='';formRef.value?.clearValidate();if(needsRefill&&!busy.value&&!model.rows.some(isDirty))void load()}
async function saveRow(row,index){
  if(row._saving||!isDirty(row))return
  row._saving=true;row._error=''
  try{
    const fields=allPathFields.filter(field=>!row.contactRestricted||!pathContactFields.includes(field)).map(field=>`rows.${index}.${field.key}`)
    if(!await formRef.value.validateField(fields).then(()=>true).catch(()=>false)){row._saving=false;await nextTick();await formRef.value.locateFirstError();return}
    const saved=await patchTalentPathFields(row.id,pathChanges(row));Object.assign(row,saved);row._original=pathSnapshot(saved)
    emit('saved',saved.id);ElMessage.success('已保存')
    const hasPath=!!saved.resumePath?.trim()
    if(typeof registered.value==='boolean'&&hasPath!==registered.value){model.rows=model.rows.filter(item=>item.id!==row.id);total.value=Math.max(0,total.value-1);needsRefill=true}
    row._saving=false
    if(needsRefill&&!busy.value&&!model.rows.some(isDirty))await load()
  }catch(failure){row._error=failure.detail||failure.message||'保存失败，当前输入已保留'}
  finally{row._saving=false}
}
const historyVisible=ref(false),historyName=ref(''),historyId=ref(null),historyPage=ref(1),historyTotal=ref(0),historyLoading=ref(false),historyError=ref(''),historyRows=ref([])
let historyController,historySequence=0
function cancelHistory(){historyController?.abort();historySequence++;historyLoading.value=false}
function openHistory(row){historyId.value=row.id;historyName.value=row.fullName;historyPage.value=1;historyTotal.value=0;historyRows.value=[];historyVisible.value=true;return loadHistory()}
async function loadHistory(){
  historyController?.abort();historyController=new AbortController();const seq=++historySequence;historyLoading.value=true;historyError.value=''
  try{const data=await getTalentPathHistory(historyId.value,{skip:(historyPage.value-1)*20,limit:20},{signal:historyController.signal});if(seq!==historySequence)return;historyTotal.value=data.total;historyRows.value=data.items.flatMap(item=>Object.entries(item.changes).map(([key,change])=>({id:`${item.id}:${key}`,time:formatBusinessDateTime(item.createdAt),actor:item.actorName,field:allPathFields.find(field=>field.key===key)?.label||key,before:change.before,after:change.after})))}
  catch(failure){if(seq===historySequence&&failure.code!=='ERR_CANCELED')historyError.value=failure.detail||failure.message||'修改记录加载失败'}
  finally{if(seq===historySequence)historyLoading.value=false}
}
onBeforeUnmount(()=>{cancelRequests();cancelHistory()})
defineExpose({open})
</script>
<style>
.talent-path-dialog{display:flex;flex-direction:column;height:90vh;max-height:90vh;overflow:hidden}
.talent-path-dialog>.el-dialog__body{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden;padding:10px 16px}
.talent-path-dialog>.el-dialog__header,.talent-path-dialog>.el-dialog__footer{flex-shrink:0}
.talent-path-dialog>.el-dialog__footer,.talent-path-history-dialog>.el-dialog__footer{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:8px 16px;border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-light)}
.talent-path-dialog .el-pagination{max-width:100%;overflow-x:auto}
.talent-path-table-form{flex:1;min-height:0;overflow:hidden}
.talent-path-filters{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;flex-shrink:0}
.talent-path-filters>.el-select{width:110px}
.talent-path-hint{font-size:12px;color:var(--el-text-color-secondary)}
.talent-path-error{margin-bottom:8px;flex-shrink:0}
.talent-path-cell-form.el-form-item{margin:0}
.talent-path-cell-form>.el-form-item__label{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);padding:0}
.talent-path-cell-form .el-form-item__content{line-height:24px}
.talent-path-cell-form .el-form-item__error{position:static}
.talent-path-contacts>summary{cursor:pointer;color:var(--el-color-primary);user-select:none}
.talent-path-contacts dl{display:grid;grid-template-columns:78px minmax(0,1fr);gap:4px 6px;margin:6px 0 0}
.talent-path-contacts dt{color:var(--el-text-color-secondary)}
.talent-path-contacts dd{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}
.talent-path-value{white-space:pre-wrap;overflow-wrap:anywhere;user-select:text}
.talent-path-row-actions{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.talent-path-row-actions .el-button{margin-left:0}
.talent-path-save-error{color:var(--el-color-danger);font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 0}
.talent-path-history-dialog{display:flex;flex-direction:column;height:min(650px,90vh);max-height:90vh;overflow:hidden}
.talent-path-history-dialog>.el-dialog__body{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden;padding:10px 16px}
.talent-path-history-dialog>.el-dialog__header,.talent-path-history-dialog>.el-dialog__footer{flex-shrink:0}
</style>
