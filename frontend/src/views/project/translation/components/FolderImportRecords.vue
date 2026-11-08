<template>
 <el-popover trigger="click" placement="bottom-end" :width="760" title="目录导入与空文件夹记录（最近100次；Excel可导出全部）" @show="load">
  <template #reference><el-button>目录导入记录</el-button></template>
  <div class="folder-import-records" v-loading="loading"><p v-if="error" role="alert">{{ error }}</p><el-empty v-if="!rows.length && !loading" description="暂无导入记录" />
   <el-descriptions v-for="row in rows" :key="row.id" :column="2" border size="small">
    <el-descriptions-item label="操作人">{{ row.actorName }}</el-descriptions-item><el-descriptions-item label="时间">{{ formatBusinessDateTime(row.createdAt) }}</el-descriptions-item>
    <el-descriptions-item label="根路径" :span="2">{{ row.rootPath }}</el-descriptions-item>
    <el-descriptions-item label="处理结果" :span="2">新增 {{ row.createdCount }} 单；空文件夹 {{ row.emptyFolders.length }} 个，未生成订单。<span v-if="!row.emptyDetectionComplete">兼容模式未检测空文件夹。</span></el-descriptions-item>
    <el-descriptions-item v-if="row.emptyFolders.length" label="空文件夹" :span="2"><div v-for="path in row.emptyFolders" :key="path">{{ row.rootPath.replace(/[\\\/]$/,'')+(path.includes('/')?'\\'+path.split('/').slice(1).join('\\'):'') }}</div></el-descriptions-item>
   </el-descriptions>
  </div>
 </el-popover>
</template>
<script setup>
import {ref} from 'vue'
import {getFolderImportRecords} from '@/api/subOrders'
import {formatBusinessDateTime} from '@/utils/deadlineDisplay'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({projectId:{type:String,required:true}})
const rows=ref([]),loading=ref(false),error=ref('')
async function load(){loading.value=true;error.value='';try{rows.value=(await getFolderImportRecords(props.projectId)).items||[]}catch(reason){error.value=getLocalizedErrorMessage(reason,'读取记录失败')}finally{loading.value=false}}
</script>
<style scoped>.folder-import-records{max-height:min(560px,calc(100vh - 120px));overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;user-select:text}.el-descriptions{margin-bottom:12px}</style>
