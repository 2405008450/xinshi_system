<template>
  <div class="rate-differences">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="total" type="warning" :closable="false" :title="`已登记项目中有 ${total} 个订单的单价与客户信息不一致`"><el-button type="warning" link @click="visible=true;load()">查看差异并选择同步</el-button></el-alert>
    <p v-else-if="!loading&&!error">{{ready?'已登记项目单价与客户信息一致':'客户单价存储尚未初始化'}}</p>
    <DraggableFormDialog v-model="visible" append-to-body class="customer-rate-differences-dialog" width="min(1200px, calc(100vw - 32px))" top="5vh" title="客户与项目单价差异" :close-on-click-modal="false" :before-close="close">
      <p>客户参考价自动带入项目。项目中单独调整的价格予以保留；同步前请核对方向、货币和单位。数量、加班费、调整后总价及说明保持原值。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-table v-loading="loading||busy" :data="items" border row-key="order_id"><el-table-column prop="order_no" label="订单号" min-width="180" /><el-table-column prop="project_name" label="项目名称" min-width="160" /><el-table-column label="客户信息单价" min-width="260"><template #default="{row}"><span class="rate-text">{{describe(row.customer_rates)}}</span></template></el-table-column><el-table-column label="已登记项目单价" min-width="260"><template #default="{row}"><span class="rate-text">{{describe(row.project_rates)}}</span></template></el-table-column><el-table-column label="同步选择" fixed="right" width="190"><template #default="{row}"><el-button v-if="canWriteProjects" link type="primary" :disabled="busy||!row.customer_rates.length" @click="synchronize(row,'client_to_project')">客户单价 → 此订单</el-button><el-button v-if="canWriteClients" link type="warning" :disabled="busy" @click="synchronize(row,'project_to_client')">此订单单价 → 客户</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" @current-change="load" />
      <template #footer><el-button :disabled="busy" @click="load">刷新差异</el-button><el-button :disabled="busy" @click="visible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {getCustomerRateDifferences,synchronizeCustomerRates} from '@/api/customerFinanceSync'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {financeSummary} from '@/utils/interpretationCustomerFinance'
const props=defineProps({module:{type:String,required:true},clientId:{type:[String,Number],default:''},revision:{type:Number,default:0}})
const emit=defineEmits(['saved'])
const canWriteProjects=hasPermission('projects:write'),canWriteClients=hasPermission('clients:write')
const visible=ref(false),items=ref([]),page=ref(1),total=ref(0),loading=ref(false),busy=ref(false),error=ref(''),ready=ref(true)
let sequence=0,controller
function describe(rows){if(props.module==='interpretation')return financeSummary({rates:rows.map(row=>({...row,quantity:1}))});const labels={foreign_words:'外文字数',characters_no_spaces:'字符数不计空格',words:'原登记字数',documents:'份数',pages:'页数',cjk_chars_korean_words:'中朝统计'};return rows.map(row=>`${row.language_pair}：${row.currency} ${row.amount} / ${row.unit_size} ${labels[row.metric]||row.metric}`).join('\n')||'未登记匹配方向的单价'}
async function load(){if(!props.clientId)return;const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getCustomerRateDifferences(props.module,props.clientId,page.value,controller.signal);if(seq!==sequence)return;items.value=data.items;total.value=data.total;ready.value=data.ready;if(page.value>1&&!items.value.length){page.value=Math.max(1,Math.ceil(total.value/10));void load()}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'单价差异加载失败')}finally{if(seq===sequence)loading.value=false}}
async function synchronize(row,direction){if(busy.value)return;const message=direction==='project_to_client'?`确认将订单 ${row.order_no} 的以下单价同步至客户信息？客户价格变更会自动下发至仍沿用原价的项目。`:`确认以客户信息中的以下单价更新订单 ${row.order_no}？`;
  try{await ElMessageBox.confirm(`${message}\n\n${describe(direction==='project_to_client'?row.project_rates:row.customer_rates)}`,'确认同步单价',{type:'warning',confirmButtonText:'确认同步',cancelButtonText:'取消'})}catch{return}
  busy.value=true;try{await synchronizeCustomerRates(props.module,props.clientId,{project_id:row.project_id,order_id:row.order_id,version:row.version,customer_version:row.customer_version,direction,confirmed:true});ElMessage.success('单价已同步并保留调整记录');await load();emit('saved')}catch(e){error.value=getLocalizedErrorMessage(e,'同步失败，请刷新差异后重新确认')}finally{busy.value=false}}
function close(done){if(busy.value)return;if(typeof done==='function')done();else visible.value=false}
watch(()=>[props.clientId,props.module,props.revision],()=>{page.value=1;void load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.rate-differences{margin:12px 0}.rate-text{white-space:pre-wrap;overflow-wrap:anywhere}p{font-size:12px;color:#64748b}.el-pagination{margin-top:12px}:global(.customer-rate-differences-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-rate-differences-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.customer-rate-differences-dialog .el-dialog__header),:global(.customer-rate-differences-dialog .el-dialog__footer){flex-shrink:0}:global(.customer-rate-differences-dialog .el-dialog__footer){border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
