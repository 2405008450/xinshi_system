<template>
  <section>
    <AppForm :model="filters" inline @submit.prevent="searchCustomers('')">
      <el-form-item label="需查看对账单的客户">
        <el-select v-model="filters.clientIds" multiple filterable remote :remote-method="queueSearch" :loading="loading" :reserve-keyword="false" clearable placeholder="搜索并选择客户，支持多选" style="width:min(680px, calc(100vw - 120px))" @change="updateExpanded">
          <el-option v-for="client in options" :key="client.id" :value="client.id" :label="`${client.shortName||client.name} ${client.code||''}`" />
        </el-select>
      </el-form-item>
      <el-form-item><el-checkbox v-model="filters.requiredOnly" @change="searchCustomers('')">仅列出需对账单的客户</el-checkbox></el-form-item>
      <el-form-item><el-button @click="searchCustomers('')">刷新客户</el-button><el-button v-if="filters.clientIds.length" @click="expanded=[...filters.clientIds]">全部展开</el-button><el-button v-if="filters.clientIds.length" @click="expanded=[]">全部收起</el-button></el-form-item>
    </AppForm>
    <p class="statement-client-hint">每个客户独立制作和核对，对账单及任务不会跨客户混放。客户较多时可输入名称或编号搜索。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-empty v-if="!filters.clientIds.length" description="请选择需查看对账单的客户" />
    <el-collapse v-else v-model="expanded" class="statement-client-groups">
      <el-collapse-item v-for="client in selectedClients" :key="client.id" :name="client.id">
        <template #title><strong>{{client.shortName||client.name}}</strong><span class="statement-client-code">{{client.code}}</span></template>
        <CustomerStatementWorkspace v-if="expanded.includes(client.id)" :client-id="client.id" :billing-month="initialClient?.id===client.id?initialClient.month:billingMonth" />
      </el-collapse-item>
    </el-collapse>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import AppForm from './AppForm.vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
import {getStatementCustomers} from '@/api/translationCustomerFinance'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({initialClient:Object,billingMonth:String})
const filters=reactive({clientIds:[],requiredOnly:true}),options=ref([]),expanded=ref([]),loading=ref(false),error=ref('')
const selectedClients=computed(()=>filters.clientIds.map(id=>options.value.find(client=>client.id===id)).filter(Boolean))
let controller,sequence=0,timer
async function searchCustomers(keyword=''){
  clearTimeout(timer);controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value=''
  try{
    const data=await getStatementCustomers({keyword:keyword.trim()||undefined,required_only:filters.requiredOnly,limit:100},{signal:controller.signal})
    if(seq!==sequence)return
    const keep=selectedClients.value
    options.value=[...(data.items||[]),...keep.filter(client=>!(data.items||[]).some(item=>item.id===client.id))]
  }catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户加载失败')}
  finally{if(seq===sequence)loading.value=false}
}
function queueSearch(keyword){clearTimeout(timer);controller?.abort();sequence++;if(!keyword.trim())void searchCustomers('');else timer=setTimeout(()=>searchCustomers(keyword),400)}
function updateExpanded(){expanded.value=[...filters.clientIds]}
watch(()=>props.initialClient,client=>{if(!client?.id)return;if(!options.value.some(item=>item.id===client.id))options.value.unshift(client);filters.clientIds=[client.id];expanded.value=[client.id]},{immediate:true})
void searchCustomers('')
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
</script>
<style scoped>
.statement-client-hint{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 12px}.statement-client-code{margin-left:12px;color:var(--el-text-color-secondary)}.statement-client-groups :deep(.el-collapse-item__header){font-size:16px;padding:0 12px;background:var(--el-fill-color-light)}.statement-client-groups :deep(.el-collapse-item__content){padding:12px;min-width:0}
</style>
