<template>
  <div class="statement-tax-preference" data-dialog-field-search-label="单价含税">
    <el-checkbox :model-value="included" :disabled="!clientId||!canWrite||loading||saving" @change="save">单价含税</el-checkbox>
    <span>对账单采用客户选择的税口径；未勾选时标注“不含税”。</span>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
  </div>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {getStatementPreference,saveStatementPreference} from '@/api/customerStatements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:{type:[String,Number],default:''},canWrite:Boolean})
const included=ref(false),revision=ref(0),loading=ref(false),saving=ref(false),error=ref('')
let sequence=0,controller
async function load(){controller?.abort();const seq=++sequence;included.value=false;revision.value=0;error.value='';if(!props.clientId)return;controller=new AbortController();loading.value=true;try{const data=await getStatementPreference(props.clientId,{signal:controller.signal});if(seq===sequence){included.value=data.tax_included;revision.value=data.revision}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'含税设置加载失败')}finally{if(seq===sequence)loading.value=false}}
async function save(value){if(saving.value||loading.value||!props.canWrite)return;const id=props.clientId,seq=sequence;saving.value=true;error.value='';try{const data=await saveStatementPreference(id,{revision:revision.value,tax_included:value});if(seq===sequence){included.value=data.tax_included;revision.value=data.revision;window.dispatchEvent(new CustomEvent('customer-statement-preference-saved',{detail:{clientId:id}}))}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'含税设置保存失败，请重新加载')}finally{if(seq===sequence)saving.value=false}}
watch(()=>props.clientId,load,{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.statement-tax-preference{margin-bottom:12px}.statement-tax-preference>span{font-size:12px;color:var(--el-text-color-secondary);margin-left:12px}.el-alert{margin-top:8px}
</style>
