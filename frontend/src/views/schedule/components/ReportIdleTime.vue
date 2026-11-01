<template>
  <section class="report-idle-time">
    <template v-if="editable">
      <div class="idle-summary">
        <el-button type="primary" @click="openDialog">填写空闲时间</el-button>
        <span>空闲时间（包括洗手间等所有非工作时间）：<strong>{{minutes==null?'未填写':durationLabel(minutes)}}</strong></span>
        <el-tag :type="confirmed?'success':'warning'">{{confirmed?'声明已确认':'待填写并确认声明'}}</el-tag>
      </div>
      <DraggableFormDialog v-model="visible" title="填写空闲时间" width="min(720px, calc(100vw - 32px))" top="5vh" class="report-idle-dialog" append-to-body destroy-on-close :close-on-click-modal="false">
        <AppForm ref="form" :model="model" :rules="rules" label-position="top" @submit.prevent="confirm">
          <el-form-item label="空闲时间（包括洗手间等所有非工作时间）" prop="minutes">
            <el-select v-model="model.minutes" filterable placeholder="请选择时长" aria-label="空闲时间耗时" @change="model.confirmed=false">
              <el-option :value="0" label="0分钟" />
              <el-option v-if="validIdleMinutes(model.minutes)&&model.minutes>0&&!durationOptions.includes(model.minutes)" :value="model.minutes" :label="durationLabel(model.minutes)" />
              <el-option v-for="minutes in durationOptions" :key="minutes" :value="minutes" :label="durationLabel(minutes)" />
            </el-select>
          </el-form-item>
          <el-form-item label="声明确认" prop="confirmed">
            <p class="idle-declaration">{{declarationText||idleDeclarationText}}</p>
            <el-checkbox v-model="model.confirmed" aria-label="本人已阅读并确认上述声明">本人已阅读并确认上述声明</el-checkbox>
          </el-form-item>
        </AppForm>
        <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" @click="confirm">确认</el-button></template>
      </DraggableFormDialog>
    </template>
    <template v-else><p><strong>空闲时间（包括洗手间等所有非工作时间）：</strong>{{minutes==null?'未填写':`${minutes}分钟`}}</p><p class="idle-declaration">{{declarationText||idleDeclarationText}}</p><el-tag :type="confirmed?'success':'info'">{{confirmed?'声明已确认':'声明未确认'}}</el-tag></template>
  </section>
</template>
<script setup>
import {nextTick,reactive,ref,watch} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import {durationOptions,durationLabel} from '@/utils/workReportForm'
import {idleDeclarationText,validIdleMinutes} from '@/utils/workReportIdle'
const props=defineProps({minutes:{type:Number,default:null},confirmed:Boolean,declarationText:{type:String,default:''},editable:Boolean,reportDate:String})
const emit=defineEmits(['update:minutes','update:confirmed','change'])
const form=ref(),visible=ref(false),model=reactive({minutes:null,confirmed:false})
watch(()=>props.reportDate,()=>{visible.value=false})
const rules={
  minutes:[{required:true,validator:(_rule,value,done)=>done(validIdleMinutes(value)?undefined:new Error('请选择空闲时间')),trigger:'change'}],
  confirmed:[{required:true,validator:(_rule,value,done)=>done(value===true?undefined:new Error('请勾选确认声明')),trigger:'change'}],
}
function openDialog(){model.minutes=props.minutes;model.confirmed=props.confirmed;visible.value=true;nextTick(()=>form.value?.clearValidate())}
async function confirm(){try{await form.value.validate()}catch{return}emit('update:minutes',model.minutes);emit('update:confirmed',true);emit('change');visible.value=false}
async function validate(){if(!props.editable||validIdleMinutes(props.minutes)&&props.confirmed)return true;openDialog();await nextTick();await form.value.validate();throw new Error('请确认空闲时间和声明')}
defineExpose({validate})
</script>
<style scoped>.report-idle-time{padding:14px 16px;border:1px solid var(--el-border-color);border-radius:6px;margin:14px 0;background:#fff}.idle-summary{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.idle-declaration{width:100%;margin:0 0 8px;line-height:1.75;white-space:pre-wrap;overflow-wrap:anywhere}.report-idle-time :deep(.el-form-item:last-child){margin-bottom:0}</style>
<style>.report-idle-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.report-idle-dialog .el-dialog__header,.report-idle-dialog .el-dialog__footer{flex-shrink:0}.report-idle-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.report-idle-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}.report-idle-dialog .el-checkbox__label{white-space:normal}.report-idle-dialog .el-select{width:100%}</style>
