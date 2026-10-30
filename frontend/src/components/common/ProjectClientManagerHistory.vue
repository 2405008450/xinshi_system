<template>
  <el-popover trigger="click" placement="left" :width="760" title="客户经理调整记录" popper-class="project-manager-history" @show="load(1)">
    <template #reference><el-button link type="primary" @click.stop>{{ label }}</el-button></template>
    <div v-loading="loading" class="history-body">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-table v-else :data="items" size="small" border empty-text="暂无调整记录（历史项目未补造记录）">
        <el-table-column label="调整前" prop="previous_manager_name" min-width="90"><template #default="{row}">{{ row.previous_manager_name || '未分配' }}</template></el-table-column>
        <el-table-column label="调整后" prop="new_manager_name" min-width="90"><template #default="{row}">{{ row.new_manager_name || '未分配' }}</template></el-table-column>
        <el-table-column label="调整原因" prop="reason" min-width="160" />
        <el-table-column label="操作人" prop="actor_name" min-width="90" />
        <el-table-column label="调整时间" min-width="175"><template #default="{row}">{{ formatBusinessDateTime(row.changed_at) }}</template></el-table-column>
      </el-table>
    </div>
    <el-pagination v-if="total > 20" small layout="prev,pager,next,total" :page-size="20" :total="total" :current-page="page" @current-change="load" />
  </el-popover>
</template>
<script setup>
import { ref } from 'vue'
import api from '@/api'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props = defineProps({ projectType: String, projectId: String, label: { type: String, default: '查看调整记录' } })
const loading = ref(false), error = ref(''), items = ref([]), total = ref(0), page = ref(1)
let sequence = 0
async function load(nextPage) {
  const request = ++sequence
  loading.value = true; error.value = ''; page.value = nextPage
  try {
    const result = await api.get(`/project-client-managers/${props.projectType}/${props.projectId}/history`, {params:{skip:(nextPage-1)*20,limit:20}})
    if (request !== sequence) return
    items.value = result.items || []; total.value = result.total || 0
  } catch { if (request === sequence) error.value = '调整记录加载失败，请关闭后重试' }
  finally { if (request === sequence) loading.value = false }
}
</script>
<style scoped>
.history-body{max-height:min(480px,calc(100vh - 160px));overflow:auto;overflow-wrap:anywhere}
</style>
<style>.project-manager-history{max-width:calc(100vw - 32px)}</style>
