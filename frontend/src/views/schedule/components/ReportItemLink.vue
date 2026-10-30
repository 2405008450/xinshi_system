<template>
  <TechnicalTaskReference v-if="row.display_metadata?.technical_task_id" :task-id="row.display_metadata.technical_task_id" :label="text" :kind="kind === 'project' ? 'details' : 'progress'" />
  <el-popover v-else ref="popover" v-model:visible="visible" trigger="click" placement="left" :width="760" :z-index="zIndex" :popper-options="popoverOptions" popper-class="report-item-detail-popover" @show="load" @hide="cancel">
    <template #reference><el-button type="primary" link class="report-item-link" :aria-label="`${kind==='project'?'查看项目':'查看任务'}：${text}`" @click.stop="raise">{{text}}</el-button></template>
    <div ref="panel" class="report-item-detail" v-loading="loading">
      <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
      <template v-if="target?.sourceType==='technical'&&state.detail">
        <header><strong>开发任务详情</strong><el-button link @click="visible=false">关闭</el-button></header>
        <el-descriptions :column="2" border size="small"><el-descriptions-item v-for="field in technicalFields" :key="field.key" :label="field.label">{{state.detail[field.key]??'-'}}</el-descriptions-item></el-descriptions>
      </template>
      <template v-else-if="kind==='task'">
        <header><strong>任务详情</strong><el-button link @click="visible=false">关闭</el-button></header>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="项目 / 任务">{{row.task_name||'-'}}</el-descriptions-item>
          <el-descriptions-item label="订单号"><ReportItemLink v-if="identity.orderNo" :row="row" kind="project" :text="identity.orderNo" /><span v-else>-</span></el-descriptions-item>
          <el-descriptions-item label="任务类型" :span="2">{{(row.display_metadata?.report_types||[row.task_type]).join('、')}}</el-descriptions-item>
          <el-descriptions-item label="具体任务" :span="2">{{row.progress_content||'-'}}</el-descriptions-item>
          <el-descriptions-item label="工作量">{{row.display_metadata?.quantity??'-'}} {{row.display_metadata?.quantity_unit_other||row.display_metadata?.quantity_unit||''}}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{durationLabel(row.duration_minutes)}}</el-descriptions-item>
          <el-descriptions-item label="工作成果" :span="2">{{row.result_content||'-'}}</el-descriptions-item>
        </el-descriptions>
      </template>
      <template v-else>
        <AssociatedProjectDetailPanel v-if="target&&target.sourceType!=='consultation'" title="项目详情" :source-type="target.sourceType" :project-id="target.projectId" :state="state" @retry="load" @close="visible=false" @enter="enterProject" />
        <template v-else-if="state.detail"><header><strong>咨询详情</strong><el-button link @click="visible=false">关闭</el-button></header><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="field in consultationFields" :key="field.key" :label="field.label">{{state.detail[field.key]||'-'}}</el-descriptions-item></el-descriptions></template>
      </template>
    </div>
  </el-popover>
</template>
<script setup>
import {computed,defineAsyncComponent,nextTick,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {useRouter} from 'vue-router'
import {reportProjectIdentity,exactReportProject} from '@/utils/workReportTarget'
import {searchReportProjects} from '@/api/projectArrangements'
import {fetchAssociatedProject} from '@/api/associatedProjectDetail'
import api from '@/api/index'
import {associatedProjectError} from '@/utils/associatedProjectDetail'
import {arrangementProjectRoute} from '@/utils/resourceArrangements'
import {chatOverlayZIndex} from '@/utils/chatOverlay'
import {durationLabel} from '@/utils/workReportForm'
import TechnicalTaskReference from '@/components/common/TechnicalTaskReference.vue'
const AssociatedProjectDetailPanel=defineAsyncComponent(()=>import('@/components/project/AssociatedProjectDetailPanel.vue'))
const props=defineProps({row:{type:Object,required:true},kind:{type:String,default:'project'},text:{type:String,required:true}})
const router=useRouter(),visible=ref(false),loading=ref(false),error=ref(''),zIndex=ref(2100),target=ref(null)
const state=reactive({loading:false,detail:null,error:'',extras:{}})
const popover=ref(),panel=ref()
const observer=new ResizeObserver(()=>nextTick(()=>{if(visible.value)popover.value?.popperRef?.popperInstanceRef?.update()}))
watch(panel,value=>{observer.disconnect();if(value)observer.observe(value)},{flush:'post'})
const identity=computed(()=>reportProjectIdentity(props.row))
const consultationFields=[{key:'consultation_code',label:'咨询编号'},{key:'project_name',label:'项目名称'},{key:'client_name',label:'客户名称'},{key:'consultation_method',label:'咨询方式'},{key:'consultation_type',label:'咨询类型'},{key:'customer_source',label:'客户来源'}]
const technicalFields=[{key:'task_no',label:'任务编号'},{key:'name',label:'任务名称'},{key:'content',label:'具体任务'},{key:'progress',label:'进度（%）'},{key:'arranger_name',label:'安排人'},{key:'executor_name',label:'执行人'},{key:'adjustment',label:'反馈后调整'},{key:'notes',label:'备注'}]
const popoverOptions={modifiers:[{name:'preventOverflow',options:{rootBoundary:'viewport',altAxis:true,tether:false,padding:16}}]}
let sequence=0,controller
function raise(event){zIndex.value=chatOverlayZIndex(event.currentTarget)}
function cancel(){sequence++;controller?.abort();loading.value=false}
async function load(){
  cancel();if(props.kind==='task'&&identity.value.sourceType!=='technical')return
  const serial=sequence;controller=new AbortController();const signal=controller.signal
  loading.value=true;error.value='';target.value=null;Object.assign(state,{detail:null,error:'',extras:{}})
  try{
    const value={...identity.value}
    if(!value.sourceType)throw new Error('此工作记录尚未关联项目，请先在工作报告中选择项目')
    if(!value.projectId){
      const result=await searchReportProjects({project_type:value.category,keyword:value.orderNo,page:1,page_size:100},{signal})
      if(signal.aborted)return
      const match=exactReportProject(result.items,value.orderNo)
      if(!match)throw new Error('未找到唯一对应的项目，请核对订单号或重新选择项目')
      value.projectId=match.id
    }
    const result=value.sourceType==='technical'?{detail:await api.get(`/technical-development/tasks/${value.projectId}`,{signal})}:value.sourceType==='consultation'?{detail:await api.get(`/consultations/${value.projectId}`,{signal})}:await fetchAssociatedProject(value,signal)
    if(serial!==sequence)return
    const {detail,...extras}=result;target.value=value;Object.assign(state,{detail,extras})
  }catch(e){if(serial===sequence&&!signal.aborted)error.value=e.response||e.status?associatedProjectError(e):e.detail||e.message||'读取项目失败'}finally{if(serial===sequence)loading.value=false}
}
function enterProject(){visible.value=false;router.push(arrangementProjectRoute({source_type:target.value.sourceType,project_id:target.value.projectId}))}
watch(()=>[props.row,identity.value.projectId,identity.value.orderNo,identity.value.sourceType],()=>{visible.value=false;cancel()})
onBeforeUnmount(()=>{cancel();observer.disconnect()})
</script>
<style scoped>
.report-item-link{white-space:pre-wrap;text-align:left;height:auto;line-height:1.5;max-width:100%;overflow-wrap:anywhere;user-select:text}.report-item-detail{max-height:min(560px,calc(100vh - 140px));overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere}.report-item-detail header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
</style>
<style>.report-item-detail-popover{width:min(760px,calc(100vw - 32px))!important;max-width:calc(100vw - 32px)}</style>
