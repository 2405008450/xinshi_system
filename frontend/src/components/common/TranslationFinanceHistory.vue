<template>
  <section v-loading="loading" class="translation-finance-history">
    <p>记录单价、调整后总价及下级继承导致的金额变化，保留修改人、时间和前后内容。从本功能启用后开始记录。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-collapse><el-collapse-item v-for="event in items" :key="event.id" :title="`${event.orderNo} · ${event.actorName} · ${formatTime(event.createdAt)}`"><div v-if="event.after?.syncOperation" class="finance-sync-history"><p>同月单价同步 · 第 {{event.after.syncOperation.count}} 次 · {{event.after.syncOperation.billingMonth}}</p><p>同步订单：{{event.after.syncOperation.targets.join('、')}}</p><p v-for="(price,index) in event.after.syncOperation.prices" :key="index">{{price.languagePair}} · {{price.currency}} {{price.amount}} / {{price.unitSize}} · {{metricLabel(price.metric)}}</p><p>本次仅同步目标订单，来源订单未保存内容仍保留在编辑窗口。</p></div><div v-else class="finance-history-comparison"><div v-for="[label,data] in [['修改前',event.before],['修改后',event.after]]" :key="label"><strong>{{label}}</strong><p>{{data.projectName||event.projectName}}</p><p v-for="(price,index) in data.prices||[]" :key="price.id||index">{{price.languagePair}}：{{price.currency}} {{price.amount}} / {{price.unitSize}} · {{metricLabel(price.metric)}}</p><p v-if="!data.prices?.length">暂无单价</p><p>调整后总价：{{data.adjustedTotal==null?'未手动调整':Number(data.adjustedTotal).toFixed(2)}}</p><p>总价汇总：{{amounts(data.totals)}}</p><p>调整后汇总：{{amounts(data.adjustedTotals)}}</p><p>说明：{{data.explanation||'-'}}</p></div></div></el-collapse-item></el-collapse>
    <el-empty v-if="!items.length&&!loading&&!error" description="暂无修改记录" :image-size="45" />
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" @current-change="load" />
  </section>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {getTranslationFinanceHistory} from '@/api/translationCustomerFinance'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
import {basisLabel} from '@/utils/translationQuantityBasis'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({projectId:{type:String,required:true},orderId:{type:String,default:''}})
const items=ref([]),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
let sequence=0,controller
const metricLabel=basisLabel
const amounts=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${Number(value).toFixed(2)}`).join('；')||'-'
async function load(){const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getTranslationFinanceHistory(props.projectId,{order_id:props.orderId||undefined,page:page.value},{signal:controller.signal});if(current===sequence){items.value=data.items||[];total.value=data.total||0;if(data.ready===false)error.value='修改记录存储尚未初始化'}}catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'修改记录加载失败')}finally{if(current===sequence)loading.value=false}}
watch(()=>[props.projectId,props.orderId],()=>{page.value=1;load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.translation-finance-history>p{font-size:12px;color:#64748b}.finance-history-comparison{display:grid;grid-template-columns:1fr 1fr;gap:16px;white-space:pre-wrap;overflow-wrap:anywhere}.finance-history-comparison>div{padding:12px;background:#f8fafc;border:1px solid #dbe3ec;border-radius:6px}.el-pagination{margin-top:12px}@media(max-width:700px){.finance-history-comparison{grid-template-columns:1fr}}
</style>
