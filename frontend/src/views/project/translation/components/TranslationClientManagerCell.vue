<template>
  <el-button link type="primary" class="business-clickable-cell" :title="editable ? '调整客户经理并查看记录' : '查看客户经理调整记录'" @click.stop="open">{{ row.clientManager || '未分配' }}</el-button>
  <DraggableFormDialog v-model="visible" title="客户经理与调整记录" width="min(720px, calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close :close-on-click-modal="false">
    <div v-loading="loading">
      <p class="manager-project">{{ row.orderNo }} · {{ row.sourceFileName || row.projectName }}</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <AppForm v-if="editable && !error" ref="formRef" :model="form" :saved-sync-enabled="false" data-auto-draft="off" label-width="150px" @submit.prevent="save">
        <ProjectClientManagerField :key="historyVersion" v-model="form.clientManagerId" v-model:reason="form.clientManagerChangeReason" :baseline-id="baselineId" :baseline-name="baselineName" :project-id="row.id" project-type="translation" />
      </AppForm>
      <template v-else-if="!editable">
        <p>当前客户经理：{{ baselineName || row.clientManager || '未分配' }}</p>
        <ProjectClientManagerHistory project-type="translation" :project-id="row.id" />
      </template>
    </div>
    <template #footer>
      <el-button :disabled="saving" @click="visible=false">关闭</el-button>
      <el-button v-if="editable" type="primary" :loading="saving" :disabled="loading || !!error || !changed" @click="save">确认调整</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProject, updateProject } from '@/api/projects'
import ProjectClientManagerField from '@/components/common/ProjectClientManagerField.vue'
import ProjectClientManagerHistory from '@/components/common/ProjectClientManagerHistory.vue'

const props=defineProps({row:{type:Object,required:true},editable:Boolean})
const emit=defineEmits(['saved'])
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),formRef=ref(),historyVersion=ref(0)
const baselineId=ref(''),baselineName=ref(''),expectedUpdatedAt=ref(null)
const form=reactive({clientManagerId:'',clientManagerChangeReason:''})
const changed=computed(()=>String(form.clientManagerId||'')!==String(baselineId.value||''))
let sequence=0,controller
async function open(){
  visible.value=true;loading.value=true;error.value=''
  form.clientManagerId='';form.clientManagerChangeReason=''
  const request=++sequence;controller?.abort();controller=new AbortController()
  try{
    const detail=await getProject(props.row.id,{signal:controller.signal})
    if(request!==sequence||!visible.value)return
    baselineId.value=detail.clientManagerId||'';baselineName.value=detail.clientManager||''
    expectedUpdatedAt.value=detail.updatedAt||null
    form.clientManagerId=baselineId.value
    historyVersion.value++
    await nextTick();formRef.value?.clearValidate()
  }catch(err){if(request===sequence&&err.code!=='ERR_CANCELED')error.value=err.detail||'客户经理信息加载失败，请关闭后重试'}
  finally{if(request===sequence)loading.value=false}
}
async function save(){
  if(saving.value||loading.value||!changed.value)return
  if(!await formRef.value?.validate().catch(()=>false))return
  saving.value=true
  try{
    const updated=await updateProject(props.row.id,{clientManagerId:form.clientManagerId||null,clientManagerChangeReason:form.clientManagerChangeReason.trim(),expectedUpdatedAt:expectedUpdatedAt.value})
    baselineId.value=updated.clientManagerId||'';baselineName.value=updated.clientManager||'';expectedUpdatedAt.value=updated.updatedAt||null
    form.clientManagerId=baselineId.value;form.clientManagerChangeReason='';historyVersion.value++
    emit('saved',updated);ElMessage.success('客户经理已调整，调整记录已保存')
  }catch(err){ElMessage.error(err.detail||'客户经理调整失败，请重试')}
  finally{saving.value=false}
}
onBeforeUnmount(()=>{sequence++;controller?.abort()})
</script>

<style scoped>
.manager-project{margin:0 0 18px;color:var(--el-text-color-secondary);overflow-wrap:anywhere}
</style>
