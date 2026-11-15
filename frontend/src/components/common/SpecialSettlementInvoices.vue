<template>
  <section v-loading="loading">
    <AppForm :model="filters" inline @submit.prevent="search">
      <el-form-item label="账单月份">
        <el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" @change="changeMonth" />
      </el-form-item>
      <el-form-item v-if="filters.month" label="账期">
        <StatementPeriodSelect v-model="filters.period" :month="filters.month" :client-id="clientId" settlement-scope="special" @update:model-value="search" />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="发票状态">
        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width:135px" @change="search">
          <el-option v-for="option in invoiceStatusOptions" :key="option.value" v-bind="option" />
          <el-option label="无需发票" value="not_required" />
        </el-select>
      </el-form-item>
      <el-form-item><el-button native-type="submit">查询</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" row-key="id" border max-height="460" empty-text="暂无特殊结算项目">
      <el-table-column prop="orderNo" label="订单号" min-width="180" />
      <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="clientShortName" label="客户" min-width="120" />
      <el-table-column label="含税总价" min-width="120">
        <template #default="{row}">{{amounts(row.totalsInclTax)}}</template>
      </el-table-column>
      <el-table-column label="特殊结算发票" min-width="300">
        <template #default="{row}">
          <span>{{requirement(row.specialInvoiceRequired)}}</span>
          <el-select v-if="row.specialInvoiceRequired" :model-value="row.specialInvoiceStatus"
            :aria-label="`${row.orderNo} 特殊结算发票状态`" :disabled="!canWrite||saving"
            size="small" style="width:115px;margin:0 8px" @change="save(row,{invoice_status:$event})">
            <el-option v-for="option in invoiceStatusOptions" :key="option.value" v-bind="option" />
          </el-select>
          <el-checkbox v-if="row.specialInvoiceStatus==='issued'" :model-value="row.specialInvoiceSent"
            :disabled="!canWrite||saving" @change="save(row,{invoice_sent:$event})">已发客户</el-checkbox>
        </template>
      </el-table-column>
      <el-table-column label="原订单发票" min-width="185">
        <template #default="{row}">
          <span>{{requirement(row.originalInvoiceRequired)}} · {{invoiceStatusLabels[row.invoiceStatus]||'未开票'}}</span>
          <el-button link type="primary" @click="original=row">查看原发票</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total,prev,pager,next" @current-change="load" />
    <ProjectInvoiceDialog v-if="original" :model-value="true" :context="{projectId:original.rootId,orderId:original.id,order:original}"
      readonly @update:model-value="original=null" />
  </section>
</template>

<script setup>
import {onBeforeUnmount, onMounted, reactive, ref, watch} from 'vue'
import {getCustomerFinancePage, saveSpecialSettlement} from '@/api/translationCustomerFinance'
import {invoiceStatusOptions, invoiceStatusLabels} from '@/utils/documentRequirements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {connectInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import AppForm from './AppForm.vue'
import ProjectInvoiceDialog from './ProjectInvoiceDialog.vue'
import StatementPeriodSelect from './StatementPeriodSelect.vue'

const props=defineProps({clientId:[String,Number],projectId:String,month:String,periodNumber:Number,managerQuery:Object})
const filters=reactive({month:props.month||'',period:props.periodNumber,keyword:'',status:''})
const rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),saving=ref(false),error=ref(''),original=ref(null)
const canWrite=hasPermission('projects:write')
const requirement=value=>value==null?'待判断':value?'需发票':'无需发票'
const amounts=totals=>Object.entries(totals||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('、')||'—'
const events=['translation-invoice-changed','translation-statements-changed']
let controller,timer

async function load(){
  clearTimeout(timer)
  controller?.abort()
  const request=controller=new AbortController()
  loading.value=true
  error.value=''
  try{
    const data=await getCustomerFinancePage({...props.managerQuery,settlement_scope:'special',special_invoice_tracking:true,
      invoice_status:filters.status||undefined,billing_month:filters.month||undefined,period_number:filters.period,
      keyword:filters.keyword.trim()||undefined,client_ids:props.clientId?[props.clientId]:undefined,
      special_invoice_project_id:props.projectId||undefined,skip:(page.value-1)*20,limit:20},{signal:request.signal})
    if(!request.signal.aborted){
      rows.value=data.items||[]
      total.value=data.total||0
    }
  }catch(e){
    if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'特殊结算发票加载失败')
  }finally{
    if(!request.signal.aborted)loading.value=false
  }
}
function search(){page.value=1;void load()}
function changeMonth(){filters.period=undefined;search()}
function queueSearch(){clearTimeout(timer);controller?.abort();if(filters.keyword.trim())timer=setTimeout(search,400);else search()}
async function save(row,fields){
  if(saving.value)return
  saving.value=true
  error.value=''
  try{
    await saveSpecialSettlement(row.rootId,{order_id:row.id,...fields})
  }catch(e){
    error.value=getLocalizedErrorMessage(e,'保存特殊结算发票失败')
  }finally{saving.value=false}
}
watch(()=>props.month,value=>{filters.month=value||'';changeMonth()})
watch(()=>[props.clientId,props.projectId,JSON.stringify(props.managerQuery)],search)
function onInvoiceChange(event){if(['special-settlement','records'].includes(event.detail?.kind))void load()}
onMounted(()=>{
  connectInvoiceParties()
  window.addEventListener(invoicePartiesEvent,onInvoiceChange)
  events.forEach(event=>window.addEventListener(event,load))
  void load()
})
onBeforeUnmount(()=>{
  window.removeEventListener(invoicePartiesEvent,onInvoiceChange)
  events.forEach(event=>window.removeEventListener(event,load))
  controller?.abort()
  clearTimeout(timer)
})
</script>
