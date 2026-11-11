<template>
  <section class="customer-invoice-records">
    <h4>客户项目开票记录</h4>
    <p v-if="!clientId">保存客户后可查看项目开票记录。</p>
    <template v-else>
      <p class="invoice-record-summary">项目 {{summary.projects||0}} 个 · 需发票 {{summary.required||0}} 个 · 已开 {{summary.issued||0}} 个 · 部分开 {{summary.partial||0}} 个 · 未开 {{summary.unissued||0}} 个 · 无需 {{summary.not_required||0}} 个</p>
      <AppForm :model="filters" inline class="invoice-record-filters" @submit.prevent="search"><el-form-item label="项目"><el-input v-model="filters.keyword" clearable placeholder="订单号、项目名称" @input="queueSearch" @keyup.enter="search" /></el-form-item><el-form-item label="是否需发票"><el-select v-model="filters.required" clearable placeholder="全部" style="width:130px" @change="search"><el-option label="需发票" value="yes" /><el-option label="无需发票" value="no" /></el-select></el-form-item><el-form-item label="开票状态"><el-select v-model="filters.status" clearable placeholder="全部" style="width:130px" @change="search"><el-option v-for="item in invoiceStatusOptions" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item><el-form-item><el-button @click="search">查询</el-button><el-button @click="reset">重置</el-button></el-form-item></AppForm>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-table v-loading="loading" :data="rows" border row-key="id" max-height="400" empty-text="暂无匹配的项目开票记录"><el-table-column prop="order_no" label="订单号" min-width="160" /><el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip /><el-table-column prop="billing_month" label="账单月份" width="110" /><el-table-column label="是否需发票" width="110"><template #default="{row}">{{needLabel(row.invoice_required)}}</template></el-table-column><el-table-column label="发票状态" width="110"><template #default="{row}">{{invoiceStatusLabels[row.invoice_status]||'未开票'}}</template></el-table-column><el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" :title="`${row.order_no} 发票详情`"><div class="invoice-record-details"><el-descriptions :column="2" border size="small"><el-descriptions-item label="订单号">{{row.order_no}}</el-descriptions-item><el-descriptions-item label="是否需发票">{{needLabel(row.invoice_required)}}</el-descriptions-item><el-descriptions-item label="发票状态">{{invoiceStatusLabels[row.invoice_status]||'未开票'}}</el-descriptions-item><el-descriptions-item label="项目计费金额">{{formatTotals(row.billing_totals)}}</el-descriptions-item><el-descriptions-item label="发票截图及备注" :span="2"><ScreenshotText v-if="row.invoice_proofs" :text="row.invoice_proofs" /><span v-else>-</span></el-descriptions-item></el-descriptions></div><template #reference><el-button link type="primary">查看详情</el-button></template></el-popover></template></el-table-column><el-table-column v-if="allowOpen" label="操作" fixed="right" width="80"><template #default="{row}"><el-button link type="primary" @click="$emit('open-invoice',row)">发票</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total,prev,pager,next" @current-change="load" />
    </template>
  </section>
</template>
<script setup>
import {reactive,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import AppForm from './AppForm.vue'
import ScreenshotText from './ScreenshotText.vue'
import {invoiceStatusOptions,invoiceStatusLabels} from '@/utils/documentRequirements'
import {getClientInvoiceRecords,connectInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({clientId:{type:[String,Number],default:''},allowOpen:{type:Boolean,default:true}})
defineEmits(['open-invoice'])
const filters=reactive({keyword:'',required:'',status:''}),rows=ref([]),summary=ref({}),total=ref(0),page=ref(1),loading=ref(false),error=ref('')
let timer,controller,sequence=0,alive=true
const needLabel=value=>value===null?'待判断':value?'需':'无需'
const formatTotals=value=>Object.entries(value||{}).map(([key,amount])=>`${key} ${Number(amount).toFixed(2)}`).join('；')||'-'
async function load(){if(!props.clientId){rows.value=[];total.value=0;return}controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value='';try{const data=await getClientInvoiceRecords(props.clientId,{keyword:filters.keyword.trim()||undefined,required:filters.required==='yes'?true:filters.required==='no'?false:undefined,invoice_status:filters.status||undefined,skip:(page.value-1)*10,limit:10},{signal:controller.signal});if(alive&&seq===sequence){rows.value=data.items||[];summary.value=data.summary||{};total.value=data.total||0;if(page.value>1&&!rows.value.length){page.value=Math.max(1,Math.ceil(total.value/10));void load()}}}catch(e){if(alive&&seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户项目发票记录加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(value){clearTimeout(timer);controller?.abort();sequence++;if(!value.trim())search();else timer=setTimeout(search,400)}
function reset(){Object.assign(filters,{keyword:'',required:'',status:''});search()}
function changed(event){if(event.type==='translation-invoice-changed'||event.detail?.kind==='records'&&String(event.detail.clientId)===String(props.clientId))void load()}
watch(()=>props.clientId,()=>{clearTimeout(timer);controller?.abort();sequence++;search()},{immediate:true})
onMounted(()=>{connectInvoiceParties();window.addEventListener(invoicePartiesEvent,changed);window.addEventListener('translation-invoice-changed',changed)})
onBeforeUnmount(()=>{alive=false;clearTimeout(timer);controller?.abort();sequence++;window.removeEventListener(invoicePartiesEvent,changed);window.removeEventListener('translation-invoice-changed',changed)})
</script>
<style scoped>.customer-invoice-records{margin-top:18px;min-width:0}.customer-invoice-records h4{margin:12px 0}.invoice-record-summary{font-size:12px;color:var(--el-text-color-secondary)}.invoice-record-filters{display:flex;gap:8px;flex-wrap:wrap}.invoice-record-filters :deep(.el-form-item){margin-right:0;margin-bottom:8px}.customer-invoice-records .el-pagination{margin-top:10px;flex-wrap:wrap}.invoice-record-details{max-height:560px;overflow:auto;overflow-wrap:anywhere;white-space:pre-wrap}</style>
