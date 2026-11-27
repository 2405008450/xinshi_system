<template>
  <div class="department-paged-list">
    <section v-for="group in result.groups" :key="group.name" class="department-paged-list__group">
      <header v-if="grouped" class="department-paged-list__heading"><strong>{{group.name}}</strong><span>本页 {{group.rows.length}} 条</span></header>
      <slot :rows="group.rows" :department="group.name" />
    </section>
    <slot v-if="!result.groups.length" :rows="[]" :department="''" />
    <el-pagination v-model:current-page="currentPage" v-model:page-size="currentSize" :page-sizes="[10,20,50]" :total="rowTotal" layout="total,sizes,prev,pager,next" @current-change="changed" @size-change="sizeChanged" />
  </div>
</template>
<script setup>
import {computed,inject,ref,watch} from 'vue'
import {departmentPagedLists} from '@/utils/departmentPagedLists'
const props=defineProps({items:{type:Array,default:()=>[]},grouped:Boolean,server:Boolean,total:{type:Number,default:0},page:{type:Number,default:1},pageSize:{type:Number,default:20}})
const emit=defineEmits(['update:page','update:pageSize','change'])
const names=inject('attendance-department-names',computed(()=>({})))
const localPage=ref(1),localSize=ref(20)
const currentPage=computed({get:()=>props.server?props.page:localPage.value,set:value=>props.server?emit('update:page',value):localPage.value=value})
const currentSize=computed({get:()=>props.server?props.pageSize:localSize.value,set:value=>props.server?emit('update:pageSize',value):localSize.value=value})
const result=computed(()=>departmentPagedLists(props.items,{names:names.value,grouped:props.grouped,page:currentPage.value,pageSize:currentSize.value,server:props.server}))
const rowTotal=computed(()=>props.server?props.total:result.value.total)
watch(()=>props.items,()=>{if(!props.server)localPage.value=1})
let queued=false
function changed(){if(props.server&&!queued){queued=true;queueMicrotask(()=>{queued=false;emit('change')})}}
function sizeChanged(){currentPage.value=1;changed()}
</script>
<style scoped>.department-paged-list :deep(.el-table){margin:0}</style>
<style scoped>.department-paged-list{min-width:0;margin:12px 0}.department-paged-list__group{margin-bottom:16px;min-width:0}.department-paged-list__heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 12px;background:#f1f5f9;border:1px solid #dbe3ed;border-bottom:0;border-radius:6px 6px 0 0}.department-paged-list__heading span{font-size:12px;color:#64748b}.department-paged-list :deep(.el-pagination){display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}</style>
