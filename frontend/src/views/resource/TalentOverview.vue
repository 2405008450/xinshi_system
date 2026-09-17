<template>
  <el-card class="talent-overview-card compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">人才概览</span>
          <span class="page-subtitle">语种与方言资源快照，共 {{ tableRows.length }} 项</span>
        </div>
      </div>
    </template>

    <TalentResourceNav />

    <div class="overview-note">
      合计为原表各单元格相加，不代表去重后的人才人数；空白表示原表未填写，明确的零保留显示为 0。
    </div>

    <el-table
      :data="tableRows"
      row-key="language"
      border
      stripe
      show-summary
      :summary-method="summaryMethod"
      height="calc(100vh - 246px)"
      class="overview-table"
    >
      <el-table-column prop="language" label="语种/方言" width="190" fixed="left" show-overflow-tooltip />
      <el-table-column prop="updatedAt" label="更新日期" width="118" fixed="left" align="center">
        <template #default="{ row }">{{ row.updatedAt || '' }}</template>
      </el-table-column>

      <el-table-column
        v-for="group in TALENT_OVERVIEW_COLUMN_GROUPS"
        :key="group.key"
        :label="group.label"
        header-align="center"
      >
        <el-table-column
          v-for="column in group.columns"
          :key="column.key"
          :prop="`counts.${column.key}`"
          :label="column.label"
          :width="column.width"
          align="right"
          header-align="center"
        >
          <template #default="{ row }">{{ formatTalentCount(row.counts[column.key]) }}</template>
        </el-table-column>
      </el-table-column>

      <el-table-column prop="rowTotal" label="合计" width="112" fixed="right" align="right" header-align="center">
        <template #default="{ row }">{{ formatTalentCount(row.rowTotal) }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import TalentResourceNav from '@/views/resource/components/TalentResourceNav.vue'
import {
  TALENT_OVERVIEW_COLUMNS,
  TALENT_OVERVIEW_COLUMN_GROUPS,
  TALENT_OVERVIEW_ROWS,
} from '@/data/talentOverview'
import {
  calculateTalentColumnTotals,
  calculateTalentGrandTotal,
  calculateTalentRowTotal,
  formatTalentCount,
} from '@/utils/talentOverview'

const tableRows = TALENT_OVERVIEW_ROWS.map(row => ({
  ...row,
  rowTotal: calculateTalentRowTotal(row),
}))
const columnTotals = calculateTalentColumnTotals(tableRows)
const grandTotal = calculateTalentGrandTotal(tableRows)

function summaryMethod({ columns }) {
  return columns.map(column => {
    if (column.property === 'language') return '合计'
    if (column.property === 'updatedAt') return ''
    if (column.property === 'rowTotal') return formatTalentCount(grandTotal)
    const key = column.property?.replace(/^counts\./, '')
    return key && TALENT_OVERVIEW_COLUMNS.some(item => item.key === key)
      ? formatTalentCount(columnTotals[key])
      : ''
  })
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.overview-note {
  margin-bottom: 12px;
  padding: 9px 12px;
  border: 1px solid var(--el-color-info-light-7);
  border-radius: var(--el-border-radius-base);
  background: var(--el-color-info-light-9);
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}

.overview-table {
  min-height: 360px;
}

.overview-table :deep(.el-table__header-wrapper th) {
  background: var(--el-fill-color-light);
}

.overview-table :deep(.el-table__header-wrapper .cell) {
  white-space: normal;
  line-height: 1.35;
}

.overview-table :deep(.el-table__footer-wrapper td) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  font-weight: 600;
}

@media (max-width: 768px) {
  .page-subtitle {
    display: block;
    margin: 4px 0 0;
  }

  .overview-note {
    font-size: 12px;
  }
}
</style>
