<template>
  <section v-if="showEmpty||items.length||error" class="settlement-numbers" data-dialog-field-search-label="结算编号与修改记录">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p v-else-if="showEmpty&&!items.length" class="settlement-number-help">
      <strong>结算编号与修改记录</strong>
      <span>{{loading?'正在加载…':'填写实际付款金额并保存后生成结算编号，点击编号可查看该笔付款的修改记录。'}}</span>
    </p>
    <el-collapse v-if="items.length" v-model="expanded" @change="loadHistory">
      <el-collapse-item v-for="entry in items" :key="entry.number" :name="entry.number">
        <template #title><strong>结算编号 {{entry.number}}</strong>&nbsp;·&nbsp;{{entry.payment_key==='full'?'全款':'第'+Number(entry.number.split('.').at(-1))+'期付款'}}&nbsp;·&nbsp;修改记录</template>
        <div v-loading="pending.has(entry.number)">
          <p>首次登记 {{formatBusinessDateTime(entry.issued_at)}}</p>
          <el-alert v-if="historyErrors[entry.number]" :title="historyErrors[entry.number]" type="error" :closable="false" />
          <template v-if="histories[entry.number]">
            <h4>调整记录</h4>
            <el-table :data="changeRows(histories[entry.number])" size="small" border max-height="320" empty-text="暂无调整记录">
              <el-table-column label="时间" width="165"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column>
              <el-table-column label="操作人" prop="actor_name" width="110" />
              <el-table-column label="调整内容" prop="description" min-width="170" />
              <el-table-column label="调整前" prop="previous" min-width="100" />
              <el-table-column label="调整后" prop="current" min-width="100" />
            </el-table>
          </template>
        </div>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<script setup>
import {onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import api from '@/api'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {connectPaymentSync,paymentChangeEvent} from '@/utils/paymentConfirmation'

const props=defineProps({projectId:{type:String,required:true},showEmpty:Boolean})
const items=ref([]),expanded=ref([]),error=ref(''),loading=ref(false)
const histories=reactive({}),historyErrors=reactive({}),pending=reactive(new Set())
let controller
const path=()=>`/translation-payments/${props.projectId}/settlement-numbers`
const totals=values=>Object.entries(values||{}).map(([currency,value])=>`${currency} ${value}`).join('、')||'—'
function payment(state){
  if(!state)return '—'
  return [state.full_payment_currency,state.full_payment_amount??state.actual_amount,state.payment_account||state.payment_method].filter(value=>value!==null&&value!==undefined&&value!=='').join(' ')||'—'
}
function changeRows(history){
  return [...history.payments.map(row=>({...row,description:row.action,previous:payment(row.before),current:payment(row.after)})),
    ...history.finance.map(row=>({...row,description:`${row.order_no} · ${row.changes.join('、')}`,
      previous:totals(row.before_totals),current:totals(row.after_totals)}))].sort((a,b)=>b.created_at.localeCompare(a.created_at))
}
async function loadHistory(){
  const request=controller
  if(!request||request.signal.aborted)return
  await Promise.all(expanded.value.filter(number=>!histories[number]&&!pending.has(number)).map(async number=>{
    pending.add(number)
    delete historyErrors[number]
    try{
      const value=await api.get(`${path()}/${number}`,{signal:request.signal})
      if(!request.signal.aborted)histories[number]=value
    }catch(e){
      if(!request.signal.aborted)historyErrors[number]=getLocalizedErrorMessage(e,'调整记录加载失败')
    }finally{if(!request.signal.aborted)pending.delete(number)}
  }))
}
async function load(){
  controller?.abort()
  const request=controller=new AbortController()
  pending.clear()
  for(const number of Object.keys(histories))delete histories[number]
  for(const number of Object.keys(historyErrors))delete historyErrors[number]
  error.value=''
  loading.value=true
  try{
    const data=await api.get(path(),{signal:request.signal})
    if(request.signal.aborted)return
    items.value=data.items||[]
    if(data.ready===false&&props.showEmpty)error.value='结算编号存储尚未初始化。'
    await loadHistory()
  }catch(e){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'结算编号加载失败')}
  finally{if(!request.signal.aborted)loading.value=false}
}
function changed(event){
  if(!event.detail?.projectId||event.detail.projectId===props.projectId||event.detail.syncScope)void load()
}
watch(()=>props.projectId,()=>{items.value=[];expanded.value=[];void load()},{immediate:true})
onMounted(()=>{
  connectPaymentSync()
  window.addEventListener(paymentChangeEvent,changed)
  window.addEventListener('translation-statements-changed',changed)
  window.addEventListener('translation-word-count-saved',changed)
})
onBeforeUnmount(()=>{
  controller?.abort()
  window.removeEventListener(paymentChangeEvent,changed)
  window.removeEventListener('translation-statements-changed',changed)
  window.removeEventListener('translation-word-count-saved',changed)
})
</script>

<style scoped>
.settlement-numbers{margin:12px 0}
.settlement-number-help{display:flex;flex-wrap:wrap;gap:4px 12px;color:var(--el-text-color-secondary);font-size:12px}
</style>
