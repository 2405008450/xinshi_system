<template>
  <div class="statement-tax-preference" data-dialog-field-search-label="单价含税">
    <el-checkbox :model-value="included" :disabled="!clientId||!canWrite||loading||saving" @change="save">单价含税</el-checkbox>
    <span>对账单采用客户选择的税口径；未勾选时标注“不含税”。</span>
    <div class="statement-default-setting" data-dialog-field-search-label="对账单默认设置"><span>对账单默认设置</span><el-select :model-value="statementDefault" aria-label="对账单默认设置" :disabled="!clientId||!canWrite||loading||saving" style="width:200px" @change="saveDefault"><el-option label="默认需对账单" value="required" /><el-option label="默认无需对账单" value="not_required" /><el-option label="未知" value="unknown" /></el-select><small>只同步尚未人工设置的项目，已手动调整的选择保留。</small></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
  </div>
</template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {getStatementPreference,saveStatementPreference} from '@/api/customerStatements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const included=ref(false),statementDefault=ref('unknown'),revision=ref(0),loading=ref(false),saving=ref(false),error=ref('')
let sequence=0,controller
async function load(){controller?.abort();const seq=++sequence;included.value=false;statementDefault.value='unknown';revision.value=0;error.value='';if(!props.clientId)return;controller=new AbortController();loading.value=true;try{const data=await getStatementPreference(props.clientId,{signal:controller.signal});if(seq===sequence){included.value=data.tax_included;statementDefault.value=data.statement_default||'unknown';revision.value=data.revision}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务设置加载失败')}finally{if(seq===sequence)loading.value=false}}
function save(value){return persist({tax_included:value})}
function saveDefault(value){return persist({tax_included:included.value,statement_default:value})}
async function persist(patch){if(saving.value||loading.value||!props.canWrite)return;const id=props.clientId,seq=sequence;saving.value=true;error.value='';try{const data=await saveStatementPreference(id,{revision:revision.value,...patch});if(seq===sequence){included.value=data.tax_included;statementDefault.value=data.statement_default||'unknown';revision.value=data.revision;window.dispatchEvent(new CustomEvent('customer-statement-preference-saved',{detail:{clientId:id}}))}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'客户财务设置保存失败，请重新加载')}finally{if(seq===sequence)saving.value=false}}
watch(()=>props.clientId,load,{immediate:true})
function refreshAfterProjectSync(event){
  if(event.detail?.fromProject&&event.detail.clientId===props.clientId&&!saving.value)void load()
}
onMounted(()=>window.addEventListener('customer-statement-preference-saved',refreshAfterProjectSync))
onBeforeUnmount(()=>{sequence++;controller?.abort();window.removeEventListener('customer-statement-preference-saved',refreshAfterProjectSync)})
</script>
<style scoped>
.statement-default-setting{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:12px}.statement-default-setting small{color:var(--el-text-color-secondary)}.statement-tax-preference{margin-bottom:12px}.statement-tax-preference>span{font-size:12px;color:var(--el-text-color-secondary);margin-left:12px}.el-alert{margin-top:8px}
</style>
