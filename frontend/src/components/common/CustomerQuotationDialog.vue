<template>
  <DraggableFormDialog :model-value="modelValue" class="customer-quotation-dialog" width="min(1180px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" @update:model-value="close">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="报价单" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading">
      <AppForm ref="formRef" :model="document" label-position="top" :disabled="!canWrite||saving">
        <el-form-item v-if="!deferSave" label="项目"><el-select v-model="selectedId" filterable remote :remote-method="searchProjects" :loading="searching" placeholder="搜索订单号、项目名称或客户" style="width:100%" @change="load"><el-option v-for="project in options" :key="project.id" :value="project.id" :label="`${project.orderNo} · ${project.projectName||'-'}`" /></el-select></el-form-item>
        <el-form-item label="订单号"><ReadonlyField :model-value="orderNo || '保存项目后自动生成'" source="auto" /></el-form-item>
        <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="报价单标题" prop="title" :rules="[{required:true,message:'请填写报价单标题',trigger:'blur'}]"><el-input v-model="document.title" maxlength="255" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="客户名称"><el-input v-model="document.client_name" maxlength="255" /></el-form-item></el-col></el-row>
        <div v-for="(item,index) in document.items" :key="index" class="quotation-line" data-dialog-field-search-group :data-dialog-field-search-group-title="`报价明细 ${index+1}`">
          <div class="quotation-line-heading"><strong>报价明细 {{index+1}}</strong><el-button link type="danger" @click="document.items.splice(index,1)">移除</el-button></div>
          <el-row :gutter="12"><el-col :xs="24" :md="12"><el-form-item label="项目/服务内容"><el-input v-model="item.description" maxlength="1000" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="语种方向"><LanguagePairSelect v-model="item.language_pair" /></el-form-item></el-col></el-row>
          <el-row :gutter="12"><el-col :xs="12" :md="6"><el-form-item label="数量"><el-input-number v-model="item.quantity" :min="0" :precision="4" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="计价单位"><el-input v-model="item.unit" maxlength="50" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="单价"><el-input-number v-model="item.unit_price" :min="0" :precision="4" :controls="false" /></el-form-item></el-col><el-col :xs="12" :md="6"><el-form-item label="货币"><el-select v-model="item.currency"><el-option v-for="currency in currencies" :key="currency" :value="currency" /></el-select></el-form-item></el-col></el-row>
          <p>金额：{{lineTotal(item)}} {{item.currency}}</p>
        </div>
        <el-button @click="document.items.push(newLine())">新增报价明细</el-button>
        <p class="quotation-totals">合计：{{totals}}</p>
        <el-form-item label="说明/报价条件"><el-input v-model="document.notes" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item>
      </AppForm>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <p v-if="deferSave" class="quotation-help">报价内容随项目一起保存。</p>
    </div>
    <template #footer><el-button :disabled="saving" @click="close(false)">取消</el-button><el-button v-if="canWrite" type="primary" :loading="saving" :disabled="loading||(!deferSave&&!selectedId)" @click="save">{{deferSave?'应用到项目':'保存报价单'}}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import api from '@/api'
