<template>
  <el-popover v-if="summary.hasData" trigger="click" placement="left" :width="760" title="地区详情" popper-class="annotation-region-summary-popover" :popper-options="viewportPopperOptions">
    <template #reference>
      <el-button link type="primary" class="annotation-region-summary-link" :title="summary.legacy ? `原地区：${summary.text}` : summary.text" @click.stop>
        <span class="annotation-region-summary-text"><span v-if="summary.legacy" class="annotation-region-legacy-prefix">原地区：</span>{{ summary.text }}</span>
        <span v-if="summary.extra" class="annotation-region-summary-count">+{{ summary.extra }}</span>
      </el-button>
    </template>
    <div class="annotation-region-summary-content">
      <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="完整地区" :span="2">
      <table v-if="regions.length" class="annotation-region-detail-table">
        <thead><tr><th>语种方向</th><th>城市</th><th>区县</th><th>街道</th></tr></thead>
        <tbody><tr v-for="(region,index) in regions" :key="index"><td>{{ region.language }}</td><td>{{ region.city || '-' }}</td><td>{{ region.district || '-' }}</td><td>{{ region.street || '-' }}</td></tr></tbody>
      </table>
      <span v-else>尚未录入城市、区县、街道。</span>
      </el-descriptions-item>
        <el-descriptions-item v-if="row.languageRegion || row.areaLabels?.length" label="原语言地区">{{ row.languageRegion || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="row.languageRegion || row.areaLabels?.length" label="原片区">{{ row.areaLabels?.join('、') || '-' }}</el-descriptions-item>
      </el-descriptions>
      <p v-if="row.languageRegion || row.areaLabels?.length" class="annotation-region-hint">原地区按原文保留，未自动对应城市、区县或街道。</p>
    </div>
  </el-popover>
  <span v-else>-</span>
</template>

<script setup>
import { computed } from 'vue'
import { annotationRegionRows, annotationRegionSummary } from '@/utils/annotationRegionDisplay'

const props = defineProps({ row: { type: Object, required: true }, level: { type: String, default: 'city' } })
const regions = computed(() => annotationRegionRows(props.row))
const summary = computed(() => annotationRegionSummary(props.row, props.level))
const viewportPopperOptions = { modifiers: [{ name: 'preventOverflow', options: { rootBoundary: 'viewport', altAxis: true, tether: false, padding: 16 } }] }
</script>

<style scoped>
.annotation-region-summary-link { display:flex; max-width:100%; height:auto; padding:0; line-height:1.5; }
.annotation-region-summary-text { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.annotation-region-summary-count { flex:none; margin-left:5px; color:var(--el-text-color-secondary); }
.annotation-region-legacy-prefix { color:var(--el-text-color-secondary); font-size:12px; }
.annotation-region-summary-content { max-height:min(560px,calc(100vh - 120px)); overflow-y:auto; }
.annotation-region-detail-table { width:100%; table-layout:fixed; border-collapse:collapse; }
.annotation-region-detail-table th,.annotation-region-detail-table td { padding:8px; border:1px solid var(--el-border-color-lighter); text-align:left; overflow-wrap:anywhere; }
.annotation-region-hint { margin:10px 0 0; color:var(--el-text-color-secondary); font-size:12px; }
</style>
<style>
.annotation-region-summary-popover { max-width:calc(100vw - 32px)!important; }
.annotation-region-summary-popover .el-descriptions__label { min-width:75px; white-space:nowrap; vertical-align:top; }
.annotation-region-summary-popover .el-descriptions__content { overflow-wrap:anywhere; white-space:normal; }
</style>
