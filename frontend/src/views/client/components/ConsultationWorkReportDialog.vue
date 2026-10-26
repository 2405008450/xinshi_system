<template>
  <DraggableFormDialog :model-value="true" title="工作报告填写 - 新咨询对接" class="consultation-report-dialog" width="min(840px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :close-on-press-escape="false" :before-close="preventClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="工作报告填写 - 新咨询对接" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBody" v-loading="loading" data-screenshot-editor="own" @paste.capture="blockReportImages" @drop.capture="blockReportImages">
      <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error && !context" @click="load">重新加载</el-button>
      <template v-if="context">
        <el-descriptions :column="2" border size="small"><el-descriptions-item label="咨询编号">{{context.consultation_code}}</el-descriptions-item><el-descriptions-item label="客户名称">{{context.client_name}}</el-descriptions-item></el-descriptions>
        <p class="report-tip">保存后加入 {{context.report_date}} 的工作报告；香港时间每天早上 07:00 换日。请完成全部字段后保存，才能关闭窗口。</p>
        <AppForm ref="formRef" :model="form" :rules="rules" label-width="105px" @submit.prevent>
          <el-form-item label="工作类型"><ReadonlyField model-value="项目工作 / 新咨询对接" source="auto" /></el-form-item>
          <el-form-item label="订单号" prop="order_no"><el-input v-model="form.order_no" maxlength="100" /></el-form-item>
          <el-form-item label="项目名称" prop="task_name"><el-input v-model="form.task_name" maxlength="255" /></el-form-item>
          <el-form-item label="具体任务" prop="progress_content"><el-input v-model="form.progress_content" type="textarea" :rows="3" maxlength="10000" /></el-form-item>
          <el-row :gutter="16"><el-col :xs="24" :sm="8"><el-form-item label="工作量" prop="quantity"><el-input v-model="form.quantity" inputmode="decimal" placeholder="请填写" /></el-form-item></el-col>
            <el-col :xs="24" :sm="8"><el-form-item label="单位" prop="quantity_unit"><el-select v-model="form.quantity_unit" filterable allow-create default-first-option placeholder="填写或选择"><el-option v-for="unit in ['次','项','个','份','人','字','小时']" :key="unit" :label="unit" :value="unit" /></el-select></el-form-item></el-col>
            <el-col :xs="24" :sm="8"><el-form-item label="耗时" prop="duration_minutes"><el-select v-model="form.duration_minutes" filterable placeholder="请选择"><el-option v-for="value in durationOptions" :key="value" :label="durationLabel(value)" :value="value" /></el-select></el-form-item></el-col></el-row>
        </AppForm>
      </template>
    </div>
    <template #footer><el-button :disabled="loading || !context" :loading="saving" @click="save(true)">保存并继续新增</el-button><el-button type="primary" :disabled="loading || !context" :loading="saving" @click="save(false)">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,reactive,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getConsultationReportContext,saveConsultationReport} from '@/api/consultations'
import {blockReportImages,durationOptions,durationLabel,validQuantity} from '@/utils/workReportForm'
const props=defineProps({consultationId:{type:String,required:true}}),emit=defineEmits(['saved'])
const formRef=ref(),editorBody=ref(),context=ref(),loading=ref(false),saving=ref(false),error=ref('')
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBody)
const form=reactive({order_no:'',task_name:'',progress_content:'',quantity:'',quantity_unit:'',duration_minutes:null})
const required=message=>[{required:true,message,trigger:['blur','change']}]
const rules={order_no:required('请输入订单号'),task_name:required('请输入项目名称'),progress_content:required('请输入具体任务'),quantity:[{required:true,validator:(_r,v,done)=>done(v!==''&&v!=null&&validQuantity(v)?undefined:new Error('请填写非负数字工作量')),trigger:['blur','change']}],quantity_unit:required('请填写单位'),duration_minutes:required('请选择本次新咨询对接耗时')}
function preventClose(){ElMessage.warning('请先完整填写并保存本次新咨询工作报告')}
let active=true
async function load(){loading.value=true;error.value='';try{const data=await getConsultationReportContext(props.consultationId);if(!active)return;if(data.completed){emit('saved',{result:data,continueCreate:false});return}context.value=data;for(const key of ['order_no','task_name','progress_content'])form[key]=data[key]}catch(e){if(active)error.value=e.detail||'加载待填工作报告失败，请重试'}finally{if(active)loading.value=false}}
async function save(continueCreate){if(saving.value||!context.value)return;if(!await formRef.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{const result=await saveConsultationReport(props.consultationId,form);emit('saved',{result,continueCreate})}catch(e){error.value=e.detail||'保存失败，请重试'}finally{saving.value=false}}
onMounted(load);onBeforeUnmount(()=>{active=false})
</script>
<style>
.consultation-report-dialog .app-window-controls button:first-child,.consultation-report-dialog .app-window-controls button:last-child{display:none}
.consultation-report-dialog .el-dialog__header,.consultation-report-dialog .el-dialog__footer{flex-shrink:0}
.consultation-report-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden}
.consultation-report-dialog .el-dialog__footer{background:#f8fafc;border-top:1px solid #e2e8f0}
.consultation-report-dialog .report-tip{font-size:13px;color:#64748b;line-height:1.6}
.consultation-report-dialog .el-select{width:100%}
</style>
