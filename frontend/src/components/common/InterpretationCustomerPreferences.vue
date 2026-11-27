<template>
  <section v-loading="loading" class="oral-customer-preferences">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm v-if="settings" :model="settings" label-position="top" data-auto-draft="off" :disabled="!canWrite||saving">
      <div class="preference-fields">
        <el-form-item label="默认结算模式"><el-select :model-value="settings.payment_method||'default'" @change="save('payment_method',$event)"><el-option label="按项目设置" value="default" /><el-option v-for="(label,key) in modes" :key="key" :value="key" :label="label" /></el-select></el-form-item>
        <el-form-item label="对账单主体"><el-select :model-value="settings.statement_subject_key||'default'" @change="save('statement_subject_key',$event)"><el-option label="系统默认" value="default" /><el-option label="广州总公司" value="guangzhou" /><el-option label="深圳分公司" value="shenzhen" /><el-option label="上海分公司" value="shanghai" /></el-select></el-form-item>
        <el-form-item v-for="field in fields" :key="field.key" :label="field.label"><el-select :model-value="settings[field.key]??'default'" @change="save(field.key,$event)"><el-option label="按订单设置" value="default" /><el-option label="需" :value="true" /><el-option label="无需" :value="false" /></el-select><el-input :model-value="settings.document_notes?.[field.kind]||''" size="small" placeholder="说明" :aria-label="field.label+'说明'" maxlength="2000" clearable @change="save('document_notes',{...settings.document_notes,[field.kind]:$event})" /></el-form-item>
        <el-form-item label="默认计费口径"><el-select :model-value="settings.tax_mode||'default'" @change="save('tax_mode',$event)"><el-option label="按订单设置" value="default" /><el-option label="不含税" value="excl_tax" /><el-option label="含税" value="incl_tax" /></el-select></el-form-item>
        <el-form-item label="客户付款账期"><el-input :model-value="settings.collection_terms||''" maxlength="300" placeholder="如月结30天，可自由填写" @change="save('collection_terms',$event)" /></el-form-item>
      </div>
    </AppForm>
    <small>修改后自动同步该客户的口译项目；特殊结算保留独立设置。单价仍需单独确认同步。</small>
  </section>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import AppForm from './AppForm.vue'
import {readOralPreferences,saveOralPreferences} from '@/api/interpretationSettlementSettings'
import {translationSettlementModeLabels as modes} from '@/utils/settlementModes'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:String,canWrite:Boolean})
const settings=ref(null),loading=ref(false),saving=ref(false),error=ref('')
const fields=[{key:'quotation_required',kind:'quotation',label:'是否需报价单'},{key:'statement_required',kind:'statement',label:'是否需对账单'},{key:'invoice_required',kind:'invoice',label:'是否需发票'}]
let controller
async function load(){controller?.abort();if(!props.clientId)return;const request=controller=new AbortController();loading.value=true;error.value='';try{const value=await readOralPreferences('client',props.clientId,{signal:request.signal});if(!request.signal.aborted)settings.value=value}catch(e){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'客户结算设置加载失败')}finally{if(!request.signal.aborted)loading.value=false}}
async function save(key,value){if(saving.value||!props.canWrite)return;saving.value=true;error.value='';try{settings.value=await saveOralPreferences('client',props.clientId,{revision:settings.value.revision,[key]:value==='default'?null:value});window.dispatchEvent(new CustomEvent('interpretation-settlement-settings-changed',{detail:{clientId:props.clientId}}))}catch(e){error.value=getLocalizedErrorMessage(e,'客户结算设置保存失败');if(e.response?.status===409)await load()}finally{saving.value=false}}
watch(()=>props.clientId,load,{immediate:true});onBeforeUnmount(()=>controller?.abort())
</script>
<style scoped>.preference-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px 16px}.preference-fields .el-input{margin-top:6px}small{display:block;font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}</style>
