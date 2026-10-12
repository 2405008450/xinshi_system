<template>
  <el-popover trigger="click" placement="left" :width="760" title="开拓问题详情" popper-class="issue-detail-popover" @show="load">
    <template #reference><el-button link type="primary">查看详情</el-button></template>
    <div v-loading="loading" class="issue-detail-body">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button text @click="load">重试</el-button></el-alert>
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="内容" :span="2">{{ detail.content }}</el-descriptions-item>
          <el-descriptions-item label="讨论主题" :span="2">{{ detail.topic_path || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类别">{{ issueCategoryLabel(detail.category) }}</el-descriptions-item><el-descriptions-item label="提出人">{{ detail.proposer_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源" :span="2"><span v-if="detail.source_type==='manual'">手工新增</span><el-button v-else link type="primary" class="issue-source" @click="$emit('source', detail)">{{ detail.source_title }}</el-button></el-descriptions-item>
          <el-descriptions-item label="原始消息" :span="2">{{ detail.source_content || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remarks || '-' }}</el-descriptions-item>
          <el-descriptions-item label="收录人">{{ detail.collected_by_name }}</el-descriptions-item><el-descriptions-item label="收录时间">{{ formatBusinessDateTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ formatBusinessDateTime(detail.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        <h4>后续安排（{{ detail.tasks.length }}）</h4>
        <p v-if="!detail.tasks.length">-</p>
        <el-descriptions v-for="task in detail.tasks" :key="task.id" :column="2" border size="small" class="issue-task-detail">
          <el-descriptions-item label="安排内容" :span="2">{{ task.content }}</el-descriptions-item><el-descriptions-item label="执行人">{{ task.executor_name }}</el-descriptions-item>
          <el-descriptions-item label="实际进度">{{ issueStatusLabel(task.status) }}</el-descriptions-item>
          <el-descriptions-item label="预定完成日期">{{ issueDateLabel(task.planned_date) }}</el-descriptions-item><el-descriptions-item label="实际完成日期">{{ issueDateLabel(task.completed_date) }}</el-descriptions-item>
          <el-descriptions-item label="进展说明" :span="2">{{ task.progress || '-' }}</el-descriptions-item><el-descriptions-item label="备注" :span="2">{{ task.remarks || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </div>
  </el-popover>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { issueApi } from '@/api/resourceIssues'
import { issueCategoryLabel, issueStatusLabel, issueDateLabel } from '@/utils/resourceIssues'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props=defineProps({row:{type:Object,required:true},version:Number})
defineEmits(['source'])
const detail=ref(null),loading=ref(false),error=ref('');let controller,seq=0
watch(()=>[props.row.id,props.row.revision,props.version],()=>{controller?.abort();seq++;detail.value=null;error.value='';loading.value=false})
async function load(){if(detail.value)return;controller?.abort();controller=new AbortController();const current=++seq;loading.value=true;error.value='';try{const data=await issueApi.detail(props.row.id,controller.signal);if(current===seq)detail.value=data}catch(e){if(current===seq&&e.code!=='ERR_CANCELED')error.value=e.message}finally{if(current===seq)loading.value=false}}
onBeforeUnmount(()=>{seq++;controller?.abort()})
</script>
<style scoped>.issue-task-detail{margin-bottom:14px}.issue-source{height:auto;white-space:normal;text-align:left}</style>
