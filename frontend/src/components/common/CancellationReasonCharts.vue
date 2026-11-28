<template><section><div class="reason-breadcrumb"><el-button link @click="path=[]">全部原因</el-button><template v-for="(label,index) in path" :key="index"><span> / </span><el-button link @click="path=path.slice(0,index+1)">{{label}}</el-button></template><el-button v-if="path.length" @click="path=path.slice(0,-1)">返回上一级</el-button></div><p>按项目去重；多选原因的项目可计入多个原因，比例以本级原因计次为分母。点击扇形或文字查看客户；有下级时同时展开下一级。</p><ProjectStatusPie :title="path.length?path.join(' / '):'未成交一级原因'" :columns="columns" :counts="counts" unit="次原因归类" @select="select"/><StatisticsCustomersDialog ref="customers"/></section></template>
<script setup>
import {computed,ref,watch} from 'vue'
import ProjectStatusPie from './ProjectStatusPie.vue'
import StatisticsCustomersDialog from './StatisticsCustomersDialog.vue'
const props=defineProps({rows:{type:Array,default:()=>[]}}),path=ref([]),customers=ref()
const paths=row=>row.classification_paths?.length?row.classification_paths:[[row.reason||'未填写']]
const grouped=computed(()=>{const groups=new Map();for(const row of props.rows){const seen=new Set();for(const parts of paths(row)){if(!path.value.every((key,index)=>parts[index]===key))continue;const label=parts[path.value.length]||'本级原因（无下级）';if(seen.has(label))continue;seen.add(label);if(!groups.has(label))groups.set(label,[]);groups.get(label).push(row)}}return groups})
const columns=computed(()=>[...grouped.value.keys()].map(key=>({key,label:key}))),counts=computed(()=>Object.fromEntries([...grouped.value].map(([key,rows])=>[key,{count:rows.length}])))
function select(slice){const rows=grouped.value.get(slice.key)||[];customers.value.open(slice.label,rows);if(rows.some(row=>paths(row).some(parts=>parts[path.value.length]===slice.key&&parts.length>path.value.length+1)))path.value=[...path.value,slice.key]}
watch(()=>props.rows,()=>path.value=[])
</script>
<style scoped>.reason-breadcrumb{display:flex;align-items:center;gap:8px;flex-wrap:wrap}p{font-size:12px;color:var(--el-text-color-secondary)}</style>
