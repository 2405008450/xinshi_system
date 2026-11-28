<template>
 <div class="statistics-pie">
  <svg viewBox="0 0 240 240" role="img" :aria-label="`${title}饼图，共 ${total} ${unit}`">
   <circle v-if="!total" cx="120" cy="120" r="100" fill="#e2e8f0"/>
   <template v-for="slice in slices" :key="slice.key">
    <path v-if="slice.count<total" :d="slice.path" :fill="slice.color" stroke="white" stroke-width="2" tabindex="0" role="button" :aria-label="`${slice.label} ${slice.count} 个，占 ${slice.share.toFixed(2)}%${slice.key==='deal_merged'?'，点击查看四个状态详情':''}`" @click="select(slice)" @keydown.enter.prevent="select(slice)" @keydown.space.prevent="select(slice)"><title>{{slice.label}}：{{slice.count}} 个（{{slice.share.toFixed(2)}}%）</title></path>
    <circle v-else cx="120" cy="120" r="100" :fill="slice.color" tabindex="0" role="button" :aria-label="slice.label+'，点击查看详情'" @click="select(slice)" @keydown.enter.prevent="select(slice)" @keydown.space.prevent="select(slice)"><title>{{slice.label}}：{{slice.count}} 个（100%）</title></circle>
   </template>
  </svg>
  <div class="statistics-pie-legend"><div v-for="slice in slices" :key="slice.key"><i :style="{background:slice.color}"/><button type="button" @click="select(slice)">{{slice.label}} · {{slice.count}} / {{slice.share.toFixed(2)}}%{{slice.key==='deal_merged'?' · 查看四个状态':''}}</button></div><span v-if="!total">当前范围暂无数据</span></div>
  <el-popover :visible="details" placement="bottom" :width="420" :popper-style="{maxWidth:'calc(100vw - 32px)'}"><template #reference><span class="pie-detail-anchor"/></template><div class="deal-details-heading"><strong>四个已成交状态详情</strong><el-button link aria-label="关闭状态详情" @click="details=false">×</el-button></div><el-table :data="dealRows" border size="small"><el-table-column prop="label" label="状态"/><el-table-column prop="count" label="数量" width="65"/><el-table-column label="占全部项目"><template #default="{row}">{{percent(row.count,total)}}</template></el-table-column><el-table-column label="占已成交"><template #default="{row}">{{percent(row.count,dealTotal)}}</template></el-table-column></el-table></el-popover>
 </div>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
const props=defineProps({title:{type:String,default:'项目状态'},unit:{type:String,default:'个项目'},columns:{type:Array,default:()=>[]},counts:{type:Object,default:()=>({})},deals:{type:Object,default:()=>({})}})
const colors=['#2563eb','#16a34a','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#db2777','#64748b','#84cc16','#f97316','#4f46e5','#0d9488','#a855f7','#b45309','#0284c7','#be123c','#6b7280','#15803d','#c026d3','#ca8a04']
const total=computed(()=>Object.values(props.counts).reduce((sum,row)=>sum+Number(row.count||0),0))
const slices=computed(()=>{let angle=-Math.PI/2;return props.columns.flatMap((column,index)=>{const count=Number(props.counts[column.key]?.count||0);if(!count)return [];const start=angle;angle+=count/total.value*2*Math.PI;const point=a=>`${120+100*Math.cos(a)} ${120+100*Math.sin(a)}`;return [{...column,count,color:colors[index%colors.length],share:count/total.value*100,path:`M 120 120 L ${point(start)} A 100 100 0 ${count/total.value>0.5?1:0} 1 ${point(angle)} Z`}]})})
const details=ref(false),dealRows=computed(()=>Object.entries(props.deals).map(([key,row])=>({key,...row}))),dealTotal=computed(()=>dealRows.value.reduce((sum,row)=>sum+Number(row.count||0),0))
const percent=(count,total)=>total?(count/total*100).toFixed(2)+'%':'0.00%'
const emit=defineEmits(['select'])
function select(slice){emit('select',slice);if(slice.key==='deal_merged')details.value=!details.value}
watch(()=>props.counts,()=>details.value=false)
</script>
<style scoped>.statistics-pie{display:flex;align-items:center;gap:24px;position:relative;padding:12px;border:1px solid var(--el-border-color-light);border-radius:8px;margin-bottom:16px}.statistics-pie svg{width:240px;max-width:100%;flex:none}.statistics-pie [role=button]{cursor:pointer}.statistics-pie-legend{display:grid;gap:9px;min-width:0;max-height:260px;overflow:auto}.statistics-pie-legend>div{display:flex;align-items:center;gap:8px}.statistics-pie-legend i{width:12px;height:12px;border-radius:2px;flex:none}.statistics-pie-legend button{border:0;background:none;color:var(--el-color-primary);font:inherit;cursor:pointer;padding:0;text-align:left}.pie-detail-anchor{position:absolute;left:120px;bottom:12px}.deal-details-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}@media(max-width:650px){.statistics-pie{flex-direction:column;align-items:stretch}.statistics-pie svg{align-self:center;width:200px}}</style>
