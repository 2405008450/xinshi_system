<template>
  <el-button
    v-if="fields.length"
    data-testid="seed-project-account-fields"
    size="small"
    type="primary"
    plain
    :disabled="disabled || !projectId"
    :loading="loading"
    @click="seedFields"
  >补齐标准列（{{ fields.length }}）</el-button>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createCustomField } from '@/api/annotationOps'

const props=defineProps({
  projectId:{type:String,default:''},
  fields:{type:Array,default:()=>[]},
  disabled:{type:Boolean,default:false},
})
const emit=defineEmits(['completed'])
const loading=ref(false)

const seedFields=async()=>{
  if(!props.projectId||!props.fields.length||loading.value)return
  loading.value=true
  try{
    for(const field of props.fields){
      await createCustomField({projectId:props.projectId,tableCode:'account_assignment',...field,options:[],isRequired:false,isActive:true})
    }
    ElMessage.success('项目账号标准列已补齐')
    emit('completed')
  }catch(error){ElMessage.error(error.detail||'补齐标准列失败')}
  finally{loading.value=false}
}
</script>
