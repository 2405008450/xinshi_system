<template>
  <section class="arrangement-order-picker" v-loading="loading">
    <div class="order-picker-heading"><strong>安排订单（可多选）</strong><span>已选 {{modelValue.length}} 个</span><el-button text :disabled="loading" @click="load">刷新订单</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-tree v-else ref="tree" :data="orders" node-key="id" show-checkbox check-strictly :default-expanded-keys="[projectId]" :default-checked-keys="modelValue" :props="{label:'order_no'}" @check="check">
      <template #default="{data}"><span class="arrangement-target-order" @dragover.stop.prevent @drop.stop.prevent="emit('drop-order',$event,data.id)"><el-tag size="small">{{data.level===1?'母订单':data.level===2?'子订单':`${data.level}级订单`}}</el-tag><span class="target-order-name">{{data.order_no}} · {{data.project_name}}</span><el-button link type="primary" :disabled="disabled" @click.stop="emit('arrange-order',data.id)">安排此订单</el-button></span></template>
    </el-tree>
    <small>勾选仅作用于所选订单，不自动包含其下级。拖入人员时安排到当前订单。</small>
  </section>
</template>
<script setup>
import {nextTick,onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
const props=defineProps({projectId:{type:String,required:true},modelValue:{type:Array,default:()=>[]},disabled:Boolean})
const emit=defineEmits(['update:modelValue','arrange-order','drop-order']),orders=ref([]),loading=ref(false),error=ref(''),tree=ref()
let sequence=0,controller
function check(_data,state){emit('update:modelValue',state.checkedKeys)}
async function load(){const request=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const result=await api.get(`/project-arrangements/project/${props.projectId}/orders`,{signal:controller.signal});if(request!==sequence)return;orders.value=result.items||[];const ids=new Set();function collect(nodes){for(const node of nodes){ids.add(node.id);collect(node.children||[])}}collect(orders.value);emit('update:modelValue',props.modelValue.filter(id=>ids.has(id)));await nextTick();if(request===sequence)tree.value?.setCheckedKeys(props.modelValue)}catch{if(request===sequence)error.value='订单加载失败，请刷新后重试'}finally{if(request===sequence)loading.value=false}}
watch(()=>props.projectId,load,{immediate:true});watch(()=>props.modelValue,()=>tree.value?.setCheckedKeys(props.modelValue),{deep:true})
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>
.arrangement-order-picker{margin:10px 0;padding:12px;border:1px solid #e2e8f0;border-radius:6px;max-width:100%;box-sizing:border-box}.order-picker-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}.arrangement-order-picker :deep(.el-tree){max-height:260px;overflow:auto}.arrangement-order-picker :deep(.el-tree-node__content){height:auto;min-height:36px}.arrangement-target-order{display:flex;align-items:center;gap:10px;min-width:0;flex:1;white-space:normal;padding:4px 0}.target-order-name{overflow-wrap:anywhere;flex:1}.arrangement-order-picker small{color:#64748b;display:block;margin-top:8px}
</style>
