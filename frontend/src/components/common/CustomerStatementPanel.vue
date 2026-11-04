<template>
  <section class="customer-statement-panel">
    <p class="statement-hint">对账单采用已保存的收费设置。修改价格或账单月份后，请先保存；未登记账单月份的订单沿用上级月份，最后按订单编号月份归属。</p>
    <el-alert v-if="!projectId" title="请先保存项目，再生成对账单" type="info" :closable="false" />
    <AppForm :model="filters" inline @submit.prevent="generate">
      <el-form-item label="账单月份" prop="month" :rules="[{required:true,message:'请选择账单月份',trigger:'change'}]"><el-date-picker v-model="filters.month" type="month" value-format="YYYY-MM" :clearable="false" @change="invalidate" /></el-form-item>
      <el-form-item label="生成范围"><el-radio-group v-model="filters.scope" @change="invalidate"><el-radio value="project">当前项目</el-radio><el-radio value="customer">该客户整月项目</el-radio></el-radio-group></el-form-item>
      <el-form-item><el-button type="primary" :disabled="!projectId||!filters.month" :loading="loading" @click="generate">生成对账单</el-button><CustomerStatementSettings @saved="invalidate" /></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="statement">
      <div class="statement-actions"><el-button :disabled="!statement.rows.length||loading" @click="print">打印 / 另存PDF</el-button><el-button :disabled="!statement.rows.length||loading" :loading="exporting" @click="download">下载Excel</el-button><span>单价口径：{{statement.tax_included?'含税':'不含税'}}</span></div>
      <el-alert v-if="statement.pending.length" :title="`有${statement.pending.length}项待补资料，当前合计仅含已登记金额`" type="warning" :closable="false"><div v-for="item in statement.pending" :key="item">{{item}}</div></el-alert>
      <div class="statement-scroll"><article ref="paper" class="statement-paper">
        <h2>{{statement.company}}</h2><h3>对账单</h3>
        <div class="statement-meta"><span>客户：{{statement.client_name}}</span><span>账单月份：{{statement.month}}　金额口径：{{statement.tax_included?'含税':'不含税'}}</span></div>
        <div class="statement-table-wrap">
          <table class="statement-table"><thead><tr><th>来稿日期</th><th>项目名称</th><th>翻译方向</th><th>工作量（计价方式）</th><th>单价</th><th>小计</th><th>备注</th></tr></thead>
            <tbody><tr v-for="(row,index) in statement.rows" :key="index"><td>{{row.received_date||'-'}}</td><td>{{row.project_name}}</td><td>{{row.language_pair}}</td><td><strong v-if="row.quantity!=null">{{row.quantity}}<br /></strong>{{row.basis}}</td><td>{{row.unit_price!=null?`${row.currency} ${number(row.unit_price)}（${row.unit_label}）`:'-'}}</td><td>{{row.subtotal!=null?`${row.currency} ${row.subtotal}`:'待补'}}</td><td>{{row.remarks||''}}</td></tr><tr v-if="!statement.rows.length"><td colspan="7">所选月份暂无对应项目</td></tr></tbody>
            <tfoot><tr><td colspan="5" class="statement-total-label">{{statement.pending.length?'合计（已登记金额）':'合计'}}</td><td colspan="2"><div v-for="(amount,currency) in statement.totals" :key="currency">{{currency}} {{amount}}</div><span v-if="!Object.keys(statement.totals).length">-</span></td></tr></tfoot>
          </table>
          <img v-if="statement.rows.length" class="statement-stamp" :src="statement.stamp_image" alt="对账单印章" />
        </div>
        <section class="statement-account"><h4>信实翻译公司 账户信息</h4><p>开户行：{{statement.settings.bank_name||''}}</p><p>账户名：{{statement.settings.account_name||''}}</p><p>账号：{{statement.settings.account_number||''}}</p></section>
        <p v-if="statement.pending.length" class="statement-incomplete">待补资料：{{statement.pending.join('；')}}</p>
      </article></div>
    </template>
  </section>
