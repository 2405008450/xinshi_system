<template>
  <el-card class="common-page-card compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">供应商</span>
          <p class="page-subtitle">外部翻译及数据服务供应商集中管理</p>
        </div>
      </div>
    </template>
    <TalentResourceNav />
    <div class="empty-state">暂无供应商数据</div>
  </el-card>
</template>

<script setup>
import TalentResourceNav from './components/TalentResourceNav.vue'
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
