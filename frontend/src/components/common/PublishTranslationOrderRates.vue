<template>
  <template v-if="canWrite">
    <el-button :disabled="disabled || publishing" @click="publish(false)">同步到客户管理客户</el-button>
    <el-button v-if="subClientId" :disabled="disabled || publishing" @click="publish(true)">同步到客户管理子客户</el-button>
  </template>
</template>

<script setup>
import {ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {synchronizeCustomerRates} from '@/api/customerFinanceSync'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {taxPriceSummary, taxUnitAmount} from '@/utils/taxPrices'

const props=defineProps({subClientId:String,prepare:Function,disabled:Boolean})
const emit=defineEmits(['synced'])
const canWrite=hasPermission('clients:write')
const publishing=ref(false)
async function publish(toSubClient){
  if(!canWrite||props.disabled||publishing.value)return
  publishing.value=true
  try{
    const {data,node}=await props.prepare()
    const subClientId=toSubClient ? node.subClientId : null
    if(toSubClient && !subClientId)throw new Error('请先保存关联的子客户')
    const library=subClientId ? data.subClientReferencePrices : data.referencePrices
    const buyer=subClientId ? node.subClientShortName || node.subClientCode : node.clientShortName || '当前客户'
    const label=`${subClientId?'子客户':'客户'}「${buyer}」`
    const prices=node.prices.filter(price=>taxUnitAmount(price.taxPrices,price.amount)!=null)
    if(!library?.ready || !prices.length)throw new Error('参考价尚未就绪，或该订单没有已填写的单价')
    const priceLabels=prices.map(price=>[price.languagePair,
      taxPriceSummary(price.taxPrices,price.currency,`${price.unitSize}单位`,false) ||
        `${price.currency} ${price.amount} / ${price.unitSize}`].join(' ')).join('；')
    try{
      await ElMessageBox.confirm(`将订单 ${node.orderNo} 的单价同步至${label}参考价。\n${priceLabels}`,
        '确认同步项目单价',{type:'warning'})
    }catch{return}
    await synchronizeCustomerRates('translation',node.clientId,{
      project_id:node.rootId,order_id:node.id,version:data.version,
      customer_version:library.version,sub_client_id:subClientId,direction:'project_to_client',confirmed:true,
    })
    ElMessage.success(`已同步至${label}参考价`)
    window.dispatchEvent(new CustomEvent('translation-finance-changed',{detail:{clientId:String(node.clientId)}}))
    emit('synced')
  }catch(cause){
    ElMessage.error(getLocalizedErrorMessage(cause,cause.message||'同步项目单价失败'))
  }finally{
    publishing.value=false
  }
}
</script>