import {getCustomerFinancePage} from '@/api/translationCustomerFinance'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {quotationLineCents,quotationMoney} from '@/utils/quotation'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
const props=defineProps({modelValue:Boolean,projects:{type:Array,default:()=>[]},query:{type:Object,default:()=>({})},draftProject:{type:Object,default:null},draft:{type:Object,default:null},deferSave:Boolean})
const emit=defineEmits(['update:modelValue','update:draft','saved'])
const currencies=['CNY','USD','HKD','EUR','GBP','JPY'],canWrite=hasPermission('projects:write')
const body=ref(),formRef=ref(),options=ref([]),selectedId=ref(''),orderNo=ref(''),loading=ref(false),searching=ref(false),saving=ref(false),error=ref('')
const document=reactive({title:'翻译服务报价单',client_name:'',items:[],notes:''})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let revision=0,sequence=0,searchSequence=0,original='',controller
const newLine=()=>({description:'',language_pair:'',quantity:undefined,unit:'字',unit_price:undefined,currency:'CNY'})
const lineTotal=item=>quotationLineCents(item)==null?'待填写数量及单价':quotationMoney(quotationLineCents(item))
const totals=computed(()=>{const sums={};let incomplete=false;for(const item of document.items){const cents=quotationLineCents(item);if(cents==null){incomplete=true;continue}const currency=item.currency||'CNY';sums[currency]=(sums[currency]||0n)+cents}return Object.entries(sums).map(([currency,value])=>`${currency} ${quotationMoney(value)}`).join('；')+(incomplete?'（部分明细待填写）':'')||'-'})
function assign(data){data={title:data.title||'翻译服务报价单',client_name:data.client_name??data.clientName??'',items:(data.items||[]).map(item=>({description:item.description||'',language_pair:item.language_pair??item.languagePair??'',quantity:item.quantity,unit:item.unit||'字',unit_price:item.unit_price??item.unitPrice,currency:item.currency||'CNY'})),notes:data.notes||''};Object.assign(document,{title:'翻译服务报价单',client_name:'',items:[],notes:''},JSON.parse(JSON.stringify(data)));document.items=document.items.map(item=>({...item,quantity:item.quantity==null?undefined:Number(item.quantity),unit_price:item.unit_price==null?undefined:Number(item.unit_price)}));original=JSON.stringify(document)}
async function searchProjects(keyword=''){const seq=++searchSequence;controller?.abort();controller=new AbortController();searching.value=true;try{const data=await getCustomerFinancePage({...props.query,keyword:keyword.trim()||undefined,skip:0,limit:100},{signal:controller.signal});if(seq===searchSequence){const current=options.value.find(row=>row.id===selectedId.value);options.value=data.items||[];if(current&&!options.value.some(row=>row.id===current.id))options.value.unshift(current)}}catch(e){if(seq===searchSequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'项目搜索失败')}finally{if(seq===searchSequence)searching.value=false}}
async function load(){const seq=++sequence;loading.value=true;error.value='';try{if(!selectedId.value)return;const data=await api.get(`/translation-quotations/${selectedId.value}`);if(seq===sequence){revision=data.revision;orderNo.value=data.order_no;assign(data.document)}}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'报价单加载失败')}finally{if(seq===sequence)loading.value=false}}
async function close(value){if(value!==false||saving.value)return;if(JSON.stringify(document)!==original){try{await ElMessageBox.confirm('报价内容尚未保存，是否放弃修改？','关闭报价单',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}emit('update:modelValue',false)}
async function save(){if(!await formRef.value?.validate().catch(()=>false))return;if(!document.items.length)return ElMessage.warning('请至少填写一条报价明细');const data=JSON.parse(JSON.stringify(document));if(props.deferSave){emit('update:draft',data);original=JSON.stringify(document);emit('update:modelValue',false);return}saving.value=true;error.value='';try{const result=await api.put(`/translation-quotations/${selectedId.value}`,{revision,document:data});revision=result.revision;assign(result.document);emit('saved');ElMessage.success('报价单已保存')}catch(e){error.value=getLocalizedErrorMessage(e,'报价单保存失败')}finally{saving.value=false}}
watch(()=>props.modelValue,visible=>{sequence++;searchSequence++;controller?.abort();clearFieldSearch();if(!visible)return;error.value='';options.value=[...props.projects];selectedId.value=options.value[0]?.id||'';orderNo.value=props.draftProject?.orderNo||'';if(props.deferSave){const project=props.draftProject||{};assign(props.draft||{client_name:project.subClientName||project.clientName||project.clientShortName||'',items:[{...newLine(),description:project.sourceFileName||project.projectName||'',language_pair:project.languagePair||''}]})}else{assign({items:[]});void load();void searchProjects()}})
onBeforeUnmount(()=>{sequence++;searchSequence++;controller?.abort()})
</script>
<style scoped>
:global(.customer-quotation-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.customer-quotation-dialog>.el-dialog__header),:global(.customer-quotation-dialog>.el-dialog__footer){flex:none}:global(.customer-quotation-dialog>.el-dialog__body){flex:1;min-height:0;overflow:auto}.quotation-line{border:1px solid var(--el-border-color);border-radius:6px;padding:12px;margin-bottom:12px}.quotation-line-heading{display:flex;justify-content:space-between;margin-bottom:12px}.quotation-line .el-input-number{width:100%}.quotation-help{font-size:12px;color:var(--el-text-color-secondary)}.quotation-totals{font-weight:600}
</style>
