<template>
  <section v-if="children.length" class="statement-sub-client-workspaces">
    <h4>子客户对账单（{{children.length}}）</h4>
    <el-collapse v-model="expanded">
      <el-collapse-item v-for="child in children" :key="child.id" :name="child.id">
        <template #title><div class="sub-client-heading"><strong>{{child.name}}</strong><small>{{child.code}} · {{child.statementProjectCount}} 个项目<span v-if="child.pendingCount"> · 待入账 {{child.pendingCount}} 项</span> · 子客户合并结算</small></div></template>
        <CustomerStatementClientWorkspace v-if="expanded.includes(child.id)" :client="client" :sub-client-id="child.id" :month="month" :period-number="periodNumber" settlement-scope="standard" required :manager-query="managerQuery" />
      </el-collapse-item>
    </el-collapse>
  </section>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import CustomerStatementClientWorkspace from './CustomerStatementClientWorkspace.vue'
const props=defineProps({client:{type:Object,required:true},month:String,periodNumber:Number,managerQuery:{type:Object,default:()=>({})}})
const expanded=ref([])
const children=computed(()=>(props.client.subClients||[]).filter(child=>child.statementProjectCount>0))
watch(()=>[props.client.id,props.month,props.periodNumber,JSON.stringify(props.managerQuery)],()=>{expanded.value=[]})
</script>
<style scoped>
.statement-sub-client-workspaces{margin:8px 0 18px;padding:12px;border:1px solid var(--el-border-color);border-radius:8px;min-width:0}
h4{margin:0 0 8px}.sub-client-heading{display:grid;gap:3px;line-height:1.6;padding:8px 0}.sub-client-heading small{color:var(--el-text-color-secondary)}
.statement-sub-client-workspaces :deep(.el-collapse-item__header){height:auto;min-height:48px}
</style>
