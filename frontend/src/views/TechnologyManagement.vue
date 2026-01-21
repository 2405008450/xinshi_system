<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>技术管理</span>
      </div>
    </template>
    <div class="empty-state">暂无技术管理数据</div>
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
