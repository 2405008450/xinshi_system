<template>
  <el-card class="common-page-card">
    <template #header><strong>数据分析</strong></template>
    <el-tabs v-model="activeDimension">
      <el-tab-pane v-for="item in dimensions" :key="item.key" :label="item.label" :name="item.key">
        <CustomerSourceAnalysis v-if="activeDimension === item.key" :key="item.key" :dimension="item.key" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import CustomerSourceAnalysis from '@/components/common/CustomerSourceAnalysis.vue'
const activeDimension = ref('source')
const dimensions = [
  { key: 'source', label: '客户来源分析' }, { key: 'method', label: '咨询方式分析' },
  { key: 'type', label: '咨询类型分析' }, { key: 'keyword', label: '关键词分析' },
  { key: 'status', label: '咨询状态分析' }, { key: 'type_status', label: '咨询类型 × 咨询状态' },
  { key: 'type_confirmed', label: '项目类型成交分析' }, { key: 'source_confirmed', label: '客户来源成交分析' },
]
</script>
