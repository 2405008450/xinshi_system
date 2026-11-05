<template>
  <div class="statement-audit-details">
    <table v-if="rows.length" class="statement-audit-table"><thead><tr><th>修改项目</th><th>修改前</th><th>修改后</th></tr></thead><tbody><tr v-for="(row,index) in rows" :key="index"><th scope="row">{{row.field}}</th><td>{{row.before}}</td><td>{{row.after}}</td></tr></tbody></table>
    <span v-else class="statement-audit-empty">未记录具体字段变化</span>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import {statementAuditRows,statementSnapshotRows} from '@/utils/statementAuditDisplay'
const props=defineProps({changes:[Object,Array],before:Object,after:Object,labels:Object,boards:Array,tasks:Object})
const rows=computed(()=>props.before&&props.after?statementSnapshotRows(props.before,props.after,props):statementAuditRows(props.changes||{},props))
</script>
<style scoped>
.statement-audit-details{max-height:420px;overflow:auto}.statement-audit-table{border-collapse:collapse;width:100%;font-size:12px;background:var(--el-bg-color)}.statement-audit-table th,.statement-audit-table td{padding:8px 10px;border:1px solid var(--el-border-color-lighter);text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere;min-width:90px}.statement-audit-table thead th{font-weight:600;background:var(--el-fill-color-light);position:sticky;top:0}.statement-audit-table tbody th{font-weight:500;width:32%;color:var(--el-text-color-regular)}.statement-audit-table td{width:34%}.statement-audit-empty{color:var(--el-text-color-secondary)}
</style>