</template>
<script setup>
import {reactive,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import AppForm from './AppForm.vue'
import CustomerStatementSettings from './CustomerStatementSettings.vue'
import {getStatement,exportStatement} from '@/api/customerStatements'
import {businessDateTimeInputValue} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {statementPrintStyles} from '@/utils/customerStatementPrint'
const props=defineProps({projectId:{type:[String,Number],default:''},orderId:{type:[String,Number],default:''},clientId:{type:[String,Number],default:''},billingMonth:String})
const filters=reactive({month:props.billingMonth||businessDateTimeInputValue().slice(0,7),scope:'project'})
const statement=ref(null),loading=ref(false),exporting=ref(false),error=ref(''),paper=ref()
let controller,sequence=0
const printFrames=new Set()
const number=value=>String(value).replace(/(\.\d*?[1-9])0+$|\.0+$/,'$1')
const params=()=>({project_id:props.projectId,order_id:props.orderId||undefined,month:filters.month,scope:filters.scope})
function invalidate(){sequence++;controller?.abort();statement.value=null;error.value='';loading.value=false}
async function generate(){if(!props.projectId||!filters.month)return;controller?.abort();controller=new AbortController();const seq=++sequence;statement.value=null;error.value='';loading.value=true;try{const data=await getStatement(params(),{signal:controller.signal});if(seq===sequence)statement.value=data}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'对账单生成失败')}finally{if(seq===sequence)loading.value=false}}
async function download(){exporting.value=true;try{const blob=await exportStatement({...params(),version:statement.value.statement_version});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=`信实翻译对账单_${statement.value.month}.xlsx`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){error.value=e.response?.status===409?'对账单数据已变化，请重新生成后下载':getLocalizedErrorMessage(e,'Excel下载失败')}finally{exporting.value=false}}
function print(){if(!paper.value)return;const frame=document.createElement('iframe');frame.style.cssText='position:fixed;width:0;height:0;border:0;right:0;bottom:0';frame.title='对账单打印';printFrames.add(frame);const cleanup=()=>{printFrames.delete(frame);frame.remove()};frame.srcdoc=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>信实翻译对账单</title><style>${statementPrintStyles}</style></head><body>${paper.value.outerHTML}</body></html>`;frame.onload=async()=>{try{await Promise.all([...frame.contentDocument.images].map(image=>image.decode().catch(()=>{})));frame.contentWindow.addEventListener('afterprint',cleanup,{once:true});frame.contentWindow.focus();frame.contentWindow.print()}catch{cleanup();ElMessage.error('打印窗口打开失败')}};document.body.appendChild(frame)}
function preferenceChanged(event){if(String(event.detail?.clientId)===String(props.clientId))invalidate()}
watch(()=>[props.projectId,props.orderId],()=>{filters.month=props.billingMonth||businessDateTimeInputValue().slice(0,7);filters.scope='project';invalidate()})
onMounted(()=>window.addEventListener('customer-statement-preference-saved',preferenceChanged))
onBeforeUnmount(()=>{for(const frame of printFrames)frame.remove();printFrames.clear();invalidate();window.removeEventListener('customer-statement-preference-saved',preferenceChanged)})
</script>
<style>
.statement-paper{background:#fff;color:#222;padding:28px;min-width:780px;font-family:'Microsoft YaHei',sans-serif}.statement-paper h2,.statement-paper h3{text-align:center;margin:0 0 12px}.statement-paper h2{font-size:22px}.statement-paper h3{font-size:20px}.statement-meta{display:flex;justify-content:space-between;margin:20px 0 12px}.statement-table-wrap{position:relative}.statement-table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}.statement-table th,.statement-table td{border:1px solid #777;padding:10px 6px;text-align:center;overflow-wrap:anywhere;white-space:pre-wrap}.statement-table th:nth-child(2){width:21%}.statement-table th:nth-child(4){width:18%}.statement-table th:nth-child(5){width:16%}.statement-table tfoot{font-weight:700}.statement-table tfoot td{height:56px}.statement-total-label{text-align:right!important;padding-right:20px!important}.statement-stamp{position:absolute;z-index:2;pointer-events:none;width:135px;height:135px;object-fit:contain;left:45%;bottom:-18px;opacity:.85;mix-blend-mode:multiply}.statement-account{margin-top:32px;break-inside:avoid}.statement-account h4{font-size:15px;margin:0 0 14px}.statement-account p{margin:7px 0;font-size:13px}.statement-incomplete{font-size:11px;color:#9b3c15}
</style>
<style scoped>
.statement-hint{font-size:12px;color:var(--el-text-color-secondary)}.statement-scroll{overflow-x:auto;border:1px solid var(--el-border-color);margin-top:14px}.statement-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0}.statement-actions>span{font-size:13px}.customer-statement-panel{min-width:0}
</style>
