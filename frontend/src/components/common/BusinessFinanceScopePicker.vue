<template>
 <AppForm :model="filters" inline data-auto-draft="off" @submit.prevent="load()">
  <el-form-item label="客户经理"><el-select v-model="filters.manager" style="width:150px" @change="resetScope"><el-option label="本人" value="self"/><el-option label="全部客户经理" value="all"/><el-option label="指定客户经理" value="name"/></el-select><FinanceManagerNameSelect v-if="filters.manager==='name'" v-model="filters.managerName" @change="resetScope"/></el-form-item>
  <el-form-item label="客户"><el-select v-model="filters.client" filterable remote clearable :remote-method="searchClients" :loading="loading" placeholder="搜索并选择客户" style="width:260px" @change="changeClient"><el-option v-for="row in clients" :key="row.id" :value="row.id" :label="row.label"/></el-select></el-form-item>
  <el-form-item v-if="filters.client" label="项目／结算范围"><el-select :model-value="modelValue" filterable :loading="loading" placeholder="请选择项目" style="width:320px" @update:model-value="choose"><el-option v-for="row in projects" :key="row.id" :value="row.id" :label="row.order_no+' · '+row.project_name"/></el-select></el-form-item>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
 </AppForm>
</template>
<script setup>
import {computed,onMounted,onBeforeUnmount,reactive,ref} from 'vue'
import api from '@/api'
import AppForm from './AppForm.vue'
import FinanceManagerNameSelect from './FinanceManagerNameSelect.vue'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:String,module:{type:String,default:'interpretation'},query:{type:Object,default:()=>({})}})
const emit=defineEmits(['update:modelValue','select'])
const filters=reactive({manager:props.query.only_mine?'self':props.query.client_manager?'name':'all',managerName:props.query.client_manager||'',client:''})
const rows=ref([]),clientRows=ref([]),loading=ref(false),error=ref('');let sequence=0,controller,timer
const clients=computed(()=>[...new Map(clientRows.value.filter(row=>row.client_id).map(row=>[row.client_id,{id:row.client_id,label:row.client_short_name||row.client_name||row.client_full_name||row.client_id}])).values()])
const projects=computed(()=>rows.value.filter(row=>!filters.client||row.client_id===filters.client))
async function load(keyword='',forClients=false){const seq=++sequence;controller?.abort();const request=controller=new AbortController();loading.value=true;error.value='';try{const params={...props.query,only_mine:filters.manager==='self',client_manager:filters.manager==='name'?filters.managerName:'',client_id:forClients?undefined:filters.client||undefined,keyword,skip:0,limit:100};const data=await api.get(props.module==='interpretation'?'/interpretation-customer-finance/page':`/business-finance/${props.module}/page`,{params,signal:request.signal});if(seq!==sequence)return;rows.value=data.items||[];if(forClients)clientRows.value=rows.value}catch(e){if(!request.signal.aborted)error.value=getLocalizedErrorMessage(e,'结算项目加载失败')}finally{if(seq===sequence)loading.value=false}}
function searchClients(keyword){clearTimeout(timer);if(!keyword)return void load('',true);timer=setTimeout(()=>void load(keyword,true),400)}
function choose(id){emit('update:modelValue',id);emit('select',projects.value.find(row=>row.id===id)||null)}
async function changeClient(){choose('');if(!filters.client)return;await load();if(projects.value.length)choose(projects.value[0].id)}
function resetScope(){filters.client='';rows.value=[];choose('');void load('',true)}
onMounted(()=>void load('',true));onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
</script>
