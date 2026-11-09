<template>
  <div class="project-contact-fields">
    <el-row :gutter="16">
      <el-col :xs="24" :md="12"><el-form-item label="客户联系人" prop="contactName" :rules="contactRules"><el-autocomplete v-model="name" :fetch-suggestions="suggest" value-key="name" :trigger-on-focus="true" :debounce="0" maxlength="100" clearable placeholder="选择已有联系人，或填写新姓名" style="width:100%" /></el-form-item></el-col>
      <el-col :xs="24" :md="12"><el-form-item label="联系人联系方式" prop="clientContactMethod"><el-input v-if="visible" v-model="method" :disabled="loading" maxlength="5000" placeholder="电话、邮箱、微信等（选填）" /><ReadonlyField v-else model-value="仅客户部、销售部、行政部可查看" source="locked" /></el-form-item></el-col>
    </el-row>
    <el-form-item label="联系人说明" prop="clientContactDescription"><el-input v-model="description" :disabled="loading" type="textarea" :rows="2" maxlength="5000" placeholder="职务、联系偏好或其他说明（选填）" /></el-form-item>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
  </div>
</template>
<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import api from '@/api'
import ReadonlyField from './ReadonlyField.vue'
import {matchesSearch} from '@/utils/searchMatching'
const props=defineProps({clientId:String,subClientId:String})
const name=defineModel('contactName',{type:String,default:''}),method=defineModel('contactMethod'),description=defineModel('contactDescription',{type:String,default:''}),version=defineModel('contactVersion'),visible=defineModel('contactsVisible',{type:Boolean,default:false})
const people=ref([]),loading=ref(false),error=ref('')
const contactRules=[{required:true,whitespace:true,message:'请选择或填写客户联系人',trigger:['blur','change']},
  {validator:(_rule,_value,done)=>done(loading.value?new Error('正在读取联系人资料，请稍后保存'):error.value?new Error(error.value):undefined),trigger:'change'}]
let sequence=0,controller
function selectCurrent(){
  if(loading.value)return
  const row=people.value.find(item=>item.name.trim().toLocaleLowerCase()===String(name.value||'').trim().toLocaleLowerCase())
  method.value=visible.value?(row?.contact_method||''):undefined
  description.value=row?.description||''
  version.value=row?.version||'new'
}
async function load(){
  const current=++sequence;controller?.abort();controller=new AbortController();loading.value=true;version.value=undefined;method.value=undefined;description.value='';people.value=[];error.value='';visible.value=false
  try{const result=props.clientId?await api.get('/client-contact-people',{params:{client_id:props.clientId,sub_client_id:props.subClientId||undefined},signal:controller.signal}):await api.get('/client-contact-people/access',{signal:controller.signal});if(current!==sequence)return;people.value=result.contact_people||[];visible.value=result.can_view_contacts===true;loading.value=false;selectCurrent()}
  catch(e){if(current===sequence)error.value='客户联系人资料加载失败，请重新选择客户后重试'}
  finally{if(current===sequence)loading.value=false}
}
function suggest(keyword,done){done(people.value.filter(item=>matchesSearch(item.name,keyword)).map(item=>({name:item.name})))}
watch(()=>[props.clientId,props.subClientId],load,{immediate:true})
watch(name,selectCurrent)
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>
<style scoped>.project-contact-fields{min-width:0;width:100%}</style>
