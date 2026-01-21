<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>工作安排</span>
      </div>
    </template>
    <div class="empty-state">暂无工作安排数据</div>
  </el-card>
</template>

<script setup>
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 24px 0;
  color: #9ca3af;
  text-align: center;
}
</style>
