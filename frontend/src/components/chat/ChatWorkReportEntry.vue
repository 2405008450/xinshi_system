<template>
  <el-button v-if="allowed && projectId" link :loading="loading" aria-label="填写工作报告" @click="open"><el-icon><Document /></el-icon><span>工作报告</span></el-button>
  <WorkReportDialog v-if="visible" v-model="visible" :project="context" />
</template>
<script setup>
import {computed,defineAsyncComponent,ref} from 'vue'
import {Document} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'
import {hasPermission} from '@/utils/permission'
import {copyTextToClipboard} from '@/utils/clipboard'
import {displayedReportProject} from '@/utils/chatWorkReportContext'
const props=defineProps({projectId:String,projectType:String,title:String,orderNo:String})
const emit=defineEmits(['opened'])
const WorkReportDialog=defineAsyncComponent(()=>import('@/components/common/WorkReportDialog.vue'))
const allowed=computed(()=>hasPermission('reports:read')||hasPermission('reports:write'))
const visible=ref(false),loading=ref(false),context=ref(null)
async function open(){
  if(loading.value||!props.projectId)return
  loading.value=true
  const id=props.projectId,kind=props.projectType
  try{
    context.value=displayedReportProject(props)
    if(context.value?.orderNo&&!await copyTextToClipboard(context.value.orderNo))ElMessage.warning('订单号自动复制失败，可在工作报告中复制')
    if(id!==props.projectId||kind!==props.projectType)return
    visible.value=true;emit('opened')
  }catch(e){ElMessage.error(e.detail||e.message||'打开工作报告失败')}
  finally{loading.value=false}
}
</script>
