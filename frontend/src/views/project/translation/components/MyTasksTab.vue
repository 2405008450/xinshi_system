<template>
  <div class="section-label">当前登录用户「{{ currentUserName }}」待处理的笔译项目</div>
  <el-table :data="tasks" border size="small" highlight-current-row @current-change="handleCurrentChange">
    <el-table-column type="index" label="序号" width="60" />
    <el-table-column label="类型" width="70">
      <template #default="{ row }">
        <el-tag :type="row.entity_type === 'suborder' ? 'warning' : 'primary'" size="small" effect="plain">
          {{ row.entity_type === 'suborder' ? '子订单' : '母订单' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="订单号" width="160">
      <template #default="{ row }">
        {{ row.entity_type === 'suborder' ? (row.sub_order_no || row.order_no) : row.order_no }}
      </template>
    </el-table-column>
    <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
    <el-table-column prop="client_short_name" label="客户简称" width="120" />
    <el-table-column label="当前阶段" width="180">
      <template #default="{ row }">
        <span v-if="row.current_stage_key">
          {{ stageByKey[row.current_stage_key]?.title || row.current_stage_key }}
          <el-tag
            v-if="row.current_stage_key === 'reception' && !row.difficulty"
            type="warning"
            size="small"
            style="margin-left: 6px"
          >
            待设定难度
          </el-tag>
        </span>
        <span v-else>-</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }">
        <el-button type="primary" link size="small" @click="$emit('select', row)">进入</el-button>
      </template>
    </el-table-column>
  </el-table>
  <el-empty v-if="!tasks.length" description="暂无待您处理的项目" />
</template>

<script setup>
const emit = defineEmits(['select'])

defineProps({
  tasks: {
    type: Array,
    default: () => []
  },
  currentUserName: {
    type: String,
    default: '当前用户'
  },
  stageByKey: {
    type: Object,
    default: () => ({})
  }
})

function handleCurrentChange(row) {
  if (row) {
    emit('select', row)
  }
}
</script>

<style scoped>
.section-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}
</style>
