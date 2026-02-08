<template>
  <div class="section-block">
    <h3 class="section-title">今日班次</h3>
    <el-table :data="data" border size="small" class="data-table">
      <el-table-column prop="shift" label="班次" width="160" show-overflow-tooltip />
      <el-table-column prop="layoutIt" label="排版" min-width="140" show-overflow-tooltip />
      <el-table-column prop="client" label="客户部" min-width="180" show-overflow-tooltip />
      <el-table-column prop="hr" label="（项目助理）HR部" min-width="120" show-overflow-tooltip />
      <el-table-column prop="translationProject" label="翻译部+项目部" min-width="140" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup>
defineProps({
  data: { type: Array, default: () => [] }
})
</script>

<style scoped>
.section-block { margin-bottom: 28px; }
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-color-primary-light-7);
}
.data-table { margin-bottom: 12px; }
</style>
