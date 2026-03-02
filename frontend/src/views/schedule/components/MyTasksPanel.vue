<template>
  <div class="section-block">
    <p v-if="currentUserName" class="section-desc">当前用户：<strong>{{ currentUserName }}</strong></p>
    <el-table :data="tasksList" border size="small" class="data-table">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="order_no" label="项目编号" width="180" show-overflow-tooltip />
      <el-table-column prop="client_short_name" label="客户简称" width="120" show-overflow-tooltip />
      <el-table-column prop="current_stage_key" label="当前阶段" width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ STAGE_LABELS[row.current_stage_key] || row.current_stage_key }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="difficulty" label="难度" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
            {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="project_status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPE[row.project_status] || ''" size="small" effect="plain">
            {{ STATUS_LABEL[row.project_status] || row.project_status }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="currentUserName && !tasksList.length" class="info-block">
      <p>暂无待处理的工作流任务。</p>
    </div>
    <el-empty v-else-if="!currentUserName" description="请先登录，登录账号将用于匹配「我的任务」" />
  </div>
</template>

<script setup>
const STAGE_LABELS = {
  reception: '客户专员',
  layout_assign: '排版指派',
  project_manager: '项目经理',
  project_specialist: '项目专员',
  project_assistant: '项目助理',
  review: '译审',
  special_qc: '专检',
  layout: '排版',
  completed: '完成'
}

const DIFFICULTY_LABEL = { simple: '简单', normal: '普通', complex: '复杂' }
const DIFFICULTY_TYPE = { simple: 'success', normal: '', complex: 'danger' }
const STATUS_LABEL = { pending: '待处理', in_progress: '进行中', completed: '已完成', paused: '暂停' }
const STATUS_TYPE = { pending: 'info', in_progress: '', completed: 'success', paused: 'warning' }

defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})
</script>

<style scoped>
.section-block { margin-bottom: 28px; }
.section-desc { margin: 0 0 8px 0; line-height: 1.6; color: var(--el-text-color-regular); }
.data-table { margin-bottom: 12px; }
.info-block {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.info-block p { margin: 0; font-size: 13px; color: var(--el-text-color-regular); }
</style>
