<template><div><el-table :data="pageRows" border :max-height="height" empty-text="暂无匹配记录" @sort-change="sort=$event"><el-table-column v-for="column in columns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.width||140" :sortable="column.sortable===false?false:'custom'"><template #header><span v-if="column.filter===false">{{column.label}}</span><ColumnHeaderFilter v-else hide-default-footer :label="column.label" :active="!!filters[column.key]" @clear="filters[column.key]=''"><el-input :model-value="draft[column.key]||''" clearable placeholder="多个关键词，空格分隔" @input="value=>queue(column.key,value)" @keyup.enter="apply(column.key)"/><div style="display:flex;gap:8px;margin-top:10px"><el-button @click="filters[column.key]='';draft[column.key]=''">清空</el-button><el-button type="primary" @click="apply(column.key)">筛选</el-button></div></ColumnHeaderFilter></template><template #default="{row}"><slot name="cell" :row="row" :column="column" :value="display(row,column)">{{display(row,column)}}</slot></template></el-table-column></el-table><el-pagination v-if="filtered.length>pageSize" v-model:current-page="page" :page-size="pageSize" :total="filtered.length" layout="total, prev, pager, next"/></div></template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import ColumnHeaderFilter from './ColumnHeaderFilter.vue'
import {matchesSearch} from '@/utils/searchMatching'
const props=defineProps({rows:{type:Array,default:()=>[]},columns:{type:Array,default:()=>[]},height:{type:[Number,String],default:430},pageSize:{type:Number,default:20}}),emit=defineEmits(['filtered'])
const filters=reactive({}),draft=reactive({}),page=ref(1),sort=ref({}),timers=new Map()
const display=(row,column)=>column.format?column.format(row):column.get?column.get(row):row[column.key]??'—'
const filtered=computed(()=>{const rows=props.rows.filter(row=>props.columns.every(column=>matchesSearch(String(display(row,column)??''),filters[column.key]||'')));const col=props.columns.find(column=>column.key===sort.value.prop);if(col&&sort.value.order)rows.sort((a,b)=>{const first=col.sort?col.sort(a):col.get?col.get(a):a[col.key],second=col.sort?col.sort(b):col.get?col.get(b):b[col.key];const compare=typeof first==='number'&&typeof second==='number'?first-second:String(first??'').localeCompare(String(second??''),'zh-CN',{numeric:true});return sort.value.order==='ascending'?compare:-compare});return rows})
const pageRows=computed(()=>filtered.value.slice((page.value-1)*props.pageSize,page.value*props.pageSize))
function apply(key){clearTimeout(timers.get(key));filters[key]=draft[key]||'';page.value=1}
function queue(key,value){draft[key]=value;clearTimeout(timers.get(key));if(!value)return apply(key);timers.set(key,setTimeout(()=>apply(key),400))}
watch(filtered,value=>{page.value=1;emit('filtered',value)},{immediate:true})
onBeforeUnmount(()=>timers.forEach(clearTimeout))
</script>
