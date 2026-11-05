<template>
  <section v-loading="loading" class="cooperation-projects">
    <el-empty v-if="!clientId" description="请先保存客户，再查看合作项目" />
    <el-empty v-else-if="!canRead" description="暂无项目查看权限" />
    <el-alert v-else-if="error" :title="error" type="error" :closable="false">
      <el-button link type="primary" @click="load">重新加载</el-button>
    </el-alert>
    <template v-else>
      <section v-for="group in groups" :key="group.module" class="project-group">
        <h3>{{ group.label }}（{{ group.items.length }}）</h3>
        <el-table :data="pageRows(group)" border size="small" max-height="360" row-key="id">
          <el-table-column type="index" :index="index => rowIndex(group.module, index)" label="序号" width="64" />
          <el-table-column prop="order_no" label="订单号" min-width="180" show-overflow-tooltip />
          <el-table-column prop="project_name" label="项目名称" min-width="240" show-overflow-tooltip />
          <el-table-column label="项目状态" min-width="150">
            <template #default="{ row }">{{ getProjectStatusLabel(group.module, row.project_status) || '-' }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="pagination[group.module].page"
          v-model:page-size="pagination[group.module].limit"
          :total="group.items.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          size="small"
          class="project-pagination"
          @size-change="pagination[group.module].page = 1"
        />
      </section>
      <el-empty v-if="!loading && !groups.length" description="暂无关联的合作项目" />
    </template>
  </section>
</template>

<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { getClientProjects } from '@/api/clients'
import { hasPermission } from '@/utils/permission'
import { getProjectStatusLabel } from '@/utils/projectStatus'

const props = defineProps({ clientId: { type: [String, Number], default: '' } })
const canRead = hasPermission('projects:read')
const groups = ref([])
const loading = ref(false)
const error = ref('')
const pagination = reactive(Object.fromEntries(
  ['translation', 'interpretation', 'annotation', 'recruitment'].map(module => [module, { page: 1, limit: 10 }]),
))

function pageRows(group) {
  const { page, limit } = pagination[group.module]
  return group.items.slice((page - 1) * limit, page * limit)
}

function rowIndex(module, index) {
  const { page, limit } = pagination[module]
  return (page - 1) * limit + index + 1
}

let controller
let requestId = 0

async function load() {
  controller?.abort()
  const current = ++requestId
  groups.value = []
  Object.values(pagination).forEach(state => { state.page = 1; state.limit = 10 })
  error.value = ''
  loading.value = false
  if (!props.clientId || !canRead) return
  controller = new AbortController()
  loading.value = true
  try {
    const result = await getClientProjects(props.clientId, { signal: controller.signal })
    if (current === requestId) groups.value = (result.groups || []).filter(group => group.items?.length)
  } catch (e) {
    if (current === requestId && e?.code !== 'ERR_CANCELED') error.value = e?.detail || '加载合作项目失败，请重试'
  } finally {
    if (current === requestId) loading.value = false
  }
}

watch(() => props.clientId, load, { immediate: true })
onBeforeUnmount(() => { ++requestId; controller?.abort() })
useProjectStatusSync('translation',()=>groups.value.flatMap(group=>pageRows(group).map(row=>({...row,_statusModule:group.module}))),{field:'project_status',typeForRow:row=>row._statusModule,onChanged:changes=>{for(const group of groups.value)for(const row of group.items){const status=changes.find(item=>item.projectType===group.module&&item.id===String(row.id));if(status)row.project_status=status.status}}})
</script>

<style scoped>
.cooperation-projects { min-height: 240px; }
.project-group { margin-bottom: 24px; }
.project-group h3 { margin: 0 0 12px; font-size: 15px; }
.project-pagination { margin-top: 12px; flex-wrap: wrap; gap: 8px; }
</style>
