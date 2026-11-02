<template>
  <section class="annotation-operations" v-loading="loading">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div class="operation-layout-toolbar"><span>任务布局</span><el-radio-group v-model="layoutColumns" size="small" aria-label="任务布局"><el-radio-button value="1">纵向</el-radio-button><el-radio-button value="2">两列</el-radio-button><el-radio-button value="3">三列</el-radio-button></el-radio-group></div>
    <div class="operation-groups" :data-columns="layoutColumns" :style="{'--operation-columns':layoutColumns}">
    <section v-for="group in groups" :key="group.key" class="operation-group" @dragover.prevent @drop.prevent="drop($event,group.key)">
      <div class="operation-group__header">
        <h4>{{group.label}}（{{items.filter(row=>row.stage===group.key).length}}）</h4>
        <div v-if="group.key!=='performed'" class="operation-entry-actions"><el-button v-for="type in entryTypes" :key="type" size="small" :disabled="busy||loading||!workDate" @click="openEntry(type,group.key)">{{type}}</el-button></div>
      </div>
      <div v-if="pickerStage===group.key" class="operation-picker">
        <p>仅显示“是否今日进行”为“今日进行中”的标注项目（可多选）</p>
        <el-checkbox-group v-model="selectedIds"><el-checkbox v-for="project in projects" :key="project.id" :value="project.id">{{project.orderNo}} · {{project.projectName}}</el-checkbox></el-checkbox-group>
        <el-empty v-if="!projects.length" description="暂无今日进行中的标注项目" :image-size="48" />
        <el-button type="primary" :disabled="!selectedIds.length||busy" @click="openCreate">填写具体操作</el-button>
      </div>
      <p v-if="group.key==='performed'" class="operation-hint">可将进行中任务拖至此处；实际用时默认复制预计用时，可修改后加入工作报告。</p>
      <p v-if="group.key==='in_progress'" class="operation-hint">可将待进行任务拖至此处开始进行。</p>
      <article v-for="row in items.filter(item=>item.stage===group.key)" :key="row.id" class="operation-card" :class="{'is-added':row.report_added}" :draggable="['pending','in_progress'].includes(row.stage)&&!row.report_added&&!busy" @dragstart="startDrag($event,row)" @dragend="draggedId=''">
        <el-tag size="small" class="operation-type">{{row.project_type==='非项目工作'?'非项目任务':row.project_type||'标注项目'}}</el-tag>
        <strong>{{rowTitle(row)}}</strong>
        <p class="operation-content">{{row.content}}</p>
        <p class="operation-hint">今日预计花费时间：{{durationLabel(row.estimated_minutes)}}<template v-if="row.stage==='performed'"> · 今日实际花费时间：{{durationLabel(row.actual_minutes)}} · 工作量：{{row.quantity??'-'}} {{row.unit}}</template></p>
        <div class="operation-actions">
          <template v-if="!row.report_added">
            <el-button link type="primary" :disabled="busy" @click="openEdit(row)">编辑操作</el-button>
            <el-button v-if="row.stage==='pending'" :disabled="busy" @click="move(row,'in_progress')">开始进行</el-button>
            <el-button v-if="row.stage==='in_progress'" :disabled="busy" @click="move(row,'performed')">移至已进行任务</el-button>
            <el-button v-if="row.stage==='performed'" type="primary" plain :disabled="busy" @click="openEdit(row,true)">加至工作报告</el-button>
          </template>
          <el-button v-else type="success" plain disabled>已加入工作报告</el-button>
        </div>
      </article>
      <el-empty v-if="!items.some(row=>row.stage===group.key)" :description="`暂无${group.label}`" :image-size="48" />
    </section>
    </div>
    <DraggableFormDialog v-model="editorVisible" :title="editorTitle" width="min(920px, calc(100vw - 32px))" top="5vh" class="annotation-operation-editor" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :before-close="done=>{if(!busy)done()}">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editorTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editorBody">
        <AppForm ref="form" :model="draft" label-position="top" :disabled="busy">
          <section v-for="(project,p) in draft.projects" :key="project.project_id" class="operation-edit-project" data-dialog-field-search-group :data-dialog-field-search-group-title="project.name">
            <h4>{{project.name}}</h4>
            <div v-for="(operation,i) in project.operations" :key="i" class="operation-edit-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`${project.name} · 操作${i+1}`">
              <el-form-item label="具体操作" :prop="`projects.${p}.operations.${i}.content`" :rules="[{required:true,whitespace:true,message:'请填写具体操作',trigger:'blur'}]"><el-input v-model="operation.content" type="textarea" :rows="3" maxlength="10000" placeholder="填写具体内容" /></el-form-item>
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12"><el-form-item label="今日预计花费时间" :prop="`projects.${p}.operations.${i}.estimated_minutes`" :rules="[{required:true,message:'请选择预计花费时间',trigger:'change'}]"><el-select v-model="operation.estimated_minutes" filterable placeholder="选择预计用时"><el-option v-if="operation.estimated_minutes===0" :value="0" label="未填写" /><el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" /></el-select></el-form-item></el-col>
                <template v-if="editing?.stage==='performed'">
                  <el-col :xs="24" :sm="12"><el-form-item label="今日实际花费时间" :prop="`projects.${p}.operations.${i}.actual_minutes`" :rules="[{required:true,message:'请选择实际花费时间',trigger:'change'}]"><el-select v-model="operation.actual_minutes" filterable><el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" /></el-select></el-form-item></el-col>
                  <el-col :xs="24" :sm="12"><el-form-item label="工作量" :prop="`projects.${p}.operations.${i}.quantity`" :rules="[{validator:quantityRule,trigger:'blur'}]"><el-input v-model="operation.quantity" inputmode="decimal" placeholder="填写非负数字工作量" /></el-form-item></el-col>
                  <el-col :xs="24" :sm="12"><el-form-item label="单位" :prop="`projects.${p}.operations.${i}.unit`" :rules="[{required:true,whitespace:true,message:'请选择或填写单位',trigger:'change'}]"><el-select v-model="operation.unit" filterable allow-create default-first-option placeholder="选择或输入单位"><el-option v-for="unit in units" :key="unit" :value="unit" :label="unit==='其他'?'其他（填写单位）':unit" /></el-select></el-form-item><el-form-item v-if="operation.unit==='其他'" label="具体单位" :prop="`projects.${p}.operations.${i}.unit_other`" :rules="[{required:true,whitespace:true,message:'请填写具体单位',trigger:'blur'}]"><el-input v-model="operation.unit_other" maxlength="50" /></el-form-item></el-col>
                </template>
              </el-row>
              <el-button v-if="!editing&&project.operations.length>1" link type="danger" @click="project.operations.splice(i,1)">移除此操作</el-button>
            </div>
            <el-button v-if="!editing" @click="project.operations.push(emptyOperation())">增加具体操作</el-button>
          </section>
        </AppForm>
      </div>
      <template #footer><el-button :disabled="busy" @click="editorVisible=false">取消</el-button><el-button type="primary" :loading="busy" @click="save">{{addingReport?'保存并加至工作报告':'保存操作'}}</el-button></template>
    </DraggableFormDialog>
    <ReportProjectPicker v-if="projectPickerVisible" v-model="projectPickerVisible" :project-type="creationType" :task-scope="creationType==='口译项目'" @selected="selectProject" />
  </section>
