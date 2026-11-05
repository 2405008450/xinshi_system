<template><section class="statement-full-page"><el-page-header title="返回" :content="`对账单 · ${clientName||'客户对账单'}`" @back="router.back()" /><CustomerStatementWorkspace :client-id="String(route.params.clientId)" :focus-board-id="String(route.params.boardId||'')" :focus-month="route.params.boardId?'':String(route.query.month||'')" :billing-month="String(route.query.month||'')" @loaded="data=>{if(data.client_name)clientName=data.client_name}" /></section></template>
<script setup>
import {ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import CustomerStatementWorkspace from '@/components/common/CustomerStatementWorkspace.vue'
const route=useRoute(),router=useRouter(),clientName=ref('')
watch(()=>route.params.clientId,()=>{clientName.value=''})
</script>
<style scoped>.statement-full-page{display:flex;flex-direction:column;gap:16px;min-width:0}</style>
