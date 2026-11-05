<template>
  <section class="payment-confirmation" data-dialog-field-search-group data-dialog-field-search-group-title="付款情况">
    <div class="payment-confirmation-heading"><strong>付款情况</strong><div><slot name="actions" /><el-button v-if="projectId" link @click="openHistory">付款修改记录</el-button></div></div>
    <el-form-item label="付款状态" :prop="`${prefix}.paymentOption`" :rules="value.isPaid?[{required:true,message:'请选择付款状态',trigger:'change'}]:[]"><el-radio-group :model-value="value.isPaid?value.paymentOption:null" @update:model-value="selectStatus"><el-radio v-for="item in paymentOptions" :key="item.value" :value="item.value">{{item.label}}</el-radio></el-radio-group><el-button v-if="value.isPaid" link @click="clearStatus">清除选择</el-button><small v-if="value.paymentOption==='once'">历史：已登记分次付款</small></el-form-item>
    <FullPaymentMatchFields v-if="value.isPaid&&(value.paymentOption==='full'||value.fullPaymentSource==='details')" :from-details="value.paymentOption!=='full'" :model-value="value" :project-id="projectId" :prefix="prefix" @update:model-value="emit('update:modelValue',$event)" />
    <el-form-item v-if="value.isPaid" label="付款账户" :prop="`${prefix}.paymentAccount`"><PaymentAccountSelect :model-value="value.paymentAccount" @update:model-value="update('paymentAccount',$event)" /></el-form-item>
    <el-form-item label="支付截图及备注"><ScreenshotInput :model-value="value.proofs" type="textarea" :rows="2" :maxlength="20000" placeholder="可粘贴、拖入或上传支付截图，填写付款备注" @update:model-value="update('proofs',$event)" /></el-form-item>
    <p class="payment-confirmation-help">支付截图随付款情况长期保存；清除选择不会删除已有截图。与财务管理的付款情况共用同一份记录。</p>
    <DraggableFormDialog v-model="historyVisible" title="付款修改记录" width="min(860px, calc(100vw - 32px))" top="5vh" append-to-body class="payment-confirmation-history">
      <div v-loading="historyLoading"><el-alert v-if="historyError" :title="historyError" type="error" :closable="false" /><el-empty v-else-if="!historyItems.length" description="暂无修改记录" /><div v-for="item in historyItems" :key="item.id" class="confirmation-history-item"><p>{{formatDateTime(item.created_at)}} · {{item.actor_name}}</p><el-descriptions :column="1" border><el-descriptions-item label="修改前">{{paymentConfirmationLabel(item.before)}}<ScreenshotText :text="item.before.proofs" /></el-descriptions-item><el-descriptions-item label="修改后">{{paymentConfirmationLabel(item.after)}}<ScreenshotText :text="item.after.proofs" /></el-descriptions-item></el-descriptions></div><el-pagination v-model:current-page="historyPage" :page-size="10" :total="historyTotal" layout="prev, pager, next" @current-change="loadHistory" /></div>
      <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,ref} from 'vue'
import api from '@/api'
import {formatBusinessDateTime as formatDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {paymentOptions,paymentConfirmationForm,paymentConfirmationLabel} from '@/utils/paymentConfirmation'
import ScreenshotInput from './ScreenshotInput.vue'
import PaymentAccountSelect from './PaymentAccountSelect.vue'
import FullPaymentMatchFields from './FullPaymentMatchFields.vue'
import ScreenshotText from './ScreenshotText.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
const props=defineProps({modelValue:Object,projectId:{type:String,default:''},prefix:{type:String,default:'confirmation'}})
const emit=defineEmits(['update:modelValue'])
const value=computed(()=>paymentConfirmationForm(props.modelValue))
function update(key,data){emit('update:modelValue',{...value.value,[key]:data})}
function selectStatus(option){emit('update:modelValue',{...value.value,isPaid:true,paymentOption:option,fullMatchStatus:option==='full'?'pending':'none'})}
function clearStatus(){emit('update:modelValue',{...value.value,isPaid:false,paymentOption:null})}
const historyVisible=ref(false),historyLoading=ref(false),historyError=ref(''),historyItems=ref([]),historyPage=ref(1),historyTotal=ref(0)
async function loadHistory(){historyLoading.value=true;historyError.value='';try{const data=await api.get(`/translation-payments/${props.projectId}/confirmation-history`,{params:{page:historyPage.value}});historyItems.value=data.items;historyTotal.value=data.total}catch(e){historyError.value=getLocalizedErrorMessage(e,'付款修改记录加载失败')}finally{historyLoading.value=false}}
function openHistory(){historyPage.value=1;historyItems.value=[];historyVisible.value=true;void loadHistory()}
</script>
<style scoped>.payment-confirmation{margin:16px 0;padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.payment-confirmation-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}.payment-confirmation-heading>div{display:flex;gap:12px;flex-wrap:wrap}.payment-confirmation-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6;margin:0}.confirmation-history-item{margin-bottom:14px}:global(.payment-confirmation-history){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.payment-confirmation-history>.el-dialog__body){min-height:0;overflow:auto;flex:1}:global(.payment-confirmation-history>.el-dialog__header),:global(.payment-confirmation-history>.el-dialog__footer){flex:none}</style>