</template>

<script setup>
import {computed,defineAsyncComponent,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getAnnotationOperations,createAnnotationOperations,editAnnotationOperation,addAnnotationOperationReport,importTranslationOperations} from '@/api/projectArrangements'
import {durationOptions,durationLabel,validQuantity} from '@/utils/workReportForm'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const groups=[{key:'performed',label:'已进行任务'},{key:'in_progress',label:'进行中任务'},{key:'pending',label:'待进行任务'}]
const entryTypes=['标注项目','笔译项目','口译项目','招聘项目','非项目任务']
const ReportProjectPicker=defineAsyncComponent(()=>import('@/components/common/ReportProjectPicker.vue'))
const creationType=ref('标注项目'),creationStage=ref('in_progress'),projectPickerVisible=ref(false)
const rowTitle=row=>[row.order_no,row.project_name].filter(Boolean).join(' · ')||'非项目任务'
const units=['个','份','页','字','次','人','其他']
let layoutStorageKey='annotation-operations-layout:anonymous'
try{layoutStorageKey=`annotation-operations-layout:${localStorage.getItem('user_id')||'anonymous'}`}catch{/* 使用默认布局配置。 */}
function readLayout(){try{const value=localStorage.getItem(layoutStorageKey);return ['1','2','3'].includes(value)?value:'1'}catch{return '1'}}
const layoutColumns=ref(readLayout())
watch(layoutColumns,value=>{try{localStorage.setItem(layoutStorageKey,value)}catch{/* 不影响布局切换。 */}})
const items=ref([]),projects=ref([]),loading=ref(false),busy=ref(false),error=ref(''),workDate=ref('')
const pickerStage=ref('in_progress'),selectedIds=ref([]),draggedId=ref(''),editorVisible=ref(false),editing=ref(null),addingReport=ref(false)
const draft=reactive({projects:[]}),form=ref(),editorBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const editorTitle=computed(()=>addingReport.value?'加至工作报告':editing.value?'编辑具体操作':'填写具体操作')
let controller,requestId=0
const emptyOperation=()=>({content:'',estimated_minutes:null})
async function load(){controller?.abort();controller=new AbortController();const id=++requestId;loading.value=true;error.value='';try{const data=await getAnnotationOperations({signal:controller.signal});if(id!==requestId)return;items.value=data.items;projects.value=data.projects;workDate.value=data.work_date}catch(e){if(id===requestId&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取今日任务失败'}finally{if(id===requestId)loading.value=false}}
async function togglePicker(stage){if(busy.value)return;pickerStage.value=pickerStage.value===stage?'':stage;selectedIds.value=[];if(pickerStage.value)await load()}
function openCreate(){creationType.value='标注项目';creationStage.value=pickerStage.value;editing.value=null;addingReport.value=false;draft.projects=projects.value.filter(row=>selectedIds.value.includes(row.id)).map(row=>({project_id:row.id,name:`${row.orderNo} · ${row.projectName}`,operations:[emptyOperation()]}));if(!draft.projects.length)return;editorVisible.value=true}
async function openEntry(type,stage){
  if(busy.value||loading.value)return
  if(type==='标注项目')return togglePicker(stage)
  if(type==='笔译项目'){
    busy.value=true;controller?.abort();requestId++;loading.value=false
    try{const data=await importTranslationOperations({work_date:workDate.value,stage});items.value=data.items;ElMessage.success(data.added?`已加入${data.added}项笔译任务`:(data.matched?'安排给自己的笔译任务已在任务区中':'暂无安排给自己的未完成笔译任务'))}catch(e){ElMessage.error(e.detail||'读取笔译任务失败')}finally{busy.value=false}
    return
  }
  creationType.value=type;creationStage.value=stage;editing.value=null;addingReport.value=false
  if(type==='非项目任务'){draft.projects=[{project_id:null,name:'非项目任务',operations:[emptyOperation()]}];editorVisible.value=true}
  else projectPickerVisible.value=true
}
function selectProject(project){draft.projects=[{project_id:project.id,name:`${project.order_no} · ${project.project_name}`,operations:[emptyOperation()]}];editorVisible.value=true}
function openEdit(row,report=false){editing.value=row;addingReport.value=report;draft.projects=[{project_id:row.project_id,name:rowTitle(row),operations:[{content:row.content,estimated_minutes:row.estimated_minutes,actual_minutes:row.actual_minutes||row.estimated_minutes,quantity:row.quantity??'',unit:row.unit||''}]}];editorVisible.value=true}
function quantityRule(_rule,value,done){done(value!==''&&value!=null&&validQuantity(value)?undefined:new Error('请填写非负数字工作量'))}
const editPayload=(row,operation,stage=row.stage)=>({revision:row.revision,stage,content:operation.content,estimated_minutes:operation.estimated_minutes,actual_minutes:operation.actual_minutes??row.actual_minutes,quantity:operation.quantity===''||operation.quantity==null?null:operation.quantity,unit:operation.unit==='其他'?operation.unit_other:operation.unit||''})
function replace(row){const index=items.value.findIndex(item=>item.id===row.id);if(index>=0)items.value[index]=row}
async function save(){
  if(busy.value)return
  try{await form.value.validate()}catch{return}
  busy.value=true
  try{
    if(editing.value){const row=await editAnnotationOperation(editing.value.id,editPayload(editing.value,draft.projects[0].operations[0]));replace(row);editing.value=row;if(addingReport.value){const added=await addAnnotationOperationReport(row.id,{revision:row.revision});replace(added);window.dispatchEvent(new CustomEvent('annotation-operation-report-added'))}}
    else{const result=await createAnnotationOperations({work_date:workDate.value,project_type:creationType.value,stage:creationStage.value,projects:draft.projects.map(({project_id,operations})=>({project_id,operations}))});items.value.push(...result.items);pickerStage.value='';selectedIds.value=[]}
    editorVisible.value=false;ElMessage.success(addingReport.value?'已加入工作报告':'具体操作已保存')
  }catch(e){ElMessage.error(e.detail||'保存失败，请重试')}finally{busy.value=false}
}
async function move(row,stage){if(busy.value||row.report_added)return;busy.value=true;try{replace(await editAnnotationOperation(row.id,editPayload(row,{...row,content:row.content},stage)));ElMessage.success(stage==='performed'?'已移至已进行任务，实际用时已复制':'已开始进行')}catch(e){ElMessage.error(e.detail||'移动失败，请刷新后重试')}finally{busy.value=false}}
function startDrag(event,row){if(!['pending','in_progress'].includes(row.stage)||row.report_added||busy.value){event.preventDefault();return}draggedId.value=row.id;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',row.id)}
function drop(_event,stage){const row=items.value.find(item=>item.id===draggedId.value);draggedId.value='';if(!row)return;if(row.stage==='pending'&&stage==='in_progress'||row.stage==='in_progress'&&stage==='performed')move(row,stage)}
function refresh(){if(!busy.value&&!editorVisible.value)load()}
onMounted(()=>{load();window.addEventListener('annotation-work-status-updated',refresh);window.addEventListener('focus',refresh)})
onBeforeUnmount(()=>{controller?.abort();requestId++;window.removeEventListener('annotation-work-status-updated',refresh);window.removeEventListener('focus',refresh)})
</script>

<style scoped>
.annotation-operations{border-top:1px solid var(--el-border-color-light);margin-top:24px;padding-top:8px;container-type:inline-size}.operation-group{min-width:0;margin:0;padding:16px;border:1px solid var(--el-border-color-light);border-radius:8px;min-height:120px}.operation-group__header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.operation-group h4{margin:0;font-size:15px}.operation-card{margin-top:12px;padding:12px;border:1px solid var(--el-border-color-light);border-radius:6px}.operation-card[draggable=true]{cursor:grab}.operation-card.is-added{border-color:var(--el-color-success-light-5);background:var(--el-color-success-light-9)}.operation-card.is-added .el-button.is-disabled{color:var(--el-color-success);border-color:var(--el-color-success-light-5)}.operation-content{white-space:pre-wrap;overflow-wrap:anywhere}.operation-hint{font-size:13px;color:var(--el-text-color-secondary)}.operation-picker{padding:12px 0}.operation-picker :deep(.el-checkbox-group){display:flex;flex-direction:column;align-items:flex-start;margin-bottom:12px}.operation-picker :deep(.el-checkbox){max-width:100%;height:auto;min-height:32px;white-space:normal}.operation-picker :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}.operation-actions{display:flex;gap:8px;flex-wrap:wrap}.operation-actions .el-button{margin-left:0}.operation-edit-project{margin-bottom:20px}.operation-edit-row{border-top:1px solid var(--el-border-color-lighter);padding:12px 0}.operation-edit-row .el-select{width:100%}
.operation-entry-actions{display:flex;gap:6px;flex-wrap:wrap;width:100%}.operation-entry-actions .el-button{margin-left:0}.operation-type{margin-right:6px;margin-bottom:6px}.operation-layout-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:12px;flex-wrap:wrap;margin-top:12px}.operation-groups{display:grid;grid-template-columns:repeat(var(--operation-columns,1),minmax(0,1fr));gap:16px;margin:16px 0;align-items:start}.operation-card strong{overflow-wrap:anywhere}.operation-group :deep(.el-empty__description){overflow-wrap:anywhere}
@container (max-width:760px){.operation-groups[data-columns="3"]{grid-template-columns:repeat(2,minmax(0,1fr))}}
@container (max-width:640px){.operation-groups[data-columns]{grid-template-columns:minmax(0,1fr)}}
</style>
<style>
.annotation-operation-editor.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.annotation-operation-editor .el-dialog__header,.annotation-operation-editor .el-dialog__footer{flex-shrink:0}.annotation-operation-editor .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.annotation-operation-editor .el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-light)}
</style>
