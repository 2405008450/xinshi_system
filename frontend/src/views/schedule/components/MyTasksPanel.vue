<template>
  <div class="section-block">
    <p v-if="currentUserName" class="section-desc">当前用户：<strong>{{ currentUserName }}</strong></p>
    <el-table :data="tasksList" border size="small" class="data-table">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="category" label="任务类型" width="140">
        <template #default="{ row }">
          <el-tag :type="getTaskCategoryType(row.category)" size="small" effect="plain">
            {{ row.category }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="任务内容" min-width="300" show-overflow-tooltip />
      <el-table-column prop="projectNo" label="项目编号" width="140" show-overflow-tooltip />
      <el-table-column prop="deadline" label="交稿时间" width="140" show-overflow-tooltip />
    </el-table>
    <div v-if="currentUserName && !tasksList.length" class="info-block">
      <p>暂无您的任务，或安排表中的姓名与登录账号不一致。如有疑问请联系项目经理。</p>
    </div>
    <el-empty v-else-if="!currentUserName" description="请先登录，登录账号将用于匹配「我的任务」" />
  </div>
</template>

<script setup>
const TASK_CATEGORY_TYPE = { '直接项目任务': 'danger', '非直接项目任务': 'warning', '固定任务': 'info', '其他': '' }

defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] }
})

function getTaskCategoryType(cat) {
  return TASK_CATEGORY_TYPE[cat] || ''
}
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
