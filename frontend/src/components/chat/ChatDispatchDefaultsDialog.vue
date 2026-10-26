<template>
  <DraggableFormDialog :model-value="Boolean(kind)" :title="data?.label || '标注业务设置'" width="min(680px,calc(100vw - 32px))" append-to-body @update:model-value="value=>!value && $emit('close')">
    <AppForm v-loading="loading" :disabled="saving" label-position="top">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-alert v-if="data && !data.ready" title="共享配置表尚未初始化，当前展示初始规则" type="warning" :closable="false" />
      <p>所有标注项目共用；资源需求发送时可临时增减，不改变此处默认设置。</p>
      <el-form-item label="默认被发送人"><el-select v-model="ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="3" :disabled="!data?.can_manage" :placeholder="kind==='post' ? '选择全公司人员' : '选择标注项目部人员'"><el-option v-for="person in data?.users || []" :key="person.id" :label="person.name" :value="person.id" /></el-select></el-form-item>
      <p v-if="kind==='post'">初始规则：HR 部成员，排除曾紫霞、赵震锋、Lulu。可以加入全公司其他人员。</p>
      <p v-else-if="kind==='circle'">初始名单：黄杰、王露；可调整为标注项目部其他人员。</p>
      <p v-else>初始名单：欧阳靖琳、赵震锋；可加入标注项目部其他人员。</p>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="$emit('close')">关闭</el-button><el-button :disabled="saving || loading || !data?.can_manage" @click="save(true)">恢复初始规则</el-button><el-button type="primary" :loading="saving" :disabled="loading || !data?.can_manage" @click="save(false)">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
const props=defineProps({kind:{type:String,default:''}})
const emit=defineEmits(['close'])
const data=ref(null),ids=ref([]),loading=ref(false),saving=ref(false),error=ref('')
let sequence=0
async function load(){const seq=++sequence;data.value=null;loading.value=true;error.value='';try{const result=await api.get(`/resource-requests/dispatch-defaults/${props.kind}`);if(seq===sequence){data.value=result;ids.value=[...result.user_ids]}}catch(e){if(seq===sequence)error.value=e.detail||e.message}finally{if(seq===sequence)loading.value=false}}
async function save(reset){if(saving.value)return;saving.value=true;error.value='';try{const result=await api.put(`/resource-requests/dispatch-defaults/${props.kind}`,{user_ids:reset?null:ids.value,revision:data.value.revision});data.value=result;ids.value=[...result.user_ids];ElMessage.success('默认接收人设置已保存');emit('close')}catch(e){error.value=e.detail||e.message}finally{saving.value=false}}
watch(()=>props.kind,value=>{if(value)load();else{sequence++;data.value=null}},{immediate:true})
</script>
<style scoped>p{font-size:12px;color:#64748b;line-height:1.8}.el-select{width:100%}</style>
