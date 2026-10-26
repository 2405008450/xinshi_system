<template>
  <DraggableFormDialog v-model="visible" :title="name ? `${name} · 操作记录` : '我的渠道操作记录'" width="min(850px,calc(100vw - 32px))" append-to-body>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border>
      <el-table-column label="渠道"><template #default="{row}">{{ row.after?.name || row.before?.name || '-' }}</template></el-table-column>
      <el-table-column label="操作" width="80"><template #default="{row}">{{ labels[row.action] || row.action }}</template></el-table-column>
      <el-table-column prop="actor_name" label="操作人" width="110" />
      <el-table-column label="时间" width="190"><template #default="{row}">{{ formatTime(row.created_at) }}</template></el-table-column>
      <el-table-column label="变更内容"><template #default="{row}"><details><summary>查看前后内容</summary><pre>修改前：{{ JSON.stringify(row.before,null,2) }}
修改后：{{ JSON.stringify(row.after,null,2) }}</pre></details></template></el-table-column>
    </el-table>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {developmentApi as api} from '@/api/resourceDevelopment'
import {formatBusinessDateTime as formatTime} from '@/utils/dateTime'
const visible=ref(false),rows=ref([]),name=ref(''),loading=ref(false),error=ref('')
const labels={create:'新增',update:'编辑',delete:'删除'}
async function open(row){visible.value=true;name.value=row?.name || '';rows.value=[];error.value='';loading.value=true;try{rows.value=await (row ? api.channelHistory(row.id) : api.channelOperationHistory())}catch(e){error.value=e.detail||e.message}finally{loading.value=false}}
defineExpose({open})
</script>
<style scoped>pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;overflow:auto;font-size:12px}</style>
