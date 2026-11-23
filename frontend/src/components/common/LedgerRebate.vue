<template>
  <el-button link type="primary" :disabled="!row.clientId" @click="open">{{row.ledgerRebate?.revision?'返点 '+row.ledgerRebate.rate+'%':'返点'}}</el-button>
  <DraggableFormDialog v-model="visible" append-to-body class="ledger-rebate-dialog" width="min(760px, calc(100vw - 32px))" top="5vh" title="返点">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="返点" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body">
      <p>{{row.ledgerLabel}}</p>
      <el-alert v-if="row.ledgerPending" title="项目金额尚未填写完整，返点金额待核实" type="warning" :closable="false" />
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="返点人" prop="recipient"><el-input v-model="form.recipient" maxlength="200" :disabled="!canWrite" /></el-form-item>
        <el-form-item label="返点比例（%）" prop="rate"><el-input-number v-model="form.rate" :min="0" :max="100" :precision="6" :disabled="!canWrite" /></el-form-item>
        <el-form-item label="项目计费金额"><ReadonlyField :model-value="money(row.ledgerAmounts)" source="auto" /></el-form-item>
        <el-form-item label="返点金额（项目金额 × 返点比例）"><ReadonlyField :model-value="money(amounts)" source="auto" /></el-form-item>
        <el-form-item label="客户付款状态"><ReadonlyField :model-value="row.ledgerPaymentLabel||'未付款'" source="auto" /></el-form-item>
        <el-form-item label="返点付款状态" prop="paymentStatus"><el-select v-model="form.paymentStatus" :disabled="!canWrite"><el-option label="未支付" value="unpaid" /><el-option label="已部分支付" value="partial" /><el-option label="全部支付" value="full" /></el-select></el-form-item>
        <el-form-item v-if="form.paymentStatus==='partial'" label="已支付返点金额" prop="paidAmounts"><div v-for="(_,currency) in row.ledgerAmounts" :key="currency">{{currency}} <el-input-number v-model="form.paidAmounts[currency]" :min="0" :precision="2" :disabled="!canWrite" /></div></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.note" type="textarea" :rows="3" maxlength="5000" :disabled="!canWrite" /></el-form-item>
      </AppForm>
      <el-descriptions :column="2" border size="small"><el-descriptions-item label="操作人">{{row.ledgerRebate?.actorName||'保存后自动记录'}}</el-descriptions-item><el-descriptions-item label="操作时间">{{row.ledgerRebate?.updatedAt?formatBusinessDateTime(row.ledgerRebate.updatedAt):'保存后自动记录'}}</el-descriptions-item></el-descriptions>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" @click="save">保存并记录</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,reactive,ref} from 'vue'
import api from '@/api'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
const props=defineProps({row:{type:Object,required:true},canWrite:Boolean})
const emit=defineEmits(['saved'])
const visible=ref(false),saving=ref(false),error=ref(''),body=ref(),formRef=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const form=reactive({recipient:'',rate:0,paymentStatus:'unpaid',paidAmounts:{},note:'',revision:0})
const amounts=computed(()=>Object.fromEntries(Object.entries(props.row.ledgerAmounts||{}).map(([currency,value])=>[currency,(Math.round((Number(value)*Number(form.rate||0)/100+Number.EPSILON)*100)/100).toFixed(2)])))
const money=value=>Object.entries(value||{}).map(([currency,amount])=>`${currency} ${amount}`).join(' / ')||'待补'
const rules={recipient:[{required:true,whitespace:true,message:'请填写返点人',trigger:'blur'}],rate:[{required:true,message:'请填写返点比例',trigger:'change'}],paidAmounts:[{validator:(_,value,done)=>{if(form.paymentStatus!=='partial')return done();const entries=Object.entries(amounts.value);const values=entries.map(([currency])=>Number(value[currency]||0));done(values.some(v=>v>0)&&entries.every(([currency,total])=>Number(value[currency]||0)<=Number(total))&&entries.some(([currency,total])=>Number(value[currency]||0)<Number(total))?undefined:new Error('请填写大于零、未付清且不超过返点金额的已付金额'))},trigger:'change'}]}
function open(){const saved=props.row.ledgerRebate||{};Object.assign(form,{recipient:saved.recipient||'',rate:Number(saved.rate||0),paymentStatus:saved.paymentStatus||'unpaid',paidAmounts:{...(saved.paidAmounts||{})},note:saved.note||'',revision:saved.revision||0});error.value='';visible.value=true}
async function save(){if(!await formRef.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{const result=await api.put(`/translation-statement-workspaces/${props.row.clientId}/ledger-rebate`,{unit_id:props.row.id,revision:form.revision,recipient:form.recipient,rate:form.rate,payment_status:form.paymentStatus,paid_amounts:form.paidAmounts,note:form.note});emit('saved',{...result,paymentStatus:result.payment_status,paidAmounts:result.paid_amounts,actorName:result.actor_name,updatedAt:result.updated_at});visible.value=false}catch(e){error.value=getLocalizedErrorMessage(e,'返点保存失败')}finally{saving.value=false}}
</script>
<style>
.ledger-rebate-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.ledger-rebate-dialog .el-dialog__header,.ledger-rebate-dialog .el-dialog__footer{flex-shrink:0}
.ledger-rebate-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.ledger-rebate-dialog .el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
